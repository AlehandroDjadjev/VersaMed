"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import type { SyncEnvelope } from "@/lib/auth-client";

const STORAGE_KEY = "latest_patient_sync_result";

export function PatientSyncResults() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();
  const [syncResult, setSyncResult] = useState<SyncEnvelope | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?next=/patient/sync-results");
      return;
    }

    if (!isLoading && user && user.role !== "patient") {
      router.replace("/account");
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const parsed = JSON.parse(raw) as SyncEnvelope;
      setSyncResult(parsed);
    } catch {
      setSyncResult(null);
    }
  }, [isAuthenticated, isLoading, router, user]);

  const diagnosisCount = syncResult?.analyzed_diagnoses.length ?? 0;
  const errorCount = syncResult?.analysis_errors.length ?? 0;

  const newestDiagnosis = useMemo(() => {
    if (!syncResult?.analyzed_diagnoses.length) {
      return null;
    }
    return syncResult.analyzed_diagnoses[0];
  }, [syncResult]);
  const diagnosisToShow = newestDiagnosis ?? syncResult?.latest_diagnosis ?? null;

  if (isLoading || !user || user.role !== "patient") {
    return (
      <main className="mx-auto flex w-full max-w-6xl flex-1 px-5 py-12 sm:px-8">
        <section className="glass-panel w-full animate-pulse p-10">
          <div className="h-5 w-44 rounded-full bg-teal-100" />
          <div className="mt-6 h-16 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-10 h-56 rounded-[28px] bg-white/70" />
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="glass-panel p-8 sm:p-10">
        <span className="chip">Sync results</span>
        <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
          HIS sync diagnosis output
        </h1>
        <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
          This page shows what the diagnosis pipeline produced after your last sync.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/patient/records" className="primary-button px-5 py-3">
            Back to patient records
          </Link>
          <Link href="/account" className="secondary-button px-5 py-3">
            Account dashboard
          </Link>
        </div>
      </section>

      {!syncResult ? (
        <section className="glass-panel p-8">
          <p className="text-sm text-slate-700">
            No sync result is available in this browser session yet. Run sync again from
            patient records.
          </p>
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <CardStat label="New analyzed diagnoses" value={String(diagnosisCount)} />
            <CardStat label="Analysis errors" value={String(errorCount)} />
            <CardStat
              label="New hospitalizations processed"
              value={String(syncResult.new_records.hospitalizations)}
            />
          </section>

          {diagnosisToShow ? (
            <section className="glass-panel p-8 sm:p-10">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                {newestDiagnosis ? "Latest diagnosis from this sync" : "Latest existing diagnosis"}
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
                {diagnosisToShow.diagnosis.title}
              </h2>
              <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-500">
                Type: {diagnosisToShow.diagnosis.kind}
              </p>
              <p className="mt-4 text-sm leading-7 text-slate-700">
                {diagnosisToShow.diagnosis.summary || "No summary generated."}
              </p>
              <p className="mt-4 text-sm leading-7 text-slate-700">
                {diagnosisToShow.diagnosis.description || "No detailed description generated."}
              </p>

              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <article className="rounded-[20px] border border-white/60 bg-white/72 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Body areas
                  </p>
                  <p className="mt-2 text-sm text-slate-800">
                    {diagnosisToShow.diagnosis.body_areas.length
                      ? diagnosisToShow.diagnosis.body_areas.join(", ")
                      : "None"}
                  </p>
                </article>
                <article className="rounded-[20px] border border-white/60 bg-white/72 p-4">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Keywords
                  </p>
                  <p className="mt-2 text-sm text-slate-800">
                    {diagnosisToShow.diagnosis.keywords.length
                      ? diagnosisToShow.diagnosis.keywords.join(", ")
                      : "None"}
                  </p>
                </article>
              </div>

              {diagnosisToShow.diagnosis.extracted_findings.length ? (
                <div className="mt-6">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Extracted findings
                  </p>
                  <div className="mt-3 space-y-3">
                    {diagnosisToShow.diagnosis.extracted_findings.map((finding, index) => (
                      <article
                        key={`finding-${index}`}
                        className="rounded-[20px] border border-white/60 bg-white/72 p-4"
                      >
                        <pre className="whitespace-pre-wrap wrap-break-word text-xs leading-6 text-slate-800">
                          {JSON.stringify(finding, null, 2)}
                        </pre>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="mt-6">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                  Raw diagnosis text
                </p>
                <article className="mt-3 rounded-[20px] border border-white/60 bg-white/72 p-4">
                  <pre className="whitespace-pre-wrap wrap-break-word text-xs leading-6 text-slate-800">
                    {diagnosisToShow.diagnosis.raw_text || "No raw text available."}
                  </pre>
                </article>
              </div>

              <div className="mt-6">
                <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                  Raw diagnosis JSON
                </p>
                <article className="mt-3 rounded-[20px] border border-white/60 bg-white/72 p-4">
                  <pre className="whitespace-pre-wrap wrap-break-word text-xs leading-6 text-slate-800">
                    {JSON.stringify(diagnosisToShow.diagnosis.raw_json ?? {}, null, 2)}
                  </pre>
                </article>
              </div>

              {diagnosisToShow.problem_links.length ? (
                <div className="mt-6">
                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
                    Linked problems
                  </p>
                  <div className="mt-3 space-y-3">
                    {diagnosisToShow.problem_links.map((link) => (
                      <article
                        key={link.id}
                        className="rounded-[20px] border border-white/60 bg-white/72 p-4"
                      >
                        <p className="font-medium text-slate-900">{link.problem.title}</p>
                        <p className="mt-1 text-sm text-slate-600">
                          Strength: {link.strength}
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {link.reason || "No reason provided."}
                        </p>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          {syncResult.analysis_errors.length ? (
            <section className="glass-panel p-8">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Analysis errors
              </p>
              <div className="mt-4 space-y-3">
                {syncResult.analysis_errors.map((item) => (
                  <article
                    key={`${item.source_id}-${item.message}`}
                    className="rounded-[20px] border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-900"
                  >
                    <p className="font-semibold">Source: {item.source_id}</p>
                    <p className="mt-1">{item.message}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}

function CardStat({ label, value }: { label: string; value: string }) {
  return (
    <article className="glass-panel p-6">
      <p className="text-xs uppercase tracking-[0.28em] text-slate-500">{label}</p>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">{value}</p>
    </article>
  );
}
