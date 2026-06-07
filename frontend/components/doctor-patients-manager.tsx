"use client";

import { useRouter } from "next/navigation";
import {
  useEffect,
  useState,
  type FormEvent,
  type HTMLAttributes,
} from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError, type DoctorPatientAssignment } from "@/lib/auth-client";

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

export function DoctorPatientsManager() {
  const router = useRouter();
  const { assignPatientToDoctor, fetchAssignedPatients, isAuthenticated, isLoading, user } =
    useAuth();
  const [assignments, setAssignments] = useState<DoctorPatientAssignment[]>([]);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login?next=/doctor/patients");
      return;
    }

    if (!isLoading && user && user.role !== "doctor") {
      router.replace("/account");
    }
  }, [isAuthenticated, isLoading, router, user]);

  useEffect(() => {
    if (!user || user.role !== "doctor") {
      return;
    }

    let isCancelled = false;

    async function loadAssignments() {
      setIsFetching(true);

      try {
        const nextAssignments = await fetchAssignedPatients();
        if (!isCancelled) {
          setAssignments(nextAssignments);
        }
      } catch (error) {
        if (!isCancelled) {
          setFormError(
            error instanceof Error
              ? error.message
              : "We could not load the assigned patients right now.",
          );
        }
      } finally {
        if (!isCancelled) {
          setIsFetching(false);
        }
      }
    }

    void loadAssignments();

    return () => {
      isCancelled = true;
    };
  }, [fetchAssignedPatients, user]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);

    try {
      const response = await assignPatientToDoctor({
        egn: String(formData.get("egn") ?? ""),
        firstName: String(formData.get("firstName") ?? ""),
        middleName: String(formData.get("middleName") ?? ""),
        lastName: String(formData.get("lastName") ?? ""),
      });

      setAssignments((current) => {
        const filtered = current.filter(
          (item) => item.id !== response.assignment.id,
        );
        return [response.assignment, ...filtered];
      });

      event.currentTarget.reset();
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

  if (isLoading || !user || user.role !== "doctor") {
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

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="grid gap-6 lg:grid-cols-[0.94fr_1.06fr]">
        <aside className="glass-panel p-8 sm:p-10">
          <span className="chip">Doctor patients</span>
          <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
            Assign patients by verified identity.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            Use the patient&apos;s EGN and all three names to match the correct
            patient profile before adding them to your doctor workspace.
          </p>
        </aside>

        <div className="glass-panel p-8 sm:p-10">
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            <div className="space-y-2">
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                Patient lookup
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-slate-950">
                Assign a patient
              </h2>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                name="egn"
                label="EGN"
                placeholder="9001010000"
                inputMode="numeric"
                error={fieldError(fieldErrors, "egn")}
              />
              <Field
                name="firstName"
                label="First name"
                placeholder="Ivan"
                error={fieldError(fieldErrors, "first_name")}
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
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
                error={fieldError(fieldErrors, "last_name", "non_field_errors")}
              />
            </div>

            {formError ? <p className="error-banner">{formError}</p> : null}

            <button
              type="submit"
              className="primary-button w-full px-6 py-3 text-base disabled:cursor-not-allowed disabled:opacity-70"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Assigning..." : "Assign patient"}
            </button>
          </form>
        </div>
      </section>

      <section className="glass-panel p-8 sm:p-10">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Assigned list
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              Your assigned patients
            </h2>
          </div>
          <span className="chip">{assignments.length} linked</span>
        </div>

        {isFetching ? (
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <div className="h-36 animate-pulse rounded-[28px] bg-white/70" />
            <div className="h-36 animate-pulse rounded-[28px] bg-white/70" />
          </div>
        ) : assignments.length ? (
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            {assignments.map((assignment) => (
              <article
                key={assignment.id}
                className="rounded-[28px] border border-white/60 bg-white/72 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]"
              >
                <h3 className="text-xl font-semibold text-slate-950">
                  {assignment.patient.first_name} {assignment.patient.middle_name}{" "}
                  {assignment.patient.last_name}
                </h3>
                <div className="mt-4 space-y-2 text-sm text-slate-600">
                  <Detail label="EGN" value={assignment.patient.egn} />
                  <Detail label="Birth date" value={assignment.patient.birth_date} />
                  <Detail label="Username" value={assignment.patient.user.username} />
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-8 text-base leading-7 text-slate-600">
            No patients are assigned to this doctor yet.
          </p>
        )}
      </section>
    </main>
  );
}

function Field({
  name,
  label,
  error,
  placeholder,
  inputMode,
}: {
  name: string;
  label: string;
  error: string | null;
  placeholder?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        name={name}
        type="text"
        className={inputClassName(Boolean(error))}
        placeholder={placeholder}
        inputMode={inputMode}
        required
      />
      {error ? <p className="error-text">{error}</p> : null}
    </label>
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
