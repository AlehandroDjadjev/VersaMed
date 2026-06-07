import { Suspense } from "react";

import { AuthForm } from "@/components/auth-form";

export default function SignUpPage() {
  return (
    <Suspense fallback={<AuthShellFallback />}>
      <AuthForm mode="signup" />
    </Suspense>
  );
}

function AuthShellFallback() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 items-center px-5 py-10 sm:px-8 lg:py-14">
      <section className="glass-panel w-full animate-pulse p-10">
        <div className="h-5 w-28 rounded-full bg-teal-100" />
        <div className="mt-6 h-16 w-2/3 rounded-3xl bg-slate-200" />
        <div className="mt-4 h-6 w-1/2 rounded-3xl bg-slate-200" />
        <div className="mt-10 h-80 rounded-[28px] bg-white/70" />
      </section>
    </main>
  );
}
