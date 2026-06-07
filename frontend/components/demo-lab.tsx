"use client";

import Link from "next/link";

import { demoAgents, demoDoctor, demoPatient } from "@/lib/demo-data";

export function DemoLab() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-5 py-12 sm:px-8">
      <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="glass-panel p-8 sm:p-10">
          <span className="chip">Demo setup</span>
          <h1 className="mt-6 font-[family:var(--font-versa-display)] text-5xl leading-[0.96] tracking-tight text-slate-950">
            Hardcoded doctor and agents for testing.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-600">
            This page gives you a clean place to test the current logic. Seed the
            demo data once, log in as the demo doctor, and open the doctor patient
            page to verify the assigned patient flow.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/login" className="primary-button px-5 py-3">
              Open login
            </Link>
            <Link href="/doctor/patients" className="secondary-button px-5 py-3">
              Open doctor patients
            </Link>
          </div>
        </div>

        <aside className="glass-panel p-8">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Seed command
          </p>
          <div className="mt-4 rounded-[28px] border border-white/55 bg-white/72 p-5 font-mono text-sm text-slate-800 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
            python manage.py seed_demo_data
          </div>
          <p className="mt-4 text-sm leading-7 text-slate-600">
            Run that once from the `backend` folder. It creates or updates one doctor,
            one patient, and a doctor-patient assignment.
          </p>
        </aside>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="glass-panel p-8">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Demo doctor
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
            {demoDoctor.fullName}
          </h2>
          <div className="mt-5 space-y-3 text-sm text-slate-600">
            <Detail label="Username" value={demoDoctor.username} />
            <Detail label="Password" value={demoDoctor.password} />
            <Detail label="Email" value={demoDoctor.email} />
            <Detail label="UIN" value={demoDoctor.uin} />
            <Detail label="Specialty" value={demoDoctor.specialty} />
          </div>
        </article>

        <article className="glass-panel p-8">
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
            Assigned patient
          </p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-slate-950">
            {demoPatient.fullName}
          </h2>
          <div className="mt-5 space-y-3 text-sm text-slate-600">
            <Detail label="Username" value={demoPatient.username} />
            <Detail label="Password" value={demoPatient.password} />
            <Detail label="EGN" value={demoPatient.egn} />
            <Detail label="Birth date" value={demoPatient.birthDate} />
          </div>
        </article>
      </section>

      <section className="glass-panel p-8 sm:p-10">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Hardcoded agents
            </p>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
              Current agent set
            </h2>
          </div>
          <span className="chip">{demoAgents.length} agents</span>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {demoAgents.map((agent) => (
            <article
              key={agent.name}
              className="rounded-[28px] border border-white/60 bg-white/72 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]"
            >
              <p className="text-sm font-semibold tracking-tight text-slate-950">
                {agent.name}
              </p>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                {agent.purpose}
              </p>
              <p className="mt-4 text-xs uppercase tracking-[0.24em] text-slate-500">
                Focus
              </p>
              <p className="mt-2 text-sm text-slate-700">{agent.focus}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="glass-panel p-8">
        <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
          Test flow
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <Step
            title="1. Seed data"
            description="Run the demo management command once from the backend project."
          />
          <Step
            title="2. Log in as doctor"
            description="Use the demo doctor credentials on the login page and complete the verification code step."
          />
          <Step
            title="3. Open doctor patients"
            description="Go to the doctor patients page and confirm the assigned patient appears in the list."
          />
        </div>
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

function Step({ title, description }: { title: string; description: string }) {
  return (
    <article className="rounded-[28px] border border-white/60 bg-white/72 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.88)]">
      <h3 className="text-lg font-semibold tracking-tight text-slate-950">{title}</h3>
      <p className="mt-3 text-sm leading-7 text-slate-600">{description}</p>
    </article>
  );
}
