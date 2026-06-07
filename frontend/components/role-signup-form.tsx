"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  startTransition,
  useState,
  type FormEvent,
  type HTMLAttributes,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/auth-client";

type FieldErrors = Record<string, string[]>;
type Role = "patient" | "doctor";

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

export function RoleSignupForm({ role }: { role: Role }) {
  const router = useRouter();
  const { signupDoctor, signupPatient } = useAuth();
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isPatient = role === "patient";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);

    try {
      if (isPatient) {
        await signupPatient({
          username: String(formData.get("username") ?? ""),
          email: String(formData.get("email") ?? ""),
          password: String(formData.get("password") ?? ""),
          passwordConfirm: String(formData.get("passwordConfirm") ?? ""),
          firstName: String(formData.get("firstName") ?? ""),
          middleName: String(formData.get("middleName") ?? ""),
          lastName: String(formData.get("lastName") ?? ""),
          egn: String(formData.get("egn") ?? ""),
          birthDate: String(formData.get("birthDate") ?? ""),
          gender: String(formData.get("gender") ?? ""),
          bloodType: String(formData.get("bloodType") ?? ""),
          address: String(formData.get("address") ?? ""),
        });
      } else {
        await signupDoctor({
          username: String(formData.get("username") ?? ""),
          email: String(formData.get("email") ?? ""),
          password: String(formData.get("password") ?? ""),
          passwordConfirm: String(formData.get("passwordConfirm") ?? ""),
          firstName: String(formData.get("firstName") ?? ""),
          middleName: String(formData.get("middleName") ?? ""),
          lastName: String(formData.get("lastName") ?? ""),
          uin: String(formData.get("uin") ?? ""),
          specialty: String(formData.get("specialty") ?? ""),
        });
      }

      startTransition(() => {
        router.push("/account");
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
      <section className="grid w-full gap-6 lg:grid-cols-[0.88fr_1.12fr]">
        <aside className="glass-panel p-8 sm:p-10">
          <span className="chip">{isPatient ? "Patient signup" : "Doctor signup"}</span>
          <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
            {isPatient
              ? "Create your patient profile."
              : "Create your doctor workspace."}
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            {isPatient
              ? "These fields map directly to the mock hospital identity shape so your patient profile is complete from day one."
              : "Doctor accounts can later assign patients by EGN and three-name identity, then manage their assigned list from one page."}
          </p>
        </aside>

        <div className="glass-panel p-8 sm:p-10">
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                {isPatient ? "Patient profile" : "Doctor profile"}
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                {isPatient ? "Patient registration" : "Doctor registration"}
              </h2>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <Field
                name="firstName"
                label="First name"
                placeholder="Ivan"
                autoComplete="given-name"
                error={fieldError(fieldErrors, "first_name")}
              />
              <Field
                name="middleName"
                label="Middle name"
                placeholder="Petrov"
                error={fieldError(fieldErrors, "middle_name")}
              />
              <Field
                name="lastName"
                label="Last name"
                placeholder="Ivanov"
                autoComplete="family-name"
                error={fieldError(fieldErrors, "last_name")}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                name="username"
                label="Username"
                placeholder="ivanov90"
                autoComplete="username"
                error={fieldError(fieldErrors, "username")}
              />
              <Field
                name="email"
                label="Email"
                type="email"
                placeholder="you@versamed.app"
                autoComplete="email"
                error={fieldError(fieldErrors, "email")}
              />
            </div>

            {isPatient ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    name="egn"
                    label="EGN"
                    placeholder="9001010000"
                    inputMode="numeric"
                    error={fieldError(fieldErrors, "egn")}
                  />
                  <Field
                    name="birthDate"
                    label="Birth date"
                    type="date"
                    error={fieldError(fieldErrors, "birth_date")}
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    name="gender"
                    label="Gender"
                    placeholder="male"
                    error={fieldError(fieldErrors, "gender")}
                  />
                  <Field
                    name="bloodType"
                    label="Blood type"
                    placeholder="A+"
                    error={fieldError(fieldErrors, "blood_type")}
                  />
                </div>

                <Field
                  name="address"
                  label="Address"
                  placeholder="Sofia, Synthetic District"
                  error={fieldError(fieldErrors, "address")}
                />
              </>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field
                  name="uin"
                  label="UIN"
                  placeholder="1234567890"
                  inputMode="numeric"
                  error={fieldError(fieldErrors, "uin")}
                />
                <Field
                  name="specialty"
                  label="Specialty"
                  placeholder="General Practice"
                  error={fieldError(fieldErrors, "specialty")}
                />
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                name="password"
                label="Password"
                type="password"
                placeholder="Choose a strong password"
                autoComplete="new-password"
                error={fieldError(fieldErrors, "password")}
              />
              <Field
                name="passwordConfirm"
                label="Confirm password"
                type="password"
                placeholder="Repeat your password"
                autoComplete="new-password"
                error={fieldError(fieldErrors, "password_confirm")}
              />
            </div>

            {formError ? <p className="error-banner">{formError}</p> : null}

            <button
              type="submit"
              className="primary-button w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-70"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating account..." : "Create account"}
            </button>

            <p className="text-sm text-slate-600">
              Already registered?{" "}
              <Link
                href="/login"
                className="font-medium text-teal-800 underline decoration-teal-300 underline-offset-4"
              >
                Login instead
              </Link>
            </p>
          </form>
        </div>
      </section>
    </main>
  );
}

function Field({
  name,
  label,
  error,
  type = "text",
  placeholder,
  autoComplete,
  inputMode,
}: {
  name: string;
  label: string;
  error: string | null;
  type?: string;
  placeholder?: string;
  autoComplete?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        type={type}
        className={inputClassName(Boolean(error))}
        placeholder={placeholder}
        autoComplete={autoComplete}
        inputMode={inputMode}
        required
      />
      {error ? <p className="error-text">{error}</p> : null}
    </label>
  );
}
