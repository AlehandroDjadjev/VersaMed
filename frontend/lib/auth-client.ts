export type AuthUser = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
};

type AuthEnvelope = {
  user: AuthUser;
};

type FieldErrors = Record<string, string[]>;

type LoginPayload = {
  username: string;
  password: string;
};

type SignUpPayload = {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  firstName: string;
  lastName: string;
};

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const BACKEND_PREFIX = "/backend";

export class ApiError extends Error {
  status: number;
  fieldErrors: FieldErrors;

  constructor(message: string, status: number, fieldErrors: FieldErrors = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

function readCookie(name: string) {
  if (typeof document === "undefined") {
    return null;
  }

  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}=([^;]*)`),
  );

  return match ? decodeURIComponent(match[1]) : null;
}

function normalizeFieldErrors(payload: unknown): FieldErrors {
  if (!payload || typeof payload !== "object") {
    return {};
  }

  return Object.fromEntries(
    Object.entries(payload).map(([key, value]) => {
      if (Array.isArray(value)) {
        return [key, value.map((item) => String(item))];
      }

      return [key, [String(value)]];
    }),
  );
}

function getBestErrorMessage(fieldErrors: FieldErrors, fallback: string) {
  const firstErrorGroup = Object.values(fieldErrors)[0];
  return firstErrorGroup?.[0] ?? fallback;
}

async function ensureCsrfCookie() {
  await fetch(BACKEND_PREFIX, {
    method: "GET",
    cache: "no-store",
    credentials: "same-origin",
  });

  const csrfToken = readCookie("csrftoken");
  if (!csrfToken) {
    throw new ApiError(
      "We could not prepare a secure session. Please refresh and try again.",
      500,
    );
  }

  return csrfToken;
}

async function request<T>(path: string, init: RequestInit = {}) {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie("csrftoken") ?? (await ensureCsrfCookie());
    headers.set("X-CSRFToken", csrfToken);
  }

  const response = await fetch(`${BACKEND_PREFIX}${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? ((await response.json()) as unknown) : null;

  if (!response.ok) {
    const fieldErrors = normalizeFieldErrors(payload);
    throw new ApiError(
      getBestErrorMessage(fieldErrors, "Something went wrong. Please try again."),
      response.status,
      fieldErrors,
    );
  }

  return payload as T;
}

export async function fetchCurrentUser() {
  const payload = await request<AuthEnvelope>("/auth/me/");
  return payload.user;
}

export async function loginUser(payload: LoginPayload) {
  const response = await request<AuthEnvelope>("/auth/login/", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return response.user;
}

export async function signUpUser(payload: SignUpPayload) {
  const response = await request<AuthEnvelope>("/auth/signup/", {
    method: "POST",
    body: JSON.stringify({
      username: payload.username,
      email: payload.email,
      password: payload.password,
      password_confirm: payload.passwordConfirm,
      first_name: payload.firstName,
      last_name: payload.lastName,
    }),
  });

  return response.user;
}

export async function logoutUser() {
  await request("/auth/logout/", {
    method: "POST",
  });
}

export async function primeSecurityContext() {
  await ensureCsrfCookie();
}
