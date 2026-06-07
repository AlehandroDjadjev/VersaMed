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

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="glass-panel p-8 sm:p-10">
          <span className="chip">Account center</span>
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            <div className="flex h-24 w-24 items-center justify-center rounded-[30px] bg-[linear-gradient(135deg,#0e736f,#39c0b4)] text-2xl font-semibold tracking-[0.12em] text-white shadow-[0_18px_40px_rgba(14,115,111,0.26)]">
              {initials(user.first_name, user.last_name, user.username)}
            </div>
            <div className="space-y-2">
              <h1 className="font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
                {user.first_name ? `${user.first_name}, you're in.` : "You're in."}
              </h1>
              <p className="max-w-xl text-lg leading-8 text-slate-600">
                This is a minimal signed-in area for VersaMed. It confirms the
                session, exposes core user details, and gives us a clean place to
                extend profile and dashboard behavior next.
              </p>
            </div>
          </div>
        </div>

        <aside className="glass-panel animate-float p-8">
          <div className="space-y-4">
            <span className="chip">Current identity</span>
            <div className="rounded-[28px] border border-white/55 bg-white/70 p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
              <div className="space-y-3 text-sm text-slate-600">
                <Detail label="Username" value={user.username} />
                <Detail
                  label="Name"
                  value={`${user.first_name} ${user.last_name}`.trim() || "Not provided"}
                />
                <Detail label="Email" value={user.email} />
                <Detail label="Session status" value="Authenticated" />
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="glass-panel p-6">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Secure flow
          </p>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
            Login and logout are live.
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            This page is backed by the Django session and the frontend mirrors
            state changes immediately.
          </p>
        </article>

        <article className="glass-panel p-6">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Ready to grow
          </p>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
            A stable spot for profile features.
          </h2>
          <p className="mt-3 text-sm leading-7 text-slate-600">
            We can layer roles, profile editing, and app-specific dashboards on
            top of this without reworking the auth foundation.
          </p>
        </article>

        <article className="glass-panel p-6">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Quick actions
          </p>
          <div className="mt-4 flex flex-col gap-3">
            <Link href="/" className="secondary-button px-5 py-3 text-center">
              Return home
            </Link>
            <button
              type="button"
              className="primary-button px-5 py-3 disabled:cursor-not-allowed disabled:opacity-70"
              onClick={() => void handleLogout()}
              disabled={isPending}
            >
              {isPending ? "Signing out..." : "Logout"}
            </button>
          </div>
        </article>
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
