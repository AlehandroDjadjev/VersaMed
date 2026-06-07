"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTransition } from "react";

import { useAuth } from "@/components/auth-provider";

export function AppChrome() {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, logout, user } = useAuth();
  const [isPending, startTransition] = useTransition();

  if (pathname === "/login" || pathname.startsWith("/signup")) {
    return null;
  }

  async function handleLogout() {
    await logout();
    startTransition(() => {
      router.push("/");
      router.refresh();
    });
  }

  return (
    <header className="sticky top-0 z-30 px-4 pt-4 sm:px-6">
      <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <div className="header-glass flex w-full items-center justify-between gap-4 rounded-[1.75rem] px-5 py-4 sm:px-7">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#0e736f,#39c0b4)] text-sm font-semibold tracking-[0.24em] text-white shadow-[0_12px_30px_rgba(14,115,111,0.28)]">
            VM
            </span>
            <span className="flex flex-col">
              <span className="font-[family:var(--font-versa-sans)] text-lg font-semibold tracking-tight text-slate-900">
                VersaMed
              </span>
              <span className="text-xs uppercase tracking-[0.24em] text-slate-500">
                Medical intelligence
              </span>
            </span>
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            <Link href="/demo" className="secondary-button px-4 py-2">
              Demo
            </Link>
            {isLoading ? (
              <span className="chip animate-pulse">Checking session</span>
            ) : isAuthenticated ? (
              <>
                <Link href="/account" className="secondary-button px-4 py-2">
                  {user?.first_name ? `${user.first_name}'s space` : "Account"}
                </Link>
                <button
                  type="button"
                  className="primary-button px-4 py-2 disabled:cursor-not-allowed disabled:opacity-70"
                  onClick={() => void handleLogout()}
                  disabled={isPending}
                >
                  {isPending ? "Signing out..." : "Logout"}
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="secondary-button px-4 py-2">
                  Login
                </Link>
                <Link href="/signup" className="primary-button px-4 py-2">
                  Create account
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
