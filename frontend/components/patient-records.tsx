"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type MouseEvent,
} from "react";

import { useAuth } from "@/components/auth-provider";
import {
  ApiError,
  fetchPatientDashboard,
  syncPatientFromHisApi,
  type PatientDashboardData,
} from "@/lib/auth-client";

export function PatientRecords() {
  const router = useRouter();
  const { isAuthenticated, isLoading, refreshUser, user } = useAuth();
  const [dashboard, setDashboard] = useState<PatientDashboardData | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?next=/patient/records");
      return;
    }

    if (!isLoading && user && user.role !== "patient") {
      router.replace("/account");
    }
  }, [isAuthenticated, isLoading, router, user]);

  useEffect(() => {
    if (!user || user.role !== "patient") {
      return;
    }

    let isCancelled = false;

    async function loadDashboard() {
      setIsFetching(true);
      setPageError(null);

      try {
        const nextDashboard = await fetchPatientDashboard();
        if (!isCancelled) {
          setDashboard(nextDashboard);
        }
      } catch (error) {
        if (!isCancelled) {
          setPageError(
            error instanceof ApiError
              ? error.message
              : "We could not load your patient records right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsFetching(false);
        }
      }
    }

    void loadDashboard();

    return () => {
      isCancelled = true;
    };
  }, [user]);

  async function handleSync(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault();

    if (!user?.patient_profile?.egn) {
      setPageError("This patient account does not have an EGN to sync with the HIS API.");
      return;
    }

    setIsSyncing(true);
    setPageError(null);

    try {
      const syncResult = await syncPatientFromHisApi(user.patient_profile.egn);
      await refreshUser();
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(
          "latest_patient_sync_result",
          JSON.stringify(syncResult),
        );
      }
      router.push("/patient/sync-results");
    } catch (error) {
      setPageError(
        error instanceof ApiError
          ? error.message
          : "We could not sync the HIS data right now.",
      );
    } finally {
      setIsSyncing(false);
    }
  }

  if (isLoading || !user || user.role !== "patient") {
    return (
      <main className="mx-auto flex w-full max-w-6xl flex-1 px-5 py-12 sm:px-8">
        <section className="glass-panel w-full animate-pulse p-10">
          <div className="h-5 w-28 rounded-full bg-teal-100" />
          <div className="mt-6 h-16 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-10 h-64 rounded-[28px] bg-white/70" />
        </section>
      </main>
    );
  }

  const immunizations = dashboard?.database.immunizations ?? [];
  const hospitalizations = dashboard?.database.hospitalizations ?? [];
  const patient = dashboard?.patient;
  const apiStatus = dashboard?.mock_hospital_api;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="grid gap-6 lg:grid-cols-[1.08fr_0.92fr]">
        <div className="glass-panel p-8 sm:p-10">
          <span className="chip">Patient records</span>
          <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
            All your synced medical data in one place.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
            This page organizes the patient information currently available from
            the HIS-backed data flow, including identity details, immunizations,
            hospitalizations, and epicrisis notes.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleSync}
              className="primary-button px-5 py-3 disabled:cursor-not-allowed disabled:opacity-70"
              disabled={isSyncing}
            >
              {isSyncing ? "Syncing HIS data..." : "Sync from HIS API"}
            </button>
            <Link href="/account" className="secondary-button px-5 py-3">
              Back to account
            </Link>
          </div>
        </div>

        <aside className="glass-panel p-8">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Sync status
          </p>
          <div className="mt-5 space-y-3 text-sm text-slate-600">
            <Detail label="HIS connection" value={apiStatus?.status ?? "Loading"} />
            <Detail
              label="Patient found"
              value={apiStatus ? (apiStatus.patient_found ? "Yes" : "No") : "Loading"}
            />
            <Detail
              label="Immunizations"
              value={String(apiStatus?.records_available.immunizations ?? 0)}
            />
            <Detail
              label="Hospitalizations"
              value={String(apiStatus?.records_available.hospitalizations ?? 0)}
            />
            <Detail
              label="Epicrises"
              value={String(apiStatus?.records_available.epicrises ?? 0)}
            />
          </div>
        </aside>
      </section>

      {pageError ? <p className="error-banner">{pageError}</p> : null}

      {isFetching ? (
        <section className="grid gap-4 md:grid-cols-3">
          <div className="glass-panel h-36 animate-pulse" />
          <div className="glass-panel h-36 animate-pulse" />
          <div className="glass-panel h-36 animate-pulse" />
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Identity
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                {patient?.full_name ||
                  `${user.first_name} ${user.middle_name} ${user.last_name}`.trim() ||
                  user.username}
              </h2>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <Detail label="Birth date" value={patient?.birth_date ?? "Not available"} />
                <Detail label="Gender" value={patient?.gender ?? "Not available"} />
                <Detail label="Blood type" value={patient?.blood_type ?? "Not available"} />
              </div>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Residence
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                Address on file
              </h2>
              <p className="mt-4 text-sm leading-7 text-slate-600">
                {patient?.address ?? "No address is currently available."}
              </p>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Records
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                Coverage summary
              </h2>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <Detail label="Immunizations" value={String(immunizations.length)} />
                <Detail label="Hospitalizations" value={String(hospitalizations.length)} />
                <Detail
                  label="Epicrises"
                  value={String(hospitalizations.filter((item) => item.epicrisis).length)}
                />
              </div>
            </article>
          </section>

          <section className="grid gap-6 lg:grid-cols-[0.92fr_1.08fr]">
            <article className="glass-panel p-8 sm:p-10">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                    Immunizations
                  </p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                    Vaccination history
                  </h2>
                </div>
                <span className="chip">{immunizations.length} items</span>
              </div>

              {immunizations.length ? (
                <div className="mt-8 space-y-4">
                  {immunizations.map((item) => (
                    <article
                      key={`${item.vaccine_name}-${item.date}-${item.dose_number}`}
                      className="rounded-[28px] border border-white/60 bg-white/72 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]"
                    >
                      <h3 className="text-lg font-semibold tracking-tight text-slate-950">
                        {item.vaccine_name}
                      </h3>
                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        <Detail label="Dose" value={String(item.dose_number)} />
                        <Detail label="Date" value={item.date} />
                        <Detail label="Institution" value={item.institution} />
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState text="No immunization records are currently synced for this patient." />
              )}
            </article>

            <article className="glass-panel p-8 sm:p-10">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                    Hospitalizations
                  </p>
                  <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
                    Admissions and epicrises
                  </h2>
                </div>
                <span className="chip">{hospitalizations.length} stays</span>
              </div>

              {hospitalizations.length ? (
                <div className="mt-8 space-y-5">
                  {hospitalizations.map((item) => (
                    <article
                      key={`${item.diagnosis_code}-${item.admission_date}-${item.department}`}
                      className="rounded-[28px] border border-white/60 bg-white/72 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h3 className="text-xl font-semibold tracking-tight text-slate-950">
                            {item.diagnosis}
                          </h3>
                          <p className="mt-2 text-sm text-slate-500">
                            {item.diagnosis_code} · {item.department}
                          </p>
                        </div>
                        <span className="chip">{item.institution}</span>
                      </div>

                      <div className="mt-5 grid gap-3 md:grid-cols-2">
                        <StatCard label="Admission date" value={item.admission_date} />
                        <StatCard
                          label="Discharge date"
                          value={item.discharge_date ?? "Ongoing / not recorded"}
                        />
                      </div>

                      {item.epicrisis ? (
                        <div className="mt-5 rounded-[24px] border border-teal-100 bg-teal-50/80 p-5">
                          <p className="text-xs uppercase tracking-[0.24em] text-teal-700">
                            Epicrisis
                          </p>
                          <p className="mt-3 text-sm leading-7 text-slate-700">
                            {item.epicrisis.summary}
                          </p>
                          <p className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">
                            Recommendations
                          </p>
                          <p className="mt-2 text-sm leading-7 text-slate-700">
                            {item.epicrisis.recommendations}
                          </p>
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState text="No hospitalization records are currently synced for this patient." />
              )}
            </article>
          </section>
        </>
      )}
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

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/60 bg-white/82 p-4">
      <p className="text-xs uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="mt-8 text-sm leading-7 text-slate-600">{text}</p>;
}
