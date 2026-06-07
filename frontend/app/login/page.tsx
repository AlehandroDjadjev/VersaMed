import { Suspense } from "react";

import { LoginFlow } from "@/components/login-flow";

export default function LoginPage() {
  return (
    <Suspense fallback={<AuthShellFallback />}>
      <LoginFlow />
    </Suspense>
  );
}

function AuthShellFallback() {
  return (
    <main className="min-h-screen bg-[#F7F8FA] px-6 py-12">
      <section className="mx-auto grid min-h-[80vh] w-full max-w-6xl animate-pulse gap-6 rounded-[2rem] bg-white/70 p-8 lg:grid-cols-2">
        <div className="hidden rounded-[1.75rem] bg-[#08111F] lg:block" />
        <div className="rounded-[1.75rem] bg-white p-8">
          <div className="h-4 w-24 rounded-full bg-emerald-100" />
          <div className="mt-5 h-12 w-2/3 rounded-3xl bg-slate-200" />
          <div className="mt-3 h-5 w-1/2 rounded-3xl bg-slate-200" />
          <div className="mt-10 h-64 rounded-[1.5rem] bg-slate-100" />
        </div>
      </section>
    </main>
  );
}
