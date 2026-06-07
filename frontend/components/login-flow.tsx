"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { startTransition, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError, type LoginChallenge } from "@/lib/auth-client";

type LoginStage = "credentials" | "verify";
type FieldErrors = Record<string, string[]>;

function fieldError(errors: FieldErrors, ...keys: string[]) {
  for (const key of keys) {
    const message = errors[key]?.[0];
    if (message) {
      return message;
    }
  }

  return null;
}

function inputClassName(hasError: boolean) {
  return [
    "mt-2 w-full rounded-[1.15rem] border bg-white px-5 py-4 text-[#08111F] outline-none",
    "placeholder:text-slate-400 focus:border-[#08111F] focus:shadow-[0_0_0_4px_rgba(8,17,31,0.08)]",
    hasError ? "border-rose-300" : "border-slate-200",
  ].join(" ");
}

function formatExpiry(seconds: number) {
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

export function LoginFlow() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { beginLogin, verifyLogin } = useAuth();
  const [stage, setStage] = useState<LoginStage>("credentials");
  const [challenge, setChallenge] = useState<LoginChallenge | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTarget = searchParams.get("next") || "/account";

  async function handleCredentialsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);

    try {
      const nextChallenge = await beginLogin({
        loginId: String(formData.get("loginId") ?? ""),
        password: String(formData.get("password") ?? ""),
      });
      setChallenge(nextChallenge);
      setStage("verify");
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("We ran into a network issue. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleVerificationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!challenge) {
      setStage("credentials");
      return;
    }

    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);

    try {
      await verifyLogin({
        challengeId: challenge.challenge_id,
        code: String(formData.get("code") ?? ""),
      });
      startTransition(() => {
        router.push(redirectTarget);
        router.refresh();
      });
    } catch (error) {
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("We ran into a network issue. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function resetChallenge() {
    setStage("credentials");
    setChallenge(null);
    setFieldErrors({});
    setFormError(null);
  }

  return (
    <main className="min-h-screen bg-[#F7F8FA] text-[#08111F]">
      <div className="grid min-h-screen lg:grid-cols-2">
        <section className="relative hidden overflow-hidden bg-[#08111F] lg:block">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_24%_18%,rgba(95,230,210,0.3),transparent_34%),radial-gradient(circle_at_82%_62%,rgba(120,150,255,0.24),transparent_36%)]" />
          <div className="absolute inset-0 opacity-35">
            <div className="absolute left-20 top-24 h-64 w-64 rounded-full border border-white/15" />
            <div className="absolute bottom-20 right-20 h-96 w-96 rounded-full border border-white/10" />
            <div className="absolute left-28 top-72 h-px w-[520px] rotate-12 bg-gradient-to-r from-transparent via-white/45 to-transparent" />
            <div className="absolute left-36 top-96 h-px w-[420px] -rotate-12 bg-gradient-to-r from-transparent via-emerald-300/55 to-transparent" />
          </div>

          <div className="relative flex h-full flex-col justify-between p-14 text-white">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-sm font-semibold tracking-[0.2em] text-[#08111F]">
                VM
              </div>
              <span className="text-xl font-semibold tracking-tight">VersaMed</span>
            </div>

            <div className="max-w-xl">
              <div className="mb-5 inline-flex rounded-full border border-white/10 bg-white/10 px-4 py-2 text-sm text-white/70 backdrop-blur">
                Two-step medical access
              </div>

              <h1 className="text-5xl font-semibold tracking-tight">
                One protected space for every critical patient detail.
              </h1>

              <p className="mt-6 text-lg leading-8 text-white/65">
                Sign in with your username or email, confirm the verification
                code we send, and continue inside a session-backed clinical
                workspace.
              </p>
            </div>

            <div className="grid gap-4 rounded-[1.75rem] border border-white/10 bg-white/6 p-5 backdrop-blur">
              <div className="flex items-start gap-3">
                <ShieldCheckIcon className="mt-0.5 h-5 w-5 text-emerald-300" />
                <div>
                  <p className="text-sm font-medium text-white">Verification on every login</p>
                  <p className="mt-1 text-sm text-white/60">
                    Your credentials open the challenge. The code completes the session.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <PulseIcon className="mt-0.5 h-5 w-5 text-sky-300" />
                <div>
                  <p className="text-sm font-medium text-white">Built for medical review</p>
                  <p className="mt-1 text-sm text-white/60">
                    Session auth, CSRF protection, and a short-lived verification window.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-md">
            <div className="mb-10 lg:hidden">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#08111F] text-sm font-semibold tracking-[0.2em] text-white">
                  VM
                </div>
                <span className="text-xl font-semibold tracking-tight">VersaMed</span>
              </div>
            </div>

            <div>
              <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-700">
                Secure access
              </p>
              <h2 className="mt-3 text-4xl font-semibold tracking-tight">
                {stage === "credentials" ? "Welcome back" : "Verify your sign in"}
              </h2>
              <p className="mt-3 text-slate-500">
                {stage === "credentials"
                  ? "Use your username or email and password to begin a protected login."
                  : `Enter the 6-digit code sent to ${challenge?.email ?? "your email address"}.`}
              </p>
            </div>

            <div className="mt-8 rounded-full bg-slate-100 p-1">
              <div className="grid grid-cols-2 gap-1">
                <div
                  className={`rounded-full px-5 py-3 text-center text-sm font-medium transition ${
                    stage === "credentials"
                      ? "bg-white text-[#08111F] shadow-sm"
                      : "text-slate-500"
                  }`}
                >
                  1. Credentials
                </div>
                <div
                  className={`rounded-full px-5 py-3 text-center text-sm font-medium transition ${
                    stage === "verify"
                      ? "bg-white text-[#08111F] shadow-sm"
                      : "text-slate-500"
                  }`}
                >
                  2. Verification
                </div>
              </div>
            </div>

            {stage === "credentials" ? (
              <form className="mt-8 space-y-5" onSubmit={handleCredentialsSubmit} noValidate>
                <label className="block">
                  <span className="text-sm font-medium text-slate-700">
                    Username or email
                  </span>
                  <input
                    name="loginId"
                    type="text"
                    placeholder="you@versamed.app or ivanov90"
                    autoComplete="username"
                    className={inputClassName(
                      Boolean(fieldError(fieldErrors, "email", "username")),
                    )}
                    required
                  />
                  <FieldError message={fieldError(fieldErrors, "email", "username")} />
                </label>

                <label className="block">
                  <span className="text-sm font-medium text-slate-700">Password</span>
                  <input
                    name="password"
                    type="password"
                    placeholder="Enter your password"
                    autoComplete="current-password"
                    className={inputClassName(Boolean(fieldError(fieldErrors, "password")))}
                    required
                  />
                  <FieldError message={fieldError(fieldErrors, "password")} />
                </label>

                {formError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{formError}</p> : null}

                <button
                  type="submit"
                  className="group flex w-full items-center justify-center gap-3 rounded-[1.15rem] bg-[#08111F] px-5 py-4 font-semibold text-white shadow-xl shadow-slate-900/10 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-70"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Sending code..." : "Continue"}
                  <ArrowRightIcon className="h-4 w-4 transition group-hover:translate-x-1" />
                </button>
              </form>
            ) : (
              <form className="mt-8 space-y-5" onSubmit={handleVerificationSubmit} noValidate>
                <div className="rounded-[1.5rem] border border-slate-200 bg-white px-5 py-4">
                  <p className="text-sm font-medium text-slate-700">Verification code sent</p>
                  <p className="mt-1 text-sm text-slate-500">
                    This code stays active for {challenge ? formatExpiry(challenge.expires_in) : "a few minutes"}.
                  </p>
                </div>

                <label className="block">
                  <span className="text-sm font-medium text-slate-700">6-digit code</span>
                  <input
                    name="code"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="123456"
                    maxLength={6}
                    className={inputClassName(Boolean(fieldError(fieldErrors, "code")))}
                    required
                  />
                  <FieldError message={fieldError(fieldErrors, "code")} />
                </label>

                {challenge?.dev_code ? (
                  <div className="rounded-[1.5rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                    Development code: <span className="font-semibold tracking-[0.24em]">{challenge.dev_code}</span>
                  </div>
                ) : null}

                {formError ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{formError}</p> : null}

                <button
                  type="submit"
                  className="group flex w-full items-center justify-center gap-3 rounded-[1.15rem] bg-[#08111F] px-5 py-4 font-semibold text-white shadow-xl shadow-slate-900/10 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-70"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? "Verifying..." : "Complete sign in"}
                  <ArrowRightIcon className="h-4 w-4 transition group-hover:translate-x-1" />
                </button>

                <button
                  type="button"
                  onClick={resetChallenge}
                  className="w-full rounded-[1.15rem] border border-slate-200 bg-white px-5 py-4 font-medium text-slate-700 hover:bg-slate-50"
                >
                  Use a different login
                </button>
              </form>
            )}

            <p className="mt-8 text-center text-sm text-slate-500">
              New to VersaMed?{" "}
              <Link href="/signup" className="font-semibold text-[#08111F]">
                Create an account
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

function FieldError({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }

  return <p className="mt-2 text-sm text-rose-600">{message}</p>;
}

function ArrowRightIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      className={className}
    >
      <path
        d="M4.167 10h11.666M10.833 5l5 5-5 5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className={className}
    >
      <path
        d="M12 3.5 5.75 6v5.5c0 4.08 2.46 7.87 6.25 9.5 3.79-1.63 6.25-5.42 6.25-9.5V6L12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
      <path
        d="m9.5 12 1.7 1.7 3.3-3.7"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function PulseIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className={className}
    >
      <path
        d="M3.5 12h4l2.25-4.5L14 16l2.25-4H20.5"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
