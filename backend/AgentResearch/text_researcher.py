#!/usr/bin/env python3
"""
text_researcher.py

A parallel, agentic web researcher for text questions.

The design intentionally keeps the Qwen-facing protocol small. Qwen only decides
simple actions: search, open, dig, split, accept, reject, stop, and optionally a
short global need update. The code translates those tiny actions into the heavier
work: DuckDuckGo discovery, HTML fetching, heading snapshots, text chunking,
Octen embedding scoring, semantic duplicate checks, split-agent scheduling,
acceptance storage, and final evidence-grounded synthesis.

Expected local services/deps:
  - Qwen vLLM server compatible with /generate/text, such as qwen_vllm_server.py
  - sentence-transformers with Octen/Octen-Embedding-0.6B
  - ddgs or duckduckgo_search

Example:
  python text_researcher.py "What are the main causes of X?" \
    --qwen-url http://127.0.0.1:8009 --max-agents 8 --out-dir runs/x
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import dataclasses
from dataclasses import dataclass, field
import datetime as _dt
import hashlib
import html
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import threading
import time
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse, urlunparse, unquote

import numpy as np
import requests
from bs4 import BeautifulSoup, Tag

try:
    from ddgs import DDGS  # type: ignore
except Exception:  # pragma: no cover
    try:
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:  # pragma: no cover
        DDGS = None  # type: ignore


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

TEXT_ROUTE_AGENT_SYSTEM_PROMPT = """
You are TextRouteAgent, the routing mind inside a parallel web researcher. You are not the writer of the final answer and you do not use memory as evidence. The code around you can search the web, open pages, split into other agents, and perform embedding digs that return headings, snapshots, cosine scores, and short snippets from the page. Your job is only to choose the next small actions from the visible state.

The current research state contains the original question, the shared "need" field, global hints found by other agents, how many parallel agent slots are still free, the source assigned to you, compact page snapshots, and the latest dig reports. A dig is like punching a hole into one page: the code embeds page chunks and links with Octen embeddings, shows the top chunks, the score distribution, and the next link candidates. Treat the score as routing evidence, not as truth. A high score is useful only when the snippet actually contains the missing information. A low score is not a failure if the page snapshot points toward a better link or a better query.

Keep every option emotionally neutral. Do not dig only because a heading has a good keyword. Dig because the visible structure and the score evidence make it likely that the missing information is there. Quit branches quickly when they look thin, circular, generic, promotional, paywalled, or off-topic. Prefer asking for a better search query over grinding through a weak source. When there is no useful source, request a DuckDuckGo search with a concrete query that is likely to return large information sources, official docs, papers, manuals, reports, encyclopedic pages, or high-signal explainers rather than random blog fragments.

Use splits when one source has multiple plausible holes or when one promising link deserves its own route. A split creates another agent with the same source or a link from the last snapshot/dig, so your current agent can continue independently. The orchestrator may batch many agents at once and may deduplicate very similar searches or splits using embeddings. You can accept a dig by id when the evidence shown is enough; say only the accept action and the code will store the underlying text without making you copy it. You can accept and also request another query if the accepted information answers only part of the need.

You may refine the shared need with one short sentence when the visible research has clarified what should be searched for next. Do not bloat it; it is global memory, not a notebook. Make decisions in a way that keeps output tokens tiny.

Return only JSON with this shape:
{"need":"optional short refined need or empty","act":[{"t":"search","q":"query"},{"t":"open","s":"S1"},{"t":"open","l":"L2"},{"t":"dig","s":"S1","q":"narrow dig text"},{"t":"split","s":"S1","q":"subgoal"},{"t":"split","l":"L3","q":"subgoal"},{"t":"accept","d":"D1"},{"t":"reject","s":"S1"},{"t":"stop"}]}

Use at most three actions. Use only visible ids. For link ids use ids visible in the latest snapshot or dig. Keep all strings short. No markdown. No prose outside JSON.
""".strip()

ACTION_REPAIR_SYSTEM_PROMPT = """
You repair a broken TextRouteAgent answer into strict JSON only.
Valid shape: {"need":"short or empty","act":[{"t":"search|open|dig|split|accept|reject|stop","q":"optional","s":"optional","l":"optional","d":"optional"}]}
Keep at most three actions, use only values visible in the input, and output no prose.
""".strip()

FINAL_SYNTHESIS_SYSTEM_PROMPT = """
You are the final answer writer for TextRouteResearcher. You receive the original question and only the accepted evidence saved by the routing agents. Answer from that accepted evidence, not from outside memory. Use a clear paragraph-first answer. Cite evidence handles like [E1] inline. If the evidence is partial, say exactly what is missing and do not pretend certainty.
""".strip()

ACCEPT_NOTE_SYSTEM_PROMPT = """
You compress accepted page text into one useful evidence paragraph for a later final answer. Use only the supplied page text. Keep concrete details, numbers, definitions, dates, and named claims. Do not add outside facts. Return JSON only: {"p":"paragraph"}
""".strip()

COMPLETION_SUPERVISOR_SYSTEM_PROMPT = """
You are TextCompletionSupervisor, a small finish judge above the route agents. You do not search, route, or write the final answer. Decide whether the accepted evidence is now enough to answer the original question satisfactorily.

Compare the accepted evidence against the expanded query shape: the original question, current need, hints, and query history. Return done=true only when the accepted evidence directly covers the main ask with enough concrete facts for a grounded answer. Return done=false when important parts are missing, evidence is too thin, or it only answers a side issue.

Return only JSON: {"done":true,"why":"short reason"} or {"done":false,"why":"short missing point"}.
Keep why under 160 characters. No markdown. No prose outside JSON.
""".strip()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

USER_AGENT = "TextRouteResearcher/0.1 (+local research agent; respectful requests)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

NON_HTML_EXT = (
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp3", ".wav", ".mp4", ".mov", ".avi", ".webm",
)

BAD_URL_WORDS = (
    "mailto:", "javascript:", "tel:", "#", "/login", "/signin", "/account",
    "/privacy", "/terms", "/cookies", "/advertise", "/subscribe", "/cart",
)

SHELL_TEXT_RE = re.compile(r"\s+")


def now_iso() -> str:
    return _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def stable_id(prefix: str, text: str, n: int = 10) -> str:
    h = hashlib.sha1(str(text or "").encode("utf-8", errors="ignore")).hexdigest()[:n]
    return f"{prefix}{h}"


def norm_space(s: str) -> str:
    return SHELL_TEXT_RE.sub(" ", str(s or "")).strip()


def cap(s: str, n: int) -> str:
    s = norm_space(s)
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)].rstrip() + "..."


def clean_url(url: str, base: str = "") -> str:
    url = (url or "").strip()
    if not url:
        return ""
    try:
        if base:
            url = urljoin(base, url)
        url = html.unescape(unquote(url))
        low = url.lower()
        if any(low.startswith(x) for x in ("mailto:", "javascript:", "data:", "tel:")):
            return ""
        p = urlparse(url)
        if not p.scheme:
            p = urlparse("https://" + url)
        host = (p.hostname or "").lower()
        if not host:
            return ""
        path = re.sub(r"/{2,}", "/", p.path or "/")
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        query = re.sub(r"(^|&)(utm_[^=&]+|fbclid|gclid)=[^&]*", "", p.query or "")
        query = query.strip("&")
        return urlunparse((p.scheme or "https", host, path, "", query, ""))
    except Exception:
        return ""


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_probably_html_url(url: str) -> bool:
    u = (url or "").lower()
    if not u or any(x in u for x in BAD_URL_WORDS):
        return False
    path = urlparse(u).path or ""
    return not path.endswith(NON_HTML_EXT)


def json_safe(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return json_safe(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    return obj


def extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Best-effort JSON object extraction from model output."""
    if not text:
        return None
    s = str(text).strip()
    if "</think>" in s:
        s = s.split("</think>", 1)[1].strip()
    s = re.sub(r"^```(?:json)?\s*", "", s.strip(), flags=re.I)
    s = re.sub(r"\s*```$", "", s.strip())
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = s[start:i + 1]
                try:
                    obj = json.loads(chunk)
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


