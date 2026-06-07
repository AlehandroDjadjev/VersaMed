import logging
import time

from django.conf import settings

from AgentResearch.text_researcher import ResearcherConfig, TextRouteResearcher

logger = logging.getLogger(__name__)


def run_medical_research(query):
    started = time.perf_counter()
    logger.warning("medical_research.start query=%s", query)
    config = ResearcherConfig(
        qwen_url=settings.TEXT_RESEARCH_QWEN_URL,
        embedding_model=settings.TEXT_RESEARCH_EMBED_MODEL,
        max_agents=settings.TEXT_RESEARCH_MAX_AGENTS,
        max_rounds=settings.TEXT_RESEARCH_MAX_ROUNDS,
        out_dir=settings.TEXT_RESEARCH_OUT_DIR,
        allow_hash_embedding_fallback=settings.TEXT_RESEARCH_ALLOW_HASH_FALLBACK,
        verbose=False,
    )
    result = TextRouteResearcher(config).run(query)
    logger.warning(
        "medical_research.done accepted=%s elapsed_ms=%d",
        len(result.accepted),
        int((time.perf_counter() - started) * 1000),
    )

    return {
        "query": query,
        "answer": result.answer,
        "accepted": [
            {
                "id": item.id,
                "title": item.title,
                "url": item.url,
                "paragraph": item.paragraph,
            }
            for item in result.accepted
        ],
        "trace_path": result.trace_path,
        "answer_path": result.answer_path,
        "state_path": result.state_path,
    }
