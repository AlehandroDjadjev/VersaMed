"use client";

import { LoginFlow } from "@/components/login-flow";
import { SignupChoice } from "@/components/signup-choice";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  return mode === "login" ? <LoginFlow /> : <SignupChoice />;
}
