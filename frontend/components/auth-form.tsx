"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { startTransition, useState, type FormEvent } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/auth-client";

type AuthMode = "login" | "signup";

type AuthFormProps = {
  mode: AuthMode;
};

type FieldErrors = Record<string, string[]>;

function fieldError(errors: FieldErrors, ...keys: string[]) {
  for (const key of keys) {
    const first = errors[key]?.[0];
    if (first) {
      return first;
    }
  }

  return null;
}

function inputClassName(hasError: boolean) {
  return `field-input ${hasError ? "border-rose-300 shadow-[0_0_0_4px_rgba(244,63,94,0.08)]" : ""}`;
}

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, signup } = useAuth();
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const redirectTarget = searchParams.get("next") || "/account";
  const isLogin = mode === "login";

  const pageCopy = isLogin
    ? {
        eyebrow: "Welcome back",
        title: "Step back into your secure workspace.",
        subtitle:
          "Use your VersaMed credentials to restore your session and continue where you left off.",
        button: "Login",
        alternateText: "Need an account?",
        alternateHref: "/signup",
        alternateLabel: "Create one",
      }
    : {
        eyebrow: "Create access",
        title: "Start with a simple, secure account.",
        subtitle:
          "Create your VersaMed identity once, then let session-backed auth handle the rest smoothly.",
        button: "Create account",
        alternateText: "Already registered?",
        alternateHref: "/login",
        alternateLabel: "Login instead",
      };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);

    try {
      if (isLogin) {
        await login({
          username: String(formData.get("username") ?? ""),
          password: String(formData.get("password") ?? ""),
        });
      } else {
        await signup({
          username: String(formData.get("username") ?? ""),
          email: String(formData.get("email") ?? ""),
          password: String(formData.get("password") ?? ""),
          passwordConfirm: String(formData.get("passwordConfirm") ?? ""),
          firstName: String(formData.get("firstName") ?? ""),
          lastName: String(formData.get("lastName") ?? ""),
        });
      }

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

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 items-center px-5 py-10 sm:px-8 lg:py-14">
      <section className="grid w-full gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <aside className="glass-panel relative overflow-hidden p-8 sm:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.65),transparent_38%),radial-gradient(circle_at_bottom_right,rgba(57,192,180,0.18),transparent_42%)]" />
          <div className="relative space-y-6">
            <span className="chip">{pageCopy.eyebrow}</span>
            <h1 className="font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
              {pageCopy.title}
            </h1>
            <p className="max-w-md text-lg leading-8 text-slate-600">
              {pageCopy.subtitle}
            </p>

            <div className="grid gap-3 rounded-[28px] border border-white/55 bg-white/65 p-5 text-sm text-slate-600 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
              <div className="flex items-center justify-between">
                <span>Security model</span>
                <span className="font-medium text-slate-900">Django session</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Request protection</span>
                <span className="font-medium text-slate-900">CSRF enforced</span>
              </div>
              <div className="flex items-center justify-between">
                <span>Frontend behavior</span>
                <span className="font-medium text-slate-900">Same-origin proxy</span>
              </div>
            </div>
          </div>
        </aside>

        <div className="glass-panel p-8 sm:p-10">
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                {isLogin ? "Login" : "Sign up"}
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                {isLogin ? "Access your account" : "Create your account"}
              </h2>
            </div>

            {!isLogin && (
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    First name
                  </span>
                  <input
                    name="firstName"
                    type="text"
                    className={inputClassName(Boolean(fieldError(fieldErrors, "first_name")))}
                    placeholder="Ava"
                    autoComplete="given-name"
                  />
                  <FieldError message={fieldError(fieldErrors, "first_name")} />
                </label>

                <label className="space-y-2">
                  <span className="text-sm font-medium text-slate-700">
                    Last name
                  </span>
                  <input
                    name="lastName"
                    type="text"
                    className={inputClassName(Boolean(fieldError(fieldErrors, "last_name")))}
                    placeholder="Martin"
                    autoComplete="family-name"
                  />
                  <FieldError message={fieldError(fieldErrors, "last_name")} />
                </label>
              </div>
            )}

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">Username</span>
              <input
                name="username"
                type="text"
                className={inputClassName(Boolean(fieldError(fieldErrors, "username")))}
                placeholder="avamed"
                autoComplete="username"
                required
              />
              <FieldError message={fieldError(fieldErrors, "username")} />
            </label>

            {!isLogin && (
              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">Email</span>
                <input
                  name="email"
                  type="email"
                  className={inputClassName(Boolean(fieldError(fieldErrors, "email")))}
                  placeholder="ava@versamed.app"
                  autoComplete="email"
                  required
                />
                <FieldError message={fieldError(fieldErrors, "email")} />
              </label>
            )}

            <label className="space-y-2">
              <span className="text-sm font-medium text-slate-700">Password</span>
              <input
                name="password"
                type="password"
                className={inputClassName(Boolean(fieldError(fieldErrors, "password")))}
                placeholder={isLogin ? "Enter your password" : "Choose a strong password"}
                autoComplete={isLogin ? "current-password" : "new-password"}
                minLength={8}
                required
              />
              <FieldError message={fieldError(fieldErrors, "password")} />
            </label>

            {!isLogin && (
              <label className="space-y-2">
                <span className="text-sm font-medium text-slate-700">
                  Confirm password
                </span>
                <input
                  name="passwordConfirm"
                  type="password"
                  className={inputClassName(
                    Boolean(fieldError(fieldErrors, "password_confirm", "passwordConfirm")),
                  )}
                  placeholder="Repeat your password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
                <FieldError
                  message={fieldError(
                    fieldErrors,
                    "password_confirm",
                    "passwordConfirm",
                  )}
                />
              </label>
            )}

            {formError ? <p className="error-banner">{formError}</p> : null}

            <button
              type="submit"
              className="primary-button w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-70"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Working..." : pageCopy.button}
            </button>

            <p className="text-sm text-slate-600">
              {pageCopy.alternateText}{" "}
              <Link
                href={pageCopy.alternateHref}
                className="font-medium text-teal-800 underline decoration-teal-300 underline-offset-4"
              >
                {pageCopy.alternateLabel}
              </Link>
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}

function FieldError({ message }: { message: string | null }) {
  if (!message) {
    return null;
  }

  return <p className="error-text">{message}</p>;
}
