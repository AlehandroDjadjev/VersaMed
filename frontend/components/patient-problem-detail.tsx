"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError, fetchMedicalProblem, type MedicalProblem } from "@/lib/auth-client";

export function PatientProblemDetail({ problemId }: { problemId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading, user } = useAuth();
  const [problem, setProblem] = useState<MedicalProblem | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const cameFromSync = searchParams.get("from") === "sync";

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?next=/patient/problems/${problemId}`);
      return;
    }

    if (!isLoading && user && user.role !== "patient") {
      router.replace("/account");
    }
  }, [isAuthenticated, isLoading, problemId, router, user]);

  useEffect(() => {
    if (!user || user.role !== "patient") {
      return;
    }

    let isCancelled = false;

    async function loadProblem() {
      setIsFetching(true);
      setPageError(null);

      try {
        const nextProblem = await fetchMedicalProblem(problemId);
        if (!isCancelled) {
          setProblem(nextProblem);
        }
      } catch (error) {
        if (!isCancelled) {
          setPageError(
            error instanceof ApiError
              ? error.message
              : "We could not load this problem right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsFetching(false);
        }
      }
    }

    void loadProblem();

    return () => {
      isCancelled = true;
    };
  }, [problemId, user]);

  if (isLoading || !user || user.role !== "patient") {
    return (
      <main className="mx-auto flex w-full max-w-5xl flex-1 px-5 py-12 sm:px-8">
        <section className="glass-panel w-full animate-pulse p-10">
          <div className="h-5 w-36 rounded-full bg-teal-100" />
          <div className="mt-6 h-16 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-10 h-44 rounded-[28px] bg-white/70" />
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="glass-panel p-8 sm:p-10">
        <span className="chip">
          {cameFromSync ? "New problem found" : "Tracked problem"}
        </span>
        <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
          {isFetching ? "Loading problem" : problem?.title ?? "Problem not found"}
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
          {cameFromSync
            ? "The HIS sync found a new diagnosis source and the analysis pipeline grouped it into this tracked problem."
            : "This is one of the long-term medical problems built from your saved diagnosis history."}
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/patient/records" className="primary-button px-5 py-3">
            Back to records dashboard
          </Link>
          <Link href="/account" className="secondary-button px-5 py-3">
            Account dashboard
          </Link>
        </div>
      </section>

      {pageError ? <p className="error-banner">{pageError}</p> : null}

      {!pageError && !isFetching && problem ? (
        <section className="grid gap-6 lg:grid-cols-[1fr_0.72fr]">
          <article className="glass-panel p-8">
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Summary
            </p>
            <p className="mt-5 text-base leading-8 text-slate-700">
              {problem.summary || "No summary has been saved for this problem yet."}
            </p>
          </article>

          <aside className="glass-panel p-8">
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Context
            </p>
            <div className="mt-5 space-y-3 text-sm text-slate-600">
              <Detail label="Body area" value={problem.body_area || "Not specified"} />
              <Detail label="Created" value={new Date(problem.created_at).toLocaleDateString()} />
              <Detail label="Updated" value={new Date(problem.updated_at).toLocaleDateString()} />
            </div>

            {problem.keywords.length ? (
              <div className="mt-7 flex flex-wrap gap-2">
                {problem.keywords.map((keyword) => (
                  <span
                    key={keyword}
                    className="rounded-full border border-teal-100 bg-white/72 px-3 py-1 text-xs font-medium text-teal-800"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            ) : null}
          </aside>
        </section>
      ) : null}
    </main>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span>{label}</span>
      <span className="text-right font-medium text-slate-900">{value}</span>
    </div>
  );
}
