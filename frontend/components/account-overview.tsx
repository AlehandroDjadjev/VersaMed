"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useEffectEvent, useTransition } from "react";

import { useAuth } from "@/components/auth-provider";

function initials(firstName: string, lastName: string, username: string) {
  const first = firstName.trim().charAt(0);
  const last = lastName.trim().charAt(0);
  return `${first}${last}`.trim() || username.slice(0, 2).toUpperCase();
}

export function AccountOverview() {
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const [isPending, startTransition] = useTransition();

  const redirectIfMissingUser = useEffectEvent(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?next=/account");
    }
  });

  useEffect(() => {
    redirectIfMissingUser();
  }, [isLoading, isAuthenticated]);

  async function handleLogout() {
    await logout();
    startTransition(() => {
      router.push("/");
      router.refresh();
    });
  }

  if (isLoading) {
    return (
      <main className="mx-auto flex w-full max-w-6xl flex-1 px-5 py-12 sm:px-8">
        <section className="glass-panel w-full animate-pulse p-10">
          <div className="h-5 w-28 rounded-full bg-teal-100" />
          <div className="mt-6 h-14 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-4 h-6 w-1/2 rounded-3xl bg-slate-200" />
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            <div className="h-36 rounded-[28px] bg-white/70" />
            <div className="h-36 rounded-[28px] bg-white/70" />
            <div className="h-36 rounded-[28px] bg-white/70" />
          </div>
        </section>
      </main>
    );
  }

  if (!user) {
    return null;
  }

  const profileName =
    user.role === "patient"
      ? `${user.patient_profile?.first_name ?? user.first_name} ${user.patient_profile?.middle_name ?? ""} ${user.patient_profile?.last_name ?? user.last_name}`.trim()
      : `${user.doctor_profile?.first_name ?? user.first_name} ${user.doctor_profile?.middle_name ?? ""} ${user.doctor_profile?.last_name ?? user.last_name}`.trim();

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass-panel p-8 sm:p-10">
          <span className="chip">
            {user.role === "doctor" ? "Doctor profile" : "Patient profile"}
          </span>
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            <div className="flex h-24 w-24 items-center justify-center rounded-[30px] bg-[linear-gradient(135deg,#0e736f,#39c0b4)] text-2xl font-semibold tracking-[0.12em] text-white shadow-[0_18px_40px_rgba(14,115,111,0.26)]">
              {initials(user.first_name, user.last_name, user.username)}
            </div>
            <div className="space-y-2">
              <h1 className="font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
                {profileName || user.username}
              </h1>
              <p className="max-w-xl text-lg leading-8 text-slate-600">
                {user.role === "doctor"
                  ? "Your doctor account can assign patients by EGN and three names, then keep the assigned list inside VersaMed."
                  : "Your patient account keeps the core identity fields from the HIS mockup together with your secure application access."}
              </p>
            </div>
          </div>
        </div>

        <aside className="glass-panel p-8">
          <div className="space-y-4">
            <span className="chip">Current identity</span>
            <div className="rounded-[28px] border border-white/55 bg-white/70 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
              <div className="space-y-3 text-sm text-slate-600">
                <Detail label="Username" value={user.username} />
                <Detail label="Email" value={user.email} />
                <Detail label="Role" value={user.role} />
                {user.role === "patient" ? (
                  <>
                    <Detail
                      label="EGN"
                      value={user.patient_profile?.egn ?? "Not available"}
                    />
                    <Detail
                      label="Birth date"
                      value={user.patient_profile?.birth_date ?? "Not available"}
                    />
                  </>
                ) : (
                  <>
                    <Detail
                      label="UIN"
                      value={user.doctor_profile?.uin ?? "Not available"}
                    />
                    <Detail
                      label="Specialty"
                      value={user.doctor_profile?.specialty ?? "Not available"}
                    />
                  </>
                )}
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {user.role === "doctor" ? (
          <>
            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Assignment flow
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                Assign patients securely.
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                Match the patient with their EGN and full three-name identity to
                add them to your doctor workspace.
              </p>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Assigned list
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                See all connected patients.
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                Review the patients assigned to your account from one doctor-side
                page.
              </p>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Quick actions
              </p>
              <div className="mt-4 flex flex-col gap-3">
                <Link
                  href="/doctor/patients"
                  className="primary-button px-5 py-3 text-center"
                >
                  Manage patients
                </Link>
                <button
                  type="button"
                  className="secondary-button px-5 py-3 disabled:cursor-not-allowed disabled:opacity-70"
                  onClick={() => void handleLogout()}
                  disabled={isPending}
                >
                  {isPending ? "Signing out..." : "Logout"}
                </button>
              </div>
            </article>
          </>
        ) : (
          <>
            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Patient record
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                Identity profile is live.
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                Your EGN, names, and birth date are now stored in the patient
                profile model tied to your account.
              </p>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                HIS records
              </p>
              <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
                Open your organized patient data.
              </h2>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                View synced immunizations, hospitalizations, and epicrisis notes
                from the HIS-backed patient dashboard.
              </p>
            </article>

            <article className="glass-panel p-6">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Quick actions
              </p>
              <div className="mt-4 flex flex-col gap-3">
                <Link
                  href="/patient/records"
                  className="primary-button px-5 py-3 text-center"
                >
                  Open records
                </Link>
                <Link href="/" className="secondary-button px-5 py-3 text-center">
                  Return home
                </Link>
                <button
                  type="button"
                  className="secondary-button px-5 py-3 disabled:cursor-not-allowed disabled:opacity-70"
                  onClick={() => void handleLogout()}
                  disabled={isPending}
                >
                  {isPending ? "Signing out..." : "Logout"}
                </button>
              </div>
            </article>
          </>
        )}
      </section>
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
