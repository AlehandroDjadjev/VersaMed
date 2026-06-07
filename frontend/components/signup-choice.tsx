"use client";

import Link from "next/link";

export function SignupChoice() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 items-center px-5 py-12 sm:px-8">
      <section className="grid w-full gap-6 lg:grid-cols-[0.92fr_1.08fr]">
        <aside className="glass-panel p-8 sm:p-10">
          <span className="chip">Account setup</span>
          <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
            Choose the right profile from the start.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            VersaMed uses one secure user system with role-aware medical profiles.
            Patients create their identity record. Doctors create a clinical
            profile and can later assign patients by EGN and full name.
          </p>
        </aside>

        <div className="grid gap-4">
          <RoleCard
            href="/signup/patient"
            eyebrow="Patient account"
            title="Create a patient profile"
            description="Register your names, EGN, date of birth, gender, blood type, and address to create the patient record tied to your account."
            cta="Continue as patient"
          />
          <RoleCard
            href="/signup/doctor"
            eyebrow="Doctor account"
            title="Create a doctor profile"
            description="Register your names, UIN, and specialty so you can assign patient profiles and manage your linked patients from one workspace."
            cta="Continue as doctor"
          />
        </div>
      </section>
    </main>
  );
}

function RoleCard({
  href,
  eyebrow,
  title,
  description,
  cta,
}: {
  href: string;
  eyebrow: string;
  title: string;
  description: string;
  cta: string;
}) {
  return (
    <article className="glass-panel p-8">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{eyebrow}</p>
      <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
        {title}
      </h2>
      <p className="mt-4 max-w-2xl text-base leading-7 text-slate-600">
        {description}
      </p>
      <Link href={href} className="primary-button mt-6 px-5 py-3">
        {cta}
      </Link>
    </article>
  );
}
