"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";

const heroHighlights = [
  {
    title: "Structured report tracking",
    description: "Keep labs, scans, prescriptions, and notes in one timeline.",
  },
  {
    title: "Research connected to context",
    description: "Attach findings and references to the exact marker or symptom.",
  },
  {
    title: "Integrated medical agents",
    description: "Summarize, compare, and prepare next-step questions faster.",
  },
];

const featureBlocks = [
  {
    label: "01",
    title: "Your medical memory",
    description:
      "VersaMed keeps your reports, notes, and follow-ups organized so you stop losing the thread between appointments.",
  },
  {
    label: "02",
    title: "A cleaner research workflow",
    description:
      "Save and revisit medical research beside the record it explains, instead of scattering it across tabs and documents.",
  },
  {
    label: "03",
    title: "Agents that help, not overwhelm",
    description:
      "Use built-in agents for summaries, trend reviews, and prep work while staying in control of the reasoning path.",
  },
];

const processSteps = [
  {
    step: "Upload",
    title: "Bring records into one system",
    description:
      "Collect bloodwork, scans, physician notes, and medication history in a single place.",
  },
  {
    step: "Connect",
    title: "See what belongs together",
    description:
      "VersaMed links reports, symptoms, and supporting research so the bigger picture becomes easier to read.",
  },
  {
    step: "Ask",
    title: "Use agents to move faster",
    description:
      "Generate summaries, review changes across time, and prepare sharper follow-up questions for care decisions.",
  },
];

export function HomeShowcase() {
  const { isAuthenticated, isLoading, user } = useAuth();
  const primaryAction = isAuthenticated
    ? { href: "/account", label: "Open workspace" }
    : { href: "/signup", label: "Get started" };
  const secondaryAction = isAuthenticated
    ? { href: "/login", label: "Switch account" }
    : { href: "/login", label: "Login" };
  const statusLine = isLoading
    ? "Checking whether your medical workspace is already active."
    : isAuthenticated
      ? `Welcome back${user?.first_name ? `, ${user.first_name}` : ""}. Your account is live and ready.`
      : "A focused digital home for medical records, research, and agent-assisted review.";

  return (
    <main className="mx-auto flex w-full max-w-[1280px] flex-1 flex-col gap-7 px-5 pb-14 pt-4 sm:px-8 lg:gap-9 lg:pb-20">
      <section className="hero-shell overflow-hidden rounded-[2.5rem]">
        <div className="hero-video-shell">
          <video
            className="hero-video"
            autoPlay
            muted
            loop
            playsInline
            preload="metadata"
          >
            <source src="/videos/hero-soft-blue.mp4" type="video/mp4" />
          </video>
          <div className="hero-video-overlay" />
          <div className="hero-video-glow" />
        </div>

        <div className="relative z-10 px-6 py-8 sm:px-8 sm:py-10 lg:px-12 lg:py-14">
          <div className="reveal-up">
            <span className="chip bg-white/16 text-white ring-1 ring-white/15">
              Digital medical assistant
            </span>
          </div>

          <div className="mt-8 max-w-4xl space-y-5">
            <h1 className="hero-headline reveal-up delay-1">
              <span className="hero-line">Keep every report,</span>
              <span className="hero-line">every study,</span>
              <span className="hero-line">and every insight together.</span>
            </h1>

            <p className="hero-subcopy reveal-up delay-2">
              VersaMed is a clean workspace for medical records and research,
              powered by integrated agents that help you summarize findings,
              track changes, and stay oriented across time.
            </p>
          </div>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row reveal-up delay-3">
            <Link href={primaryAction.href} className="primary-button px-6 py-3">
              {primaryAction.label}
            </Link>
            <Link
              href={secondaryAction.href}
              className="hero-secondary-button px-6 py-3"
            >
              {secondaryAction.label}
            </Link>
          </div>

          <p className="mt-6 max-w-xl text-sm leading-7 text-white/72 reveal-up delay-4">
            {statusLine}
          </p>

          <div className="mt-10 grid gap-3 lg:grid-cols-3">
            {heroHighlights.map((item, index) => (
              <article
                key={item.title}
                className={`hero-feature-card reveal-up delay-${index + 2}`}
              >
                <div className="h-10 w-10 rounded-full border border-white/18 bg-white/12" />
                <h2 className="mt-5 text-lg font-semibold tracking-tight text-white">
                  {item.title}
                </h2>
                <p className="mt-2 text-sm leading-7 text-white/70">
                  {item.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        {featureBlocks.map((item, index) => (
          <article
            key={item.title}
            className={`glass-panel reveal-panel p-6 sm:p-7 delay-${index + 1}`}
          >
            <span className="text-xs uppercase tracking-[0.28em] text-slate-500">
              {item.label}
            </span>
            <h2 className="mt-4 text-2xl font-semibold tracking-tight text-slate-950">
              {item.title}
            </h2>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              {item.description}
            </p>
          </article>
        ))}
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="glass-panel reveal-panel p-8 sm:p-10">
          <span className="chip">Why it feels lighter</span>
          <h2 className="mt-6 max-w-xl font-[family:var(--font-versa-display)] text-4xl leading-tight tracking-tight text-slate-950 sm:text-5xl">
            Built to reduce noise, not add more of it.
          </h2>
          <p className="mt-4 max-w-xl text-base leading-8 text-slate-600 sm:text-lg">
            The homepage stays focused on what matters: records, research, and
            agent support. No unnecessary widgets. No fake complexity. Just a
            calmer entry into a medical intelligence product.
          </p>
        </div>

        <div className="glass-panel reveal-panel p-8 sm:p-10">
          <span className="chip">How it works</span>
          <div className="mt-8 space-y-4">
            {processSteps.map((item) => (
              <article key={item.step} className="process-row">
                <div className="process-step">{item.step}</div>
                <div>
                  <h3 className="text-xl font-semibold tracking-tight text-slate-950">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-sm leading-7 text-slate-600">
                    {item.description}
                  </p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
