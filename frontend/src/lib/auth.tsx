import { useNavigate } from "@tanstack/react-router";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { api, API_BASE_URL, UNAUTHORIZED_EVENT, type Me } from "./api";

type AuthState = {
  user: Me | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: {
    email: string;
    password: string;
    fullName: string;
    organizationName: string;
  }) => Promise<{ needsConfirmation: boolean }>;
  loginWithGoogle: () => Promise<void>;
  exchangeGoogleCode: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  setSessionToken: (token: string) => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("agentguard_token");
    }
    return null;
  });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const loadProfile = useCallback(async () => {
    const currentToken = typeof window !== "undefined" ? localStorage.getItem("agentguard_token") : null;
    if (!currentToken) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api<Me>("/auth/me");
      setUser(me);
    } catch {
      if (typeof window !== "undefined") {
        localStorage.removeItem("agentguard_token");
      }
      setUser(null);
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    const handler = () => {
      setUser(null);
      setToken(null);
      toast.error("Session expired. Please log in again.");
      navigate({ to: "/login", replace: true });
    };
    window.addEventListener(UNAUTHORIZED_EVENT, handler);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler);
  }, [navigate]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    if (typeof window !== "undefined") {
      localStorage.setItem("agentguard_token", res.access_token);
    }
    setToken(res.access_token);
    const me = await api<Me>("/auth/me");
    setUser(me);
  }, []);

  const signup = useCallback<AuthState["signup"]>(
    async ({ email, password, fullName, organizationName }) => {
      const cleanSlug = organizationName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      const slug = cleanSlug.length >= 2 ? cleanSlug : `org-${Date.now()}`;

      await api("/auth/register", {
        method: "POST",
        body: {
          email,
          password,
          full_name: fullName,
          organization_name: organizationName || undefined,
          organization_slug: slug,
        },
      });

      // Auto-login after registration
      await login(email, password);
      return { needsConfirmation: false };
    },
    [login],
  );

  const setSessionToken = useCallback(async (newToken: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("agentguard_token", newToken);
    }
    setToken(newToken);
    await loadProfile();
  }, [loadProfile]);

  const loginWithGoogle = useCallback(async () => {
    const apiBase = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
    const target = typeof window !== "undefined" ? `${window.location.origin}/login` : "";
    window.location.href = `${apiBase}/api/v1/auth/google/login?redirect_target=${encodeURIComponent(target)}`;
  }, []);

  const exchangeGoogleCode = useCallback(async (code: string) => {
    const res = await api<{ access_token: string; token_type: string }>("/auth/google/exchange", {
      method: "POST",
      body: { code },
    });
    if (typeof window !== "undefined") {
      localStorage.setItem("agentguard_token", res.access_token);
    }
    setToken(res.access_token);
    await loadProfile();
  }, [loadProfile]);

  const logout = useCallback(async () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("agentguard_token");
    }
    setUser(null);
    setToken(null);
    navigate({ to: "/login", replace: true });
  }, [navigate]);

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, signup, loginWithGoogle, exchangeGoogleCode, logout, setSessionToken }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
