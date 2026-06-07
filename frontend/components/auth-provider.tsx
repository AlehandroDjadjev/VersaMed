"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  fetchCurrentUser,
  loginUser,
  logoutUser,
  primeSecurityContext,
  signUpUser,
  type AuthUser,
} from "@/lib/auth-client";

type LoginInput = {
  username: string;
  password: string;
};

type SignUpInput = {
  username: string;
  email: string;
  password: string;
  passwordConfirm: string;
  firstName: string;
  lastName: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginInput) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  signup: (payload: SignUpInput) => Promise<AuthUser>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type AuthProviderProps = {
  children: ReactNode;
};

export function AuthProvider({ children }: AuthProviderProps) {
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

  async function login(payload: LoginInput) {
    const nextUser = await loginUser(payload);
    setUser(nextUser);
    return nextUser;
  }

  async function signup(payload: SignUpInput) {
    const nextUser = await signUpUser(payload);
    setUser(nextUser);
    return nextUser;
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
        login,
        logout,
        refreshUser,
        signup,
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
