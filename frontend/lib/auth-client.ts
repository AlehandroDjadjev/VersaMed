export type UserRole = "patient" | "doctor" | "admin";

export type PatientProfile = {
  egn: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  blood_type: string;
  address: string;
};

export type DoctorProfile = {
  first_name: string;
  middle_name: string;
  last_name: string;
  uin: string;
  specialty: string;
  assigned_patients_count: number;
};

export type AuthUser = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  role: UserRole;
  patient_profile: PatientProfile | null;
  doctor_profile: DoctorProfile | null;
};

export type LoginChallenge = {
  challenge_id: string;
  expires_in: number;
  email: string;
  dev_code?: string;
};

export type AssignedPatient = {
  egn: string;
  first_name: string;
  middle_name: string;
  last_name: string;
  birth_date: string;
  user: AuthUser;
};

export type DoctorPatientAssignment = {
  id: number;
  assigned_at: string;
  patient: AssignedPatient;
};

export type PatientDashboardData = {
  user: {
    id: number;
    username: string;
    email: string;
    role: UserRole;
  };
  patient: {
    full_name: string;
    birth_date: string;
    gender: string;
    blood_type: string;
    address: string;
  };
  mock_hospital_api: {
    status: string;
    patient_found: boolean;
    records_available: {
      immunizations: number;
      hospitalizations: number;
      epicrises: number;
    };
  };
  database: {
    immunizations: Array<{
      vaccine_name: string;
      dose_number: number;
      date: string;
      institution: string;
    }>;
    hospitalizations: Array<{
      department: string;
      diagnosis_code: string;
      diagnosis: string;
      admission_date: string;
      discharge_date: string | null;
      institution: string;
      epicrisis: {
        summary: string;
        recommendations: string;
      } | null;
    }>;
  };
};

export type MedicalProblem = {
  id: number;
  title: string;
  summary: string;
  body_area: string;
  keywords: string[];
  created_at: string;
  updated_at: string;
};

export type DiagnosisProblemLink = {
  id: number;
  problem: MedicalProblem;
  strength: "weak" | "moderate" | "strong";
  reason: string;
  created_at: string;
};

export type AnalyzedDiagnosis = {
  source_id: string;
  diagnosis: {
    id: number;
    kind: string;
    title: string;
    raw_text: string;
    raw_json: Record<string, unknown>;
    happened_at: string | null;
    summary: string;
    description: string;
    extracted_findings: Array<Record<string, string | number | null>>;
    keywords: string[];
    body_areas: string[];
    created_at: string;
  };
  problem_links: DiagnosisProblemLink[];
};

export type SyncEnvelope = {
  status: string;
  user: AuthUser;
  new_records: {
    hospitalizations: number;
  };
  analyzed_diagnoses: AnalyzedDiagnosis[];
  latest_diagnosis: AnalyzedDiagnosis | null;
  analysis_errors: Array<{
    source_id: string;
    message: string;
  }>;
  new_problem: MedicalProblem | null;
};

type AuthEnvelope = {
  user: AuthUser | null;
};

type AssignmentsEnvelope = {
  assignments: DoctorPatientAssignment[];
};

type AssignmentEnvelope = {
  assignment: DoctorPatientAssignment;
  created: boolean;
};

type FieldErrors = Record<string, string[]>;

export type LoginPayload = {
  loginId: string;
  password: string;
};

export type VerifyLoginPayload = {
  challengeId: string;
  code: string;
};

export type PatientSignUpPayload = {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  firstName: string;
  middleName: string;
  lastName: string;
  egn: string;
  birthDate: string;
  gender: string;
  bloodType: string;
  address: string;
};

export type DoctorSignUpPayload = {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  firstName: string;
  middleName: string;
  lastName: string;
  uin: string;
  specialty: string;
};

export type DoctorPatientLookupPayload = {
  egn: string;
  firstName: string;
  middleName: string;
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
  await fetch(`${BACKEND_PREFIX}/auth/csrf`, {
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

export async function requestLoginChallenge(payload: LoginPayload) {
  const loginId = payload.loginId.trim();

  return request<LoginChallenge>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({
      login_id: loginId,
      password: payload.password,
    }),
  });
}

export async function verifyLoginCode(payload: VerifyLoginPayload) {
  const response = await request<AuthEnvelope>("/auth/login/verify/", {
    method: "POST",
    body: JSON.stringify({
      challenge_id: payload.challengeId,
      code: payload.code,
    }),
  });

  if (!response.user) {
    throw new ApiError("We could not complete the login session.", 500);
  }

  return response.user;
}

export async function signUpPatient(payload: PatientSignUpPayload) {
  const response = await request<AuthEnvelope>("/auth/signup/patient/", {
    method: "POST",
    body: JSON.stringify({
      username: payload.username,
      email: payload.email,
      password: payload.password,
      password_confirm: payload.passwordConfirm,
      first_name: payload.firstName,
      middle_name: payload.middleName,
      last_name: payload.lastName,
      egn: payload.egn,
      birth_date: payload.birthDate,
      gender: payload.gender,
      blood_type: payload.bloodType,
      address: payload.address,
    }),
  });

  if (!response.user) {
    throw new ApiError("We could not create the patient account.", 500);
  }

  return response.user;
}

export async function signUpDoctor(payload: DoctorSignUpPayload) {
  const response = await request<AuthEnvelope>("/auth/signup/doctor/", {
    method: "POST",
    body: JSON.stringify({
      username: payload.username,
      email: payload.email,
      password: payload.password,
      password_confirm: payload.passwordConfirm,
      first_name: payload.firstName,
      middle_name: payload.middleName,
      last_name: payload.lastName,
      uin: payload.uin,
      specialty: payload.specialty,
    }),
  });

  if (!response.user) {
    throw new ApiError("We could not create the doctor account.", 500);
  }

  return response.user;
}

export async function fetchDoctorPatients() {
  const response = await request<AssignmentsEnvelope>("/auth/doctor/patients/");
  return response.assignments;
}

export async function fetchPatientDashboard() {
  return request<PatientDashboardData>("/api/dashboard/");
}

export async function fetchMedicalProblem(problemId: string | number) {
  return request<MedicalProblem>(`/api/problems/${problemId}/`);
}

export async function syncPatientFromHisApi(personalIdentifier: string) {
  return request<SyncEnvelope>("/api/onboarding/sync/", {
    method: "POST",
    body: JSON.stringify({
      personal_identifier: personalIdentifier,
    }),
  });
}

export async function assignDoctorPatient(payload: DoctorPatientLookupPayload) {
  return request<AssignmentEnvelope>("/auth/doctor/patients/", {
    method: "POST",
    body: JSON.stringify({
      egn: payload.egn,
      first_name: payload.firstName,
      middle_name: payload.middleName,
      last_name: payload.lastName,
    }),
  });
}

export async function logoutUser() {
  await request("/auth/logout/", {
    method: "POST",
  });
}

export async function primeSecurityContext() {
  await ensureCsrfCookie();
}
