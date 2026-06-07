"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  assignDoctorPatient,
  fetchCurrentUser,
  fetchDoctorPatients,
  logoutUser,
  primeSecurityContext,
  requestLoginChallenge,
  signUpDoctor,
  signUpPatient,
  type AuthUser,
  type DoctorPatientAssignment,
  type DoctorPatientLookupPayload,
  type DoctorSignUpPayload,
  type LoginChallenge,
  type LoginPayload,
  type PatientSignUpPayload,
  type VerifyLoginPayload,
  verifyLoginCode,
} from "@/lib/auth-client";

type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  beginLogin: (payload: LoginPayload) => Promise<LoginChallenge>;
  verifyLogin: (payload: VerifyLoginPayload) => Promise<AuthUser>;
  signupPatient: (payload: PatientSignUpPayload) => Promise<AuthUser>;
  signupDoctor: (payload: DoctorSignUpPayload) => Promise<AuthUser>;
  fetchAssignedPatients: () => Promise<DoctorPatientAssignment[]>;
  assignPatientToDoctor: (
    payload: DoctorPatientLookupPayload,
  ) => Promise<{ assignment: DoctorPatientAssignment; created: boolean }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isCancelled = false;

    async function bootstrapAuth() {
      try {
        await primeSecurityContext().catch(() => null);
        const nextUser = await fetchCurrentUser();

        if (!isCancelled) {
          setUser(nextUser);
        }
      } catch {
        if (!isCancelled) {
          setUser(null);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    }

    void bootstrapAuth();

    return () => {
      isCancelled = true;
    };
  }, []);

  async function refreshUser() {
    setIsLoading(true);

    void primeSecurityContext().catch(() => null);

    try {
      const nextUser = await fetchCurrentUser();
      setUser(nextUser);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }

  async function beginLogin(payload: LoginPayload) {
    return requestLoginChallenge(payload);
  }

  async function verifyLogin(payload: VerifyLoginPayload) {
    const nextUser = await verifyLoginCode(payload);
    setUser(nextUser);
    return nextUser;
  }

  async function signupPatientAction(payload: PatientSignUpPayload) {
    const nextUser = await signUpPatient(payload);
    setUser(nextUser);
    return nextUser;
  }

  async function signupDoctorAction(payload: DoctorSignUpPayload) {
    const nextUser = await signUpDoctor(payload);
    setUser(nextUser);
    return nextUser;
  }

  async function fetchAssignedPatients() {
    return fetchDoctorPatients();
  }

  async function assignPatientToDoctor(payload: DoctorPatientLookupPayload) {
    return assignDoctorPatient(payload);
  }

  async function logout() {
    await logoutUser();
    setUser(null);
    await primeSecurityContext().catch(() => null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        isLoading,
        beginLogin,
        verifyLogin,
        signupPatient: signupPatientAction,
        signupDoctor: signupDoctorAction,
        fetchAssignedPatients,
        assignPatientToDoctor,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