# ---------------------------------------------------------------------------
# Qwen client
# ---------------------------------------------------------------------------

class QwenBatchClient:
    def __init__(self, base_url: str, *, timeout: float = 600.0) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.timeout = float(timeout)

    def generate_text_batch(
        self,
        prompts: list[str],
        *,
        system_prompt: str,
        generation: Optional[dict[str, Any]] = None,
        use_tqdm: bool = False,
    ) -> list[str]:
        if not prompts:
            return []
        url = f"{self.base_url}/generate/text"
        payload = {
            "prompts": list(prompts),
            "system_prompt": system_prompt,
            "generation": generation or {
                "max_new_tokens": 320,
                "temperature": 0.0,
                "top_p": 1.0,
                "top_k": -1,
                "repetition_penalty": 1.0,
                "skip_special_tokens": True,
            },
            "use_tqdm": bool(use_tqdm),
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        rows = data.get("responses") or data.get("results") or []
        out: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                out.append(str(row.get("text", "") or row.get("output", "") or ""))
            else:
                out.append(str(row or ""))
        if len(out) != len(prompts):
            raise RuntimeError(f"Qwen batch response mismatch: got {len(out)} for {len(prompts)} prompts")
        return out


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

class EmbeddingService:
    """Thread-safe wrapper around Octen/Octen-Embedding-0.6B.

    The hash fallback exists only so the module can compile/smoke-test on machines
    without the model installed. Production should keep allow_hash_fallback=False.
    """

    def __init__(
        self,
        model_name: str = "Octen/Octen-Embedding-0.6B",
        *,
        normalize: bool = True,
        batch_size: int = 64,
        allow_hash_fallback: bool = False,
    ) -> None:
        self.model_name = model_name
        self.normalize = bool(normalize)
        self.batch_size = max(1, int(batch_size))
        self.allow_hash_fallback = bool(allow_hash_fallback)
        self._lock = threading.Lock()
        self._model = None
        self.dim = 1024
        self.using_hash_fallback = False
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(model_name)
        except Exception as exc:
            if not allow_hash_fallback:
                raise RuntimeError(
                    f"Could not load embedding model {model_name!r}. Install sentence-transformers "
                    "and ensure the model is available, or set allow_hash_fallback=True for tests."
                ) from exc
            self.using_hash_fallback = True
            self.dim = 384

    def encode(self, texts: str | list[str]) -> np.ndarray:
        single = isinstance(texts, str)
        rows = [texts] if single else list(texts or [])
        if not rows:
            return np.zeros((0, self.dim), dtype=np.float32)
        if self.using_hash_fallback:
            arr = np.stack([self._hash_embed(t) for t in rows], axis=0)
            return arr[0] if single else arr
        outs: list[np.ndarray] = []
        with self._lock:
            for i in range(0, len(rows), self.batch_size):
                chunk = rows[i:i + self.batch_size]
                emb = self._model.encode(chunk, normalize_embeddings=self.normalize)  # type: ignore[union-attr]
                outs.append(np.asarray(emb, dtype=np.float32))
        arr = np.concatenate(outs, axis=0)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        self.dim = int(arr.shape[-1])
        return arr[0] if single else arr

    def sim(self, a: str | np.ndarray, b: str | np.ndarray) -> float:
        av = self.encode(a) if isinstance(a, str) else np.asarray(a, dtype=np.float32)
        bv = self.encode(b) if isinstance(b, str) else np.asarray(b, dtype=np.float32)
        av = self._norm(av)
        bv = self._norm(bv)
        return float(np.dot(av, bv))

    def _norm(self, v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=np.float32).reshape(-1)
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def _hash_embed(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"[a-zA-Z0-9_]+", str(text or "").lower()):
            h = int(hashlib.sha1(tok.encode("utf-8")).hexdigest()[:8], 16)
            v[h % self.dim] += 1.0
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

@dataclass
class LinkRef:
    id: str
    url: str
    text: str
    context: str = ""
    score: float = 0.0


@dataclass
class TextChunk:
    id: str
    heading: str
    text: str
    score: float = 0.0
    rank: int = 0


@dataclass
class PageDoc:
    url: str
    final_url: str
    title: str
    meta: str
    headings: list[str]
    lead: str
    chunks: list[TextChunk]
    links: list[LinkRef]
    fetched_at: str
    status_code: Optional[int] = None
    content_type: str = ""
    error: str = ""

    def compact_snapshot(self, *, max_headings: int = 18, max_links: int = 12) -> str:
        hs = " | ".join(cap(h, 70) for h in self.headings[:max_headings])
        ls = " | ".join(f"{l.id}:{cap(l.text or l.url, 50)}" for l in self.links[:max_links])
        return (
            f"title: {cap(self.title, 130)}\n"
            f"url: {self.final_url or self.url}\n"
            f"meta: {cap(self.meta, 220)}\n"
            f"lead: {cap(self.lead, 420)}\n"
            f"headings: {hs or 'none'}\n"
            f"links: {ls or 'none'}\n"
            f"chunks: {len(self.chunks)} link_count: {len(self.links)}"
        )


class PageFetcher:
    def __init__(
        self,
        *,
        timeout: float = 18.0,
        max_chars: int = 180_000,
        chunk_chars: int = 1000,
        chunk_overlap: int = 160,
    ) -> None:
        self.timeout = float(timeout)
        self.max_chars = int(max_chars)
        self.chunk_chars = max(300, int(chunk_chars))
        self.chunk_overlap = max(0, int(chunk_overlap))
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch(self, url: str) -> PageDoc:
        clean = clean_url(url)
        if not clean:
            return PageDoc(url=url, final_url=url, title="", meta="", headings=[], lead="", chunks=[], links=[], fetched_at=now_iso(), error="invalid_url")
        if not is_probably_html_url(clean):
            return PageDoc(url=clean, final_url=clean, title="", meta="", headings=[], lead="", chunks=[], links=[], fetched_at=now_iso(), error="non_html_url")
        try:
            r = self.session.get(clean, timeout=self.timeout, allow_redirects=True)
            ct = (r.headers.get("Content-Type") or "").lower()
            if r.status_code >= 400:
                return PageDoc(url=clean, final_url=str(r.url or clean), title="", meta="", headings=[], lead="", chunks=[], links=[], fetched_at=now_iso(), status_code=r.status_code, content_type=ct, error=f"http_{r.status_code}")
            if "html" not in ct and "xml" not in ct and ct:
                return PageDoc(url=clean, final_url=str(r.url or clean), title="", meta="", headings=[], lead="", chunks=[], links=[], fetched_at=now_iso(), status_code=r.status_code, content_type=ct, error="content_type_not_html")
            text = r.text or ""
            if len(text) > self.max_chars:
                text = text[: self.max_chars]
            return self.parse(text, requested_url=clean, final_url=str(r.url or clean), status_code=r.status_code, content_type=ct)
        except Exception as exc:
            return PageDoc(url=clean, final_url=clean, title="", meta="", headings=[], lead="", chunks=[], links=[], fetched_at=now_iso(), error=f"fetch_error:{exc.__class__.__name__}")

    def parse(self, html_text: str, *, requested_url: str, final_url: str, status_code: Optional[int], content_type: str) -> PageDoc:
        soup = BeautifulSoup(html_text or "", "html.parser")
        for tag in soup(["script", "style", "noscript", "template", "svg", "canvas", "form"]):
            tag.decompose()
        title = norm_space(soup.title.get_text(" ", strip=True) if soup.title else "")
        meta = ""
        md = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if isinstance(md, Tag):
            meta = norm_space(md.get("content") or "")
        if not meta:
            og = soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})
            if isinstance(og, Tag):
                meta = norm_space(og.get("content") or "")

        headings: list[str] = []
        for h in soup.find_all(re.compile(r"^h[1-6]$")):
            t = norm_space(h.get_text(" ", strip=True))
            if t and t.lower() not in {"navigation", "menu", "contents"}:
                headings.append(t)

        main = soup.find("main") or soup.find("article") or soup.body or soup
        blocks = self._extract_blocks(main)
        lead = " ".join(t for _, t in blocks[:5])
        chunks = self._blocks_to_chunks(blocks)
        links = self._extract_links(soup, final_url)
        return PageDoc(
            url=requested_url,
            final_url=final_url,
            title=title,
            meta=meta,
            headings=headings,
            lead=cap(lead, 2000),
            chunks=chunks,
            links=links,
            fetched_at=now_iso(),
            status_code=status_code,
            content_type=content_type,
        )

    def _extract_blocks(self, root: Tag) -> list[tuple[str, str]]:
        blocks: list[tuple[str, str]] = []
        heading_path: list[str] = []
        selector = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "figcaption", "td", "th"]
        for el in root.find_all(selector):
            if not isinstance(el, Tag):
                continue
            if self._inside_bad_region(el):
                continue
            name = (el.name or "").lower()
            text = norm_space(el.get_text(" ", strip=True))
            if not text or len(text) < 35:
                continue
            if name.startswith("h") and len(name) == 2:
                lvl = int(name[1])
                heading_path = heading_path[: max(0, lvl - 1)] + [text]
                continue
            head = " > ".join(heading_path[-3:])
            blocks.append((head, text))
        if not blocks:
            txt = norm_space(root.get_text(" ", strip=True))
            for part in re.split(r"(?<=[.!?])\s+", txt):
                if len(part) > 80:
                    blocks.append(("", part))
        return blocks

    def _inside_bad_region(self, el: Tag) -> bool:
        for p in list(el.parents)[:5]:
            if not isinstance(p, Tag):
                continue
            name = (p.name or "").lower()
            if name in {"nav", "footer", "header", "aside"}:
                return True
            cls = " ".join(p.get("class") or []).lower()
            role = str(p.get("role") or "").lower()
            ident = str(p.get("id") or "").lower()
            blob = " ".join([cls, role, ident])
            if any(w in blob for w in ("nav", "footer", "header", "sidebar", "breadcrumb", "cookie", "modal", "menu")):
                return True
        return False

    def _blocks_to_chunks(self, blocks: list[tuple[str, str]]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        cur_text: list[str] = []
        cur_head = ""
        idx = 1
        for head, text in blocks:
            if cur_text and (sum(len(x) for x in cur_text) + len(text) > self.chunk_chars):
                joined = norm_space(" ".join(cur_text))
                chunks.append(TextChunk(id=f"C{idx}", heading=cur_head, text=joined))
                idx += 1
                if self.chunk_overlap > 0 and joined:
                    cur_text = [joined[-self.chunk_overlap:]]
                else:
                    cur_text = []
            if head:
                cur_head = head
            cur_text.append(text)
        if cur_text:
            joined = norm_space(" ".join(cur_text))
            if joined:
                chunks.append(TextChunk(id=f"C{idx}", heading=cur_head, text=joined))
        return chunks

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[LinkRef]:
        out: list[LinkRef] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            if not isinstance(a, Tag):
                continue
            u = clean_url(str(a.get("href") or ""), base=base_url)
            if not u or u in seen or not is_probably_html_url(u):
                continue
            seen.add(u)
            txt = norm_space(a.get_text(" ", strip=True) or a.get("title") or a.get("aria-label") or "")
            if not txt:
                path = urlparse(u).path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ")
                txt = path or host_of(u)
            ctx = ""
            parent = a.parent
            if isinstance(parent, Tag):
                ctx = cap(parent.get_text(" ", strip=True), 220)
            out.append(LinkRef(id=f"L{len(out) + 1}", url=u, text=cap(txt, 120), context=ctx))
            if len(out) >= 120:
                break
        return out


# ---------------------------------------------------------------------------
# State objects
# ---------------------------------------------------------------------------

@dataclass
class SourceState:
    id: str
    url: str
    title: str = ""
    snippet: str = ""
    status: str = "queued"  # queued, fetched, rejected, accepted, failed
    host: str = ""
    page: Optional[PageDoc] = None
    assigned_agent_ids: list[str] = field(default_factory=list)
    opened_at_round: Optional[int] = None
    error: str = ""

    def compact(self) -> str:
        base = f"{self.id} {self.status} {self.host or host_of(self.url)} {cap(self.title or self.url, 90)}"
        if self.snippet:
            base += f" :: {cap(self.snippet, 120)}"
        return base


@dataclass
class DigHit:
    chunk_id: str
    heading: str
    score: float
    text: str


@dataclass
class DigReport:
    id: str
    source_id: str
    agent_id: str
    query: str
    best_score: float
    p50_score: float
    p90_score: float
    strong_hits: int
    total_chunks: int
    hits: list[DigHit]
    links: list[LinkRef]
    created_at: str
    status: str = "open"  # open, accepted, rejected

    def compact(self) -> str:
        top = "\n".join(
            f"  {h.chunk_id} {h.score:.3f} {cap(h.heading, 55)} :: {cap(h.text, 260)}"
            for h in self.hits[:5]
        )
        links = " | ".join(f"{l.id} {l.score:.3f} {cap(l.text, 45)}" for l in self.links[:8])
        return (
            f"{self.id} src={self.source_id} q={cap(self.query, 90)} "
            f"best={self.best_score:.3f} p90={self.p90_score:.3f} p50={self.p50_score:.3f} "
            f"strong={self.strong_hits}/{self.total_chunks}\n"
            f"top:\n{top or '  none'}\nlinks: {links or 'none'}"
        )


@dataclass
class AcceptedEvidence:
    id: str
    source_id: str
    dig_id: str
    url: str
    title: str
    paragraph: str
    raw_text: str
    accepted_at: str

    def compact(self) -> str:
        return f"[{self.id}] {cap(self.title, 90)} {self.url}\n{cap(self.paragraph or self.raw_text, 950)}"


@dataclass
class AgentState:
    id: str
    goal: str
    source_id: Optional[str] = None
    status: str = "active"  # active, accepted, stopped, rejected
    depth: int = 0
    created_from: str = "root"
    history: list[str] = field(default_factory=list)
    last_dig_ids: list[str] = field(default_factory=list)
    last_link_ids: dict[str, str] = field(default_factory=dict)  # visible link id -> url
    rounds_alive: int = 0

    def note(self, s: str, max_items: int = 8) -> None:
        self.history.append(cap(s, 260))
        if len(self.history) > max_items:
            self.history = self.history[-max_items:]


@dataclass
class ResearchState:
    question: str
    need: str
    sources: dict[str, SourceState] = field(default_factory=dict)
    agents: dict[str, AgentState] = field(default_factory=dict)
    digs: dict[str, DigReport] = field(default_factory=dict)
    accepted: list[AcceptedEvidence] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    used_queries: list[str] = field(default_factory=list)
    rejected_urls: set[str] = field(default_factory=set)
    trace: list[dict[str, Any]] = field(default_factory=list)
    source_counter: int = 0
    agent_counter: int = 0
    dig_counter: int = 0
    evidence_counter: int = 0
    round: int = 0
    finish_requested: bool = False
    finish_reason: str = ""

    def next_source_id(self) -> str:
        self.source_counter += 1
        return f"S{self.source_counter}"

    def next_agent_id(self) -> str:
        self.agent_counter += 1
        return f"A{self.agent_counter}"

    def next_dig_id(self) -> str:
        self.dig_counter += 1
        return f"D{self.dig_counter}"

    def next_evidence_id(self) -> str:
        self.evidence_counter += 1
        return f"E{self.evidence_counter}"


# ---------------------------------------------------------------------------
# DDG search
# ---------------------------------------------------------------------------

class SearchClient:
    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = float(timeout)

    def search(self, query: str, max_results: int = 8) -> list[dict[str, str]]:
        if DDGS is None:
            raise RuntimeError("Neither ddgs nor duckduckgo_search is installed")
        out: list[dict[str, str]] = []
        with DDGS() as ddgs:  # type: ignore[operator]
            rows = ddgs.text(query, max_results=max_results)
            for row in rows:
                url = clean_url(row.get("href") or row.get("url") or row.get("link") or "")
                if not url or not is_probably_html_url(url):
                    continue
                out.append({
                    "url": url,
                    "title": norm_space(row.get("title") or ""),
                    "snippet": norm_space(row.get("body") or row.get("snippet") or ""),
                })
        return out[:max_results]


# ---------------------------------------------------------------------------
# Researcher config/result
# ---------------------------------------------------------------------------

@dataclass
class ResearcherConfig:
    qwen_url: str = "http://127.0.0.1:8009"
    embedding_model: str = "Octen/Octen-Embedding-0.6B"
    max_agents: int = 8
    max_rounds: int = 14
    ddg_results: int = 8
    agents_per_search: int = 3
    request_timeout: float = 18.0
    max_page_chars: int = 180_000
    chunk_chars: int = 1000
    chunk_overlap: int = 160
    dig_top_k: int = 7
    link_top_k: int = 8
    accept_threshold: float = 0.62
    weak_threshold: float = 0.36
    semantic_dedupe_threshold: float = 0.94
    strong_hit_threshold: float = 0.58
    out_dir: str = "text_research_runs"
    allow_hash_embedding_fallback: bool = False
    qwen_max_new_tokens: int = 340
    final_max_new_tokens: int = 900
    verbose: bool = True


@dataclass
class ResearchResult:
    question: str
    answer: str
    accepted: list[AcceptedEvidence]
    trace_path: str
    answer_path: str
    state_path: str


# ---------------------------------------------------------------------------
# Main researcher
# ---------------------------------------------------------------------------

class TextRouteResearcher:
    def __init__(self, config: ResearcherConfig) -> None:
        self.cfg = config
        self.qwen = QwenBatchClient(config.qwen_url)
        self.emb = EmbeddingService(
            config.embedding_model,
            allow_hash_fallback=config.allow_hash_embedding_fallback,
        )
        self.fetcher = PageFetcher(
            timeout=config.request_timeout,
            max_chars=config.max_page_chars,
            chunk_chars=config.chunk_chars,
            chunk_overlap=config.chunk_overlap,
        )
        self.search_client = SearchClient(timeout=config.request_timeout)
        self._source_url_seen: set[str] = set()
        self._planned_texts: list[tuple[str, np.ndarray]] = []
        self._log_lock = threading.Lock()
        self._completion_thread: Optional[threading.Thread] = None
        self._completion_result_queue: queue.Queue = queue.Queue()
        self._completion_submitted_accepted_count = 0

    # ------------------------------- public -------------------------------

    def run(self, question: str) -> ResearchResult:
        question = norm_space(question)
        st = ResearchState(question=question, need=question)
        root = AgentState(id=st.next_agent_id(), goal=question, source_id=None, created_from="root")
        st.agents[root.id] = root
        self._trace(st, "start", question=question, embedding_model=self.cfg.embedding_model, qwen_url=self.cfg.qwen_url)

        for round_i in range(1, self.cfg.max_rounds + 1):
            st.round = round_i
            self._poll_completion_supervisor(st)
            if st.finish_requested:
                self._trace(st, "done_condition", round=round_i, reason=st.finish_reason)
                break
            self._fill_agents_from_queued_sources(st)
            active_agents = [a for a in st.agents.values() if a.status == "active"]
            if not active_agents:
                if st.accepted:
                    break
                self._fallback_search(st, reason="no_active_agents_no_evidence")
                self._fill_agents_from_queued_sources(st)
                active_agents = [a for a in st.agents.values() if a.status == "active"]
                if not active_agents:
                    break

            self._log(f"round {round_i}: active={len(active_agents)} sources={len(st.sources)} accepted={len(st.accepted)} need={cap(st.need, 120)}")
            prompts = [self._build_agent_prompt(st, a) for a in active_agents]
            actions = self._infer_actions_batch(st, active_agents, prompts)
            self._execute_action_batches(st, actions)
            self._submit_completion_supervisor_if_needed(st)
            self._poll_completion_supervisor(st)

            # If everything stopped but no one found enough, force a better search.
            if not st.finish_requested and self._should_force_search(st):
                self._fallback_search(st, reason="all_branches_stopped_without_fresh_work")

            if st.finish_requested or self._is_done(st):
                self._trace(st, "done_condition", round=round_i, reason=st.finish_reason or "normal_done")
                break

        self._poll_completion_supervisor(st)
        answer = self._final_answer(st)
        paths = self._write_run_outputs(st, answer)
        return ResearchResult(
            question=question,
            answer=answer,
            accepted=st.accepted,
            trace_path=paths["trace"],
            answer_path=paths["answer"],
            state_path=paths["state"],
        )

    # ------------------------------- completion supervisor ----------------

    def _submit_completion_supervisor_if_needed(self, st: ResearchState) -> None:
        if st.finish_requested or not st.accepted:
            return
        if self._completion_thread and self._completion_thread.is_alive():
            return
        if len(st.accepted) <= self._completion_submitted_accepted_count:
            return
        prompt = self._build_completion_supervisor_prompt(st)
        accepted_count = len(st.accepted)
        self._completion_submitted_accepted_count = accepted_count
        self._completion_thread = threading.Thread(
            target=self._completion_supervisor_worker,
            args=(prompt,),
            name="completion_supervisor",
            daemon=True,
        )
        self._completion_thread.start()
        self._trace(st, "completion_supervisor_start", accepted_count=accepted_count)

    def _poll_completion_supervisor(self, st: ResearchState) -> None:
        try:
            result = self._completion_result_queue.get_nowait()
        except queue.Empty:
            return
        if result.get("error"):
            self._trace(st, "completion_supervisor_error", error=str(result.get("error")))
            return
        verdict = result.get("verdict") or {}
        done = bool(verdict.get("done"))
        why = cap(str(verdict.get("why") or ""), 180)
        self._trace(st, "completion_supervisor_verdict", done=done, why=why)
        if done:
            st.finish_requested = True
            st.finish_reason = why or "accepted evidence judged sufficient"
            self._stop_active_agents(st, reason=f"completion supervisor: {st.finish_reason}")

    def _build_completion_supervisor_prompt(self, st: ResearchState) -> str:
        accepted_rows = []
        for e in st.accepted[-10:]:
            accepted_rows.append(
                f"{e.id} {cap(e.title, 90)} {e.url}\n{cap(e.paragraph or e.raw_text, 760)}"
            )
        hints = " | ".join(cap(h, 140) for h in st.hints[-8:]) or "none"
        queries = " | ".join(cap(q, 120) for q in st.used_queries[-10:]) or "none"
        return f"""
QUESTION:
{cap(st.question, 600)}

CURRENT NEED:
{cap(st.need, 700)}

HINTS:
{hints}

QUERY HISTORY:
{queries}

ACCEPTED EVIDENCE COUNT: {len(st.accepted)}
ACCEPTED EVIDENCE:
{chr(10).join(accepted_rows)}

Is this accepted evidence enough to answer the question satisfactorily?
""".strip()

    def _run_completion_supervisor(self, prompt: str) -> dict[str, Any]:
        rows = self.qwen.generate_text_batch(
            [prompt],
            system_prompt=COMPLETION_SUPERVISOR_SYSTEM_PROMPT,
            generation={"max_new_tokens": 90, "temperature": 0.0, "top_p": 1.0, "top_k": -1, "skip_special_tokens": True},
        )
        obj = extract_json_object(rows[0] if rows else "") or {}
        return {
            "done": bool(obj.get("done")) if isinstance(obj, dict) else False,
            "why": cap(str(obj.get("why") or ""), 180) if isinstance(obj, dict) else "",
        }

    def _completion_supervisor_worker(self, prompt: str) -> None:
        try:
            verdict = self._run_completion_supervisor(prompt)
            self._completion_result_queue.put({"verdict": verdict})
        except Exception as exc:
            self._completion_result_queue.put({"error": str(exc)})

    def _stop_active_agents(self, st: ResearchState, *, reason: str) -> None:
        for agent in st.agents.values():
            if agent.status == "active":
                agent.status = "stopped"
                agent.note(reason)
        self._trace(st, "active_agents_stopped", reason=reason)

    # ------------------------------- prompts ------------------------------

    def _build_agent_prompt(self, st: ResearchState, agent: AgentState) -> str:
        source_block = "none"
        visible_links: dict[str, str] = {}
        if agent.source_id and agent.source_id in st.sources:
            src = st.sources[agent.source_id]
            page = src.page
            if page:
                source_block = f"{src.compact()}\n{page.compact_snapshot()}"
                for l in page.links[:12]:
                    visible_links[l.id] = l.url
            else:
                source_block = src.compact()

        last_digs = []
        for did in agent.last_dig_ids[-3:]:
            d = st.digs.get(did)
            if d:
                last_digs.append(d.compact())
                for l in d.links[:10]:
                    visible_links[l.id] = l.url
        agent.last_link_ids = visible_links

        global_hints = " | ".join(f"H{i + 1}:{cap(h, 120)}" for i, h in enumerate(st.hints[-6:])) or "none"
        accepted_short = " | ".join(f"{e.id}:{cap(e.title, 50)}" for e in st.accepted[-8:]) or "none"
        sources_short = "\n".join(s.compact() for s in list(st.sources.values())[-10:]) or "none"
        history = " | ".join(agent.history[-5:]) or "none"
        slots_free = max(0, self.cfg.max_agents - len([a for a in st.agents.values() if a.status == "active"]))

        prompt = f"""
Q: {st.question}
Need: {st.need}
Round: {st.round} Agent: {agent.id} Goal: {agent.goal} Source: {agent.source_id or 'none'} Depth: {agent.depth} FreeSlots: {slots_free}/{self.cfg.max_agents}
Hints: {global_hints}
AcceptedEvidence: {accepted_short}
UsedQueries: {' | '.join(st.used_queries[-6:]) or 'none'}
AllSources:
{sources_short}

CurrentSourceSnapshot:
{source_block}

LastDigs:
{chr(10).join(last_digs) or 'none'}

AgentHistory: {history}

Choose the next tiny actions. If Source is none, usually search. If a page is queued/unfetched, open it. If a snapshot is broad, dig a specific hole. If a dig shows the needed answer, accept by dig id. If a source is weak, reject or search a sharper query. If a page contains multiple plausible holes or links and slots are free, split. Output JSON only.
""".strip()
        return prompt

    def _infer_actions_batch(self, st: ResearchState, agents: list[AgentState], prompts: list[str]) -> dict[str, dict[str, Any]]:
        gen = {
            "max_new_tokens": self.cfg.qwen_max_new_tokens,
            "temperature": 0.0,
            "top_p": 1.0,
            "top_k": -1,
            "repetition_penalty": 1.0,
            "skip_special_tokens": True,
        }
        raw_rows: list[str]
        try:
            raw_rows = self.qwen.generate_text_batch(prompts, system_prompt=TEXT_ROUTE_AGENT_SYSTEM_PROMPT, generation=gen)
        except Exception as exc:
            self._trace(st, "qwen_batch_error", error=str(exc))
            raw_rows = ["" for _ in prompts]

        out: dict[str, dict[str, Any]] = {}
        for agent, prompt, raw in zip(agents, prompts, raw_rows):
            parsed = extract_json_object(raw)
            if not self._valid_action_obj(parsed):
                parsed = self._repair_or_fallback_action(st, agent, prompt, raw)
            parsed = self._sanitize_actions(st, agent, parsed or {})
            out[agent.id] = parsed
            self._trace(st, "agent_action", agent=agent.id, raw=cap(raw, 900), parsed=parsed)
        return out

    def _repair_or_fallback_action(self, st: ResearchState, agent: AgentState, prompt: str, raw: str) -> dict[str, Any]:
        repair_prompt = f"INPUT STATE:\n{prompt}\n\nBROKEN ANSWER:\n{raw}"
        try:
            rows = self.qwen.generate_text_batch(
                [repair_prompt],
                system_prompt=ACTION_REPAIR_SYSTEM_PROMPT,
                generation={"max_new_tokens": 180, "temperature": 0.0, "top_p": 1.0, "top_k": -1, "skip_special_tokens": True},
            )
            obj = extract_json_object(rows[0] if rows else "")
            if self._valid_action_obj(obj):
                return obj or {}
        except Exception as exc:
            self._trace(st, "repair_error", agent=agent.id, error=str(exc))
        return self._fallback_action_for_agent(st, agent)

    def _valid_action_obj(self, obj: Optional[dict[str, Any]]) -> bool:
        if not isinstance(obj, dict):
            return False
        act = obj.get("act", [])
        return isinstance(act, list)

    def _sanitize_actions(self, st: ResearchState, agent: AgentState, obj: dict[str, Any]) -> dict[str, Any]:
        acts = obj.get("act") or []
        if not isinstance(acts, list):
            acts = []
        good: list[dict[str, str]] = []
        allowed = {"search", "open", "dig", "split", "accept", "reject", "stop"}
        for a in acts[:3]:
            if not isinstance(a, dict):
                continue
            t = str(a.get("t") or "").strip().lower()
            if t not in allowed:
                continue
            row: dict[str, str] = {"t": t}
            for k in ("q", "s", "l", "d"):
                if a.get(k) is not None:
                    row[k] = cap(str(a.get(k) or ""), 280)
            # Fill obvious defaults for source-bound actions.
            if t in {"open", "dig", "split", "reject"} and not row.get("s") and not row.get("l"):
                if agent.source_id:
                    row["s"] = agent.source_id
            if t == "dig" and not row.get("q"):
                row["q"] = agent.goal or st.need
            if t == "search" and not row.get("q"):
                row["q"] = st.need or st.question
            good.append(row)
        need = cap(str(obj.get("need") or ""), 260)
        return {"need": need, "act": good}

    def _fallback_action_for_agent(self, st: ResearchState, agent: AgentState) -> dict[str, Any]:
        if not agent.source_id:
            return {"need": "", "act": [{"t": "search", "q": self._search_query_from_state(st, agent)}]}
        src = st.sources.get(agent.source_id)
        if not src:
            return {"need": "", "act": [{"t": "search", "q": self._search_query_from_state(st, agent)}]}
        if src.status == "queued" or not src.page:
            return {"need": "", "act": [{"t": "open", "s": src.id}]}
        last = st.digs.get(agent.last_dig_ids[-1]) if agent.last_dig_ids else None
        if last and last.best_score >= self.cfg.accept_threshold and last.hits:
            return {"need": "", "act": [{"t": "accept", "d": last.id}]}
        if agent.rounds_alive > 3 and last and last.best_score < self.cfg.weak_threshold:
            return {"need": "", "act": [{"t": "reject", "s": src.id}, {"t": "search", "q": self._search_query_from_state(st, agent)}]}
        return {"need": "", "act": [{"t": "dig", "s": src.id, "q": agent.goal or st.need}]}

    # ------------------------------- execution ----------------------------

    def _execute_action_batches(self, st: ResearchState, by_agent: dict[str, dict[str, Any]]) -> None:
        # Phase 0: global need/hint updates.
        for aid, obj in by_agent.items():
            need = norm_space(str(obj.get("need") or ""))
            if need:
                self._add_hint_or_need(st, need)

        # Flatten actions with their agent.
        rows: list[tuple[AgentState, dict[str, str]]] = []
        for aid, obj in by_agent.items():
            agent = st.agents.get(aid)
            if not agent or agent.status != "active":
                continue
            agent.rounds_alive += 1
            acts = obj.get("act") or []
            if not acts:
                acts = self._fallback_action_for_agent(st, agent).get("act", [])
            for a in acts:
                if isinstance(a, dict):
                    rows.append((agent, a))

        # Phase 1: accept/reject/stop are cheap and should update state before more work.
        deferred: list[tuple[AgentState, dict[str, str]]] = []
        for agent, action in rows:
            t = action.get("t")
            if t == "accept":
                self._execute_accept(st, agent, action)
            elif t == "reject":
                self._execute_reject(st, agent, action)
            elif t == "stop":
                agent.status = "stopped"
                agent.note("stopped")
                self._trace(st, "agent_stop", agent=agent.id)
            else:
                deferred.append((agent, action))

        # Phase 2: dedupe and run searches.
        search_actions = [(ag, ac) for ag, ac in deferred if ac.get("t") == "search"]
        other_actions = [(ag, ac) for ag, ac in deferred if ac.get("t") != "search"]
        self._execute_searches(st, search_actions)

        # Assign queued sources produced by searches before other actions if possible.
        self._fill_agents_from_queued_sources(st)

        # Phase 3: open pages and execute splits that need link/source resolution.
        open_actions = [(ag, ac) for ag, ac in other_actions if ac.get("t") == "open"]
        split_actions = [(ag, ac) for ag, ac in other_actions if ac.get("t") == "split"]
        self._execute_opens(st, open_actions)
        self._execute_splits(st, split_actions)

        # Phase 4: digs run after opens so newly fetched pages can be scored.
        dig_actions = [(ag, ac) for ag, ac in other_actions if ac.get("t") == "dig"]
        self._execute_digs(st, dig_actions)

    def _execute_searches(self, st: ResearchState, actions: list[tuple[AgentState, dict[str, str]]]) -> None:
        deduped: list[tuple[AgentState, str]] = []
        for agent, ac in actions:
            q = norm_space(ac.get("q") or self._search_query_from_state(st, agent))
            if not q:
                continue
            if self._text_duplicate(q, [x for x in st.used_queries], threshold=self.cfg.semantic_dedupe_threshold):
                agent.note(f"search skipped duplicate: {q}")
                self._trace(st, "search_duplicate_skip", agent=agent.id, query=q)
                continue
            # Also dedupe among this phase.
            if self._phase_duplicate(q, label="search"):
                self._trace(st, "search_phase_duplicate_skip", agent=agent.id, query=q)
                continue
            deduped.append((agent, q))
            st.used_queries.append(q)

        if not deduped:
            return
        with cf.ThreadPoolExecutor(max_workers=min(6, len(deduped))) as ex:
            futs = {ex.submit(self.search_client.search, q, self.cfg.ddg_results): (agent, q) for agent, q in deduped}
            for fut in cf.as_completed(futs):
                agent, q = futs[fut]
                try:
                    results = fut.result()
                except Exception as exc:
                    agent.note(f"search failed: {q}")
                    self._trace(st, "search_error", agent=agent.id, query=q, error=str(exc))
                    continue
                self._trace(st, "search_results", agent=agent.id, query=q, count=len(results), results=results[:8])
                added = self._add_search_results_as_sources(st, results, agent=agent)
                agent.note(f"search {q} -> {added} sources")

    def _execute_opens(self, st: ResearchState, actions: list[tuple[AgentState, dict[str, str]]]) -> None:
        targets: list[tuple[AgentState, SourceState]] = []
        for agent, ac in actions:
            src = self._source_from_action(st, agent, ac)
            if not src:
                continue
            targets.append((agent, src))
        # Deduplicate by source id.
        seen: set[str] = set()
        uniq: list[tuple[AgentState, SourceState]] = []
        for agent, src in targets:
            if src.id in seen:
                continue
            seen.add(src.id)
            uniq.append((agent, src))
        if not uniq:
            return
        with cf.ThreadPoolExecutor(max_workers=min(8, len(uniq))) as ex:
            futs = {ex.submit(self._fetch_source, src): (agent, src) for agent, src in uniq}
            for fut in cf.as_completed(futs):
                agent, src = futs[fut]
                try:
                    fut.result()
                except Exception as exc:
                    src.status = "failed"
                    src.error = str(exc)
                if src.page and not src.page.error:
                    src.status = "fetched"
                    src.opened_at_round = st.round
                    src.title = src.page.title or src.title
                    agent.note(f"opened {src.id}: {cap(src.title, 100)}")
                    self._trace(st, "open_done", agent=agent.id, source=src.id, snapshot=src.page.compact_snapshot())
                else:
                    src.status = "failed"
                    src.error = src.error or (src.page.error if src.page else "no_page")
                    agent.note(f"open failed {src.id}: {src.error}")
                    self._trace(st, "open_failed", agent=agent.id, source=src.id, error=src.error)

    def _execute_digs(self, st: ResearchState, actions: list[tuple[AgentState, dict[str, str]]]) -> None:
        targets: list[tuple[AgentState, SourceState, str]] = []
        for agent, ac in actions:
            src = self._source_from_action(st, agent, ac)
            if not src:
                continue
            q = norm_space(ac.get("q") or agent.goal or st.need)
            if not q:
                q = st.need
            if not src.page or src.status == "queued":
                self._fetch_source(src)
                if src.page and not src.page.error:
                    src.status = "fetched"
                    src.title = src.page.title or src.title
            if src.page and not src.page.error:
                targets.append((agent, src, q))
            else:
                agent.note(f"dig skipped no page {src.id}")
        # Dedupe crazy-similar digs on same source+goal.
        uniq: list[tuple[AgentState, SourceState, str]] = []
        local_keys: list[str] = []
        for agent, src, q in targets:
            key_text = f"{src.id} {q}"
            if self._text_duplicate(key_text, local_keys, threshold=self.cfg.semantic_dedupe_threshold):
                self._trace(st, "dig_duplicate_skip", agent=agent.id, source=src.id, q=q)
                continue
            local_keys.append(key_text)
            uniq.append((agent, src, q))
        if not uniq:
            return
        with cf.ThreadPoolExecutor(max_workers=min(8, len(uniq))) as ex:
            futs = {ex.submit(self._dig_source, st, agent, src, q): (agent, src, q) for agent, src, q in uniq}
            for fut in cf.as_completed(futs):
                agent, src, q = futs[fut]
                try:
                    report = fut.result()
                except Exception as exc:
                    agent.note(f"dig failed {src.id}")
                    self._trace(st, "dig_error", agent=agent.id, source=src.id, q=q, error=str(exc))
                    continue
                st.digs[report.id] = report
                agent.last_dig_ids.append(report.id)
                agent.note(f"dig {report.id} best={report.best_score:.3f} strong={report.strong_hits}/{report.total_chunks}")
                self._trace(st, "dig_done", report=json_safe(report))

    def _execute_splits(self, st: ResearchState, actions: list[tuple[AgentState, dict[str, str]]]) -> None:
        for agent, ac in actions:
            if len([a for a in st.agents.values() if a.status == "active"]) >= self.cfg.max_agents:
                agent.note("split skipped cap full")
                continue
            q = norm_space(ac.get("q") or agent.goal or st.need)
            if not q:
                q = st.need
            src: Optional[SourceState] = None
            if ac.get("l"):
                link_url = agent.last_link_ids.get(str(ac.get("l")))
                if link_url:
                    src = self._create_or_get_source(st, link_url, title=f"link {ac.get('l')}", snippet=q)
            if src is None:
                src = self._source_from_action(st, agent, ac)
            if not src:
                continue
            if self._phase_duplicate(f"split {src.url} {q}", label="split"):
                self._trace(st, "split_duplicate_skip", agent=agent.id, source=src.id, q=q)
                continue
            aid = st.next_agent_id()
            child = AgentState(id=aid, goal=q, source_id=src.id, depth=agent.depth + 1, created_from=f"split:{agent.id}")
            src.assigned_agent_ids.append(aid)
            st.agents[aid] = child
            agent.note(f"split -> {aid} on {src.id}")
            self._trace(st, "split", parent=agent.id, child=aid, source=src.id, goal=q)

    def _execute_accept(self, st: ResearchState, agent: AgentState, ac: dict[str, str]) -> None:
        did = ac.get("d") or (agent.last_dig_ids[-1] if agent.last_dig_ids else "")
        dig = st.digs.get(did)
        if not dig:
            agent.note("accept skipped no dig")
            return
        if dig.status == "accepted":
            agent.status = "accepted"
            return
        src = st.sources.get(dig.source_id)
        if not src or not src.page:
            agent.note("accept skipped no source page")
            return
        raw = self._accepted_raw_text_from_dig(src.page, dig)
        paragraph = self._synthesize_accept_paragraph(st, src, dig, raw)
        eid = st.next_evidence_id()
        evidence = AcceptedEvidence(
            id=eid,
            source_id=src.id,
            dig_id=dig.id,
            url=src.page.final_url or src.url,
            title=src.page.title or src.title,
            paragraph=paragraph,
            raw_text=raw,
            accepted_at=now_iso(),
        )
        st.accepted.append(evidence)
        dig.status = "accepted"
        src.status = "accepted"
        agent.status = "accepted"
        agent.note(f"accepted {dig.id} -> {eid}")
        self._trace(st, "accept", agent=agent.id, evidence=json_safe(evidence))

    def _execute_reject(self, st: ResearchState, agent: AgentState, ac: dict[str, str]) -> None:
        src = self._source_from_action(st, agent, ac)
        if src:
            src.status = "rejected"
            st.rejected_urls.add(src.url)
            agent.note(f"rejected {src.id}")
            self._trace(st, "reject_source", agent=agent.id, source=src.id)
        agent.status = "rejected"

    # ------------------------------- core operations ----------------------

    def _fetch_source(self, src: SourceState) -> None:
        if src.page and not src.page.error:
            return
        page = self.fetcher.fetch(src.url)
        src.page = page
        src.host = src.host or host_of(page.final_url or src.url)
        if page.title:
            src.title = page.title
        if page.error:
            src.error = page.error

    def _dig_source(self, st: ResearchState, agent: AgentState, src: SourceState, q: str) -> DigReport:
        assert src.page is not None
        page = src.page
        did = st.next_dig_id()
        if not page.chunks:
            return DigReport(id=did, source_id=src.id, agent_id=agent.id, query=q, best_score=0.0, p50_score=0.0, p90_score=0.0, strong_hits=0, total_chunks=0, hits=[], links=[], created_at=now_iso())

        query_text = " | ".join(x for x in [st.question, st.need, agent.goal, q, " ".join(st.hints[-3:])] if x)
        qv = self.emb.encode(query_text)
        chunk_texts = [f"{c.heading}\n{c.text}" for c in page.chunks]
        chunk_vecs = self.emb.encode(chunk_texts)
        scores = np.dot(chunk_vecs, np.asarray(qv, dtype=np.float32).reshape(-1))
        order = list(np.argsort(-scores))
        hits: list[DigHit] = []
        for rank, idx in enumerate(order[: self.cfg.dig_top_k], start=1):
            c = page.chunks[int(idx)]
            sc = float(scores[int(idx)])
            c.score = sc
            c.rank = rank
            hits.append(DigHit(chunk_id=c.id, heading=c.heading, score=sc, text=cap(c.text, 720)))
        link_scores = self._score_links(query_text, page.links)
        p50 = float(np.percentile(scores, 50)) if len(scores) else 0.0
        p90 = float(np.percentile(scores, 90)) if len(scores) else 0.0
        best = float(np.max(scores)) if len(scores) else 0.0
        strong = int(np.sum(scores >= self.cfg.strong_hit_threshold)) if len(scores) else 0
        return DigReport(
            id=did,
            source_id=src.id,
            agent_id=agent.id,
            query=q,
            best_score=best,
            p50_score=p50,
            p90_score=p90,
            strong_hits=strong,
            total_chunks=len(page.chunks),
            hits=hits,
            links=link_scores[: self.cfg.link_top_k],
            created_at=now_iso(),
        )

    def _score_links(self, query_text: str, links: list[LinkRef]) -> list[LinkRef]:
        if not links:
            return []
        qv = self.emb.encode(query_text)
        texts = [f"{l.text} {l.context} {urlparse(l.url).path.replace('-', ' ').replace('_', ' ')}" for l in links]
        vecs = self.emb.encode(texts)
        scores = np.dot(vecs, np.asarray(qv, dtype=np.float32).reshape(-1))
        scored: list[LinkRef] = []
        seen: set[str] = set()
        for l, sc in sorted(zip(links, scores), key=lambda x: float(x[1]), reverse=True):
            if l.url in seen:
                continue
            seen.add(l.url)
            scored.append(LinkRef(id=l.id, url=l.url, text=l.text, context=l.context, score=float(sc)))
        return scored

    def _accepted_raw_text_from_dig(self, page: PageDoc, dig: DigReport) -> str:
        ids = {h.chunk_id for h in dig.hits[:5] if h.score >= max(self.cfg.weak_threshold, dig.best_score - 0.12)}
        parts: list[str] = []
        for c in page.chunks:
            if c.id in ids:
                prefix = f"[{c.heading}] " if c.heading else ""
                parts.append(prefix + c.text)
        if not parts:
            parts = [h.text for h in dig.hits[:3]]
        raw = "\n\n".join(parts)
        return cap(raw, 6000)

    def _synthesize_accept_paragraph(self, st: ResearchState, src: SourceState, dig: DigReport, raw: str) -> str:
        # If the Qwen endpoint is unavailable, the raw extracted text is still enough for final synthesis.
        prompt = f"QUESTION: {st.question}\nNEED: {st.need}\nSOURCE: {src.title} {src.url}\nDIG: {dig.query}\nPAGE TEXT:\n{raw}"
        try:
            rows = self.qwen.generate_text_batch(
                [prompt],
                system_prompt=ACCEPT_NOTE_SYSTEM_PROMPT,
                generation={"max_new_tokens": 260, "temperature": 0.0, "top_p": 1.0, "top_k": -1, "skip_special_tokens": True},
            )
            obj = extract_json_object(rows[0] if rows else "")
            p = norm_space(obj.get("p") if isinstance(obj, dict) else "")
            if p:
                return p
        except Exception as exc:
            self._trace(st, "accept_note_error", source=src.id, dig=dig.id, error=str(exc))
        return cap(raw, 1500)

    # ------------------------------- state helpers ------------------------

    def _add_search_results_as_sources(self, st: ResearchState, results: list[dict[str, str]], *, agent: AgentState) -> int:
        added = 0
        for row in results:
            url = clean_url(row.get("url") or "")
            if not url or url in self._source_url_seen or url in st.rejected_urls:
                continue
            src = self._create_or_get_source(st, url, title=row.get("title") or "", snippet=row.get("snippet") or "")
            if not src:
                continue
            added += 1
            if len([a for a in st.agents.values() if a.status == "active"]) < self.cfg.max_agents and added <= self.cfg.agents_per_search:
                aid = st.next_agent_id() if agent.source_id else agent.id
                if aid == agent.id and agent.source_id is None:
                    child = agent
                    child.source_id = src.id
                    child.goal = agent.goal or st.need
                    child.created_from = f"search:{agent.id}"
                else:
                    child = AgentState(id=aid, goal=st.need, source_id=src.id, created_from=f"search:{agent.id}")
                    st.agents[aid] = child
                src.assigned_agent_ids.append(child.id)
        return added

    def _create_or_get_source(self, st: ResearchState, url: str, *, title: str = "", snippet: str = "") -> Optional[SourceState]:
        u = clean_url(url)
        if not u or not is_probably_html_url(u) or u in st.rejected_urls:
            return None
        for src in st.sources.values():
            if src.url == u:
                if title and not src.title:
                    src.title = title
                if snippet and not src.snippet:
                    src.snippet = snippet
                return src
        sid = st.next_source_id()
        src = SourceState(id=sid, url=u, title=cap(title, 160), snippet=cap(snippet, 240), host=host_of(u))
        st.sources[sid] = src
        self._source_url_seen.add(u)
        self._trace(st, "source_add", source=json_safe(src))
        return src

    def _fill_agents_from_queued_sources(self, st: ResearchState) -> None:
        active_count = len([a for a in st.agents.values() if a.status == "active"])
        if active_count >= self.cfg.max_agents:
            return
        assigned_sources = {a.source_id for a in st.agents.values() if a.source_id and a.status == "active"}
        for src in st.sources.values():
            if active_count >= self.cfg.max_agents:
                break
            if src.status not in {"queued", "fetched"}:
                continue
            if src.id in assigned_sources:
                continue
            aid = st.next_agent_id()
            ag = AgentState(id=aid, goal=st.need, source_id=src.id, created_from="queued_source")
            st.agents[aid] = ag
            src.assigned_agent_ids.append(aid)
            assigned_sources.add(src.id)
            active_count += 1
            self._trace(st, "agent_from_queue", agent=aid, source=src.id)

    def _source_from_action(self, st: ResearchState, agent: AgentState, ac: dict[str, str]) -> Optional[SourceState]:
        sid = ac.get("s") or agent.source_id or ""
        if sid and sid in st.sources:
            return st.sources[sid]
        lid = ac.get("l") or ""
        if lid and lid in agent.last_link_ids:
            return self._create_or_get_source(st, agent.last_link_ids[lid], title=f"link {lid}", snippet=agent.goal)
        return None

    def _add_hint_or_need(self, st: ResearchState, text: str) -> None:
        text = cap(text, 260)
        if not text:
            return
        candidates = [st.need] + st.hints
        if self._text_duplicate(text, candidates, threshold=self.cfg.semantic_dedupe_threshold):
            return
        st.hints.append(text)
        # Keep a single refined need field as the compact global memory. If the hint is more concrete
        # than the old need, append it in a very short form rather than replacing the question.
        if len(text) > 12 and text.lower() not in st.need.lower():
            st.need = cap(f"{st.need}; look specifically for {text}", 360)
        self._trace(st, "hint_add", hint=text, need=st.need)

    def _search_query_from_state(self, st: ResearchState, agent: AgentState) -> str:
        # Prefer concrete global need; strip too much punctuation.
        base = agent.goal or st.need or st.question
        if len(base.split()) > 18:
            base = " ".join(base.split()[:18])
        return norm_space(base)

    def _fallback_search(self, st: ResearchState, *, reason: str) -> None:
        q = self._search_query_from_state(st, AgentState(id="fallback", goal=st.need))
        if self._text_duplicate(q, st.used_queries, threshold=self.cfg.semantic_dedupe_threshold):
            q = f"{st.question} evidence source facts"
        st.used_queries.append(q)
        self._trace(st, "forced_search", query=q, reason=reason)
        try:
            rows = self.search_client.search(q, self.cfg.ddg_results)
            self._add_search_results_as_sources(st, rows, agent=next(iter(st.agents.values())))
        except Exception as exc:
            self._trace(st, "forced_search_error", query=q, error=str(exc))

    def _should_force_search(self, st: ResearchState) -> bool:
        active = [a for a in st.agents.values() if a.status == "active"]
        if active:
            return False
        if st.accepted:
            return False
        queued = [s for s in st.sources.values() if s.status in {"queued", "fetched"}]
        return not queued and len(st.used_queries) < max(2, self.cfg.max_rounds // 2)

    def _is_done(self, st: ResearchState) -> bool:
        active = [a for a in st.agents.values() if a.status == "active"]
        if active:
            return False
        queued = [s for s in st.sources.values() if s.status in {"queued", "fetched"} and not s.assigned_agent_ids]
        if queued:
            return False
        return bool(st.accepted)

    # ------------------------------- semantic dedupe ----------------------

    def _text_duplicate(self, text: str, existing: Iterable[str], *, threshold: float) -> bool:
        rows = [norm_space(x) for x in existing if norm_space(x)]
        text = norm_space(text)
        if not text or not rows:
            return False
        try:
            v = self.emb.encode(text)
            embs = self.emb.encode(rows)
            sims = np.dot(embs, np.asarray(v, dtype=np.float32).reshape(-1))
            return bool(np.max(sims) >= threshold)
        except Exception:
            low = text.lower()
            return any(low == r.lower() for r in rows)

    def _phase_duplicate(self, text: str, *, label: str) -> bool:
        text = norm_space(text)
        if not text:
            return False
        try:
            v = self.emb.encode(text)
            for old_label, old_v in self._planned_texts:
                if old_label != label:
                    continue
                if float(np.dot(old_v, v)) >= self.cfg.semantic_dedupe_threshold:
                    return True
            self._planned_texts.append((label, np.asarray(v, dtype=np.float32)))
            if len(self._planned_texts) > 200:
                self._planned_texts = self._planned_texts[-120:]
            return False
        except Exception:
            return False

    # ------------------------------- final answer/output ------------------

    def _final_answer(self, st: ResearchState) -> str:
        if not st.accepted:
            return "I could not gather accepted evidence before the run stopped. Check the trace for failed searches and fetches."
        context = "\n\n".join(e.compact() for e in st.accepted[:12])
        prompt = f"QUESTION:\n{st.question}\n\nACCEPTED EVIDENCE:\n{context}\n\nWrite the answer now."
        try:
            rows = self.qwen.generate_text_batch(
                [prompt],
                system_prompt=FINAL_SYNTHESIS_SYSTEM_PROMPT,
                generation={"max_new_tokens": self.cfg.final_max_new_tokens, "temperature": 0.0, "top_p": 1.0, "top_k": -1, "skip_special_tokens": True},
            )
            ans = norm_space(rows[0] if rows else "")
            if ans:
                return ans
        except Exception as exc:
            self._trace(st, "final_answer_error", error=str(exc))
        # Fallback: still produce a grounded, usable output.
        parts = [f"Evidence-backed notes for: {st.question}"]
        for e in st.accepted:
            parts.append(f"{e.id}. {e.paragraph or cap(e.raw_text, 700)} Source: {e.url}")
        return "\n\n".join(parts)

    def _write_run_outputs(self, st: ResearchState, answer: str) -> dict[str, str]:
        run_id = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + "_" + hashlib.sha1(st.question.encode("utf-8")).hexdigest()[:8]
        out_dir = Path(self.cfg.out_dir) / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        trace_path = out_dir / "trace.json"
        state_path = out_dir / "state.json"
        answer_path = out_dir / "answer.md"
        trace_path.write_text(json.dumps(json_safe(st.trace), ensure_ascii=False, indent=2), encoding="utf-8")
        state_obj = {
            "question": st.question,
            "need": st.need,
            "finish_requested": st.finish_requested,
            "finish_reason": st.finish_reason,
            "hints": st.hints,
            "used_queries": st.used_queries,
            "sources": [json_safe(s) for s in st.sources.values()],
            "digs": [json_safe(d) for d in st.digs.values()],
            "accepted": [json_safe(e) for e in st.accepted],
        }
        state_path.write_text(json.dumps(state_obj, ensure_ascii=False, indent=2), encoding="utf-8")
        src_lines = [f"- [{e.id}] {e.title}: {e.url}" for e in st.accepted]
        answer_path.write_text(f"# Answer\n\n{answer}\n\n## Accepted sources\n" + "\n".join(src_lines) + "\n", encoding="utf-8")
        return {"trace": str(trace_path), "state": str(state_path), "answer": str(answer_path)}

    def _trace(self, st: ResearchState, kind: str, **kw: Any) -> None:
        row = {"t": now_iso(), "round": st.round, "kind": kind}
        row.update(kw)
        st.trace.append(json_safe(row))

    def _log(self, msg: str) -> None:
        if not self.cfg.verbose:
            return
        with self._log_lock:
            print(f"[TextRouteResearcher] {msg}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parallel Qwen + Octen embedding text researcher")
    p.add_argument("question", nargs="?", help="research question")
    p.add_argument("--qwen-url", default=os.getenv("QWEN_VLLM_SERVER_URL", "http://127.0.0.1:8009"))
    p.add_argument("--embedding-model", default=os.getenv("TEXT_RESEARCH_EMBED_MODEL", "Octen/Octen-Embedding-0.6B"))
    p.add_argument("--max-agents", type=int, default=8)
    p.add_argument("--max-rounds", type=int, default=14)
    p.add_argument("--out-dir", default="text_research_runs")
    p.add_argument("--allow-hash-fallback", action="store_true", help="allow deterministic hash embeddings only for smoke tests")
    p.add_argument("--quiet", action="store_true")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    if not args.question:
        raise SystemExit("Provide a question, e.g. python text_researcher.py 'What happened in ...?' ")
    cfg = ResearcherConfig(
        qwen_url=args.qwen_url,
        embedding_model=args.embedding_model,
        max_agents=args.max_agents,
        max_rounds=args.max_rounds,
        out_dir=args.out_dir,
        allow_hash_embedding_fallback=args.allow_hash_fallback,
        verbose=not args.quiet,
    )
    researcher = TextRouteResearcher(cfg)
    result = researcher.run(args.question)
    print(result.answer)
    print(f"\ntrace: {result.trace_path}")
    print(f"answer: {result.answer_path}")
    print(f"state: {result.state_path}")


if __name__ == "__main__":
    main()
