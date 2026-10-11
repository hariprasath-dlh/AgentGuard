import { get, post, BASE } from "./api";

export interface Session {
  name: string;
  email: string;
  org: string;
  orgName: string;
  role: string;
  userId: string;
  expiresAt: number;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  organization_name: string;
  organization_slug: string;
}

const KEY = "ag_token";
const SESSION_KEY = "ag_session";
const TTL = 1000 * 60 * 60 * 8;

export function getSession(): { session: Session | null; expired: boolean } {
  if (typeof window === "undefined") return { session: null, expired: false };
  const raw = localStorage.getItem(SESSION_KEY);
  if (!raw) return { session: null, expired: false };
  try {
    const s = JSON.parse(raw) as Session;
    if (s.expiresAt < Date.now()) {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(KEY);
      return { session: null, expired: true };
    }
    return { session: s, expired: false };
  } catch {
    return { session: null, expired: false };
  }
}

export function storeSession(s: Omit<Session, "expiresAt">): Session {
  const session: Session = { ...s, expiresAt: Date.now() + TTL };
  if (typeof window !== "undefined") {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  }
  return session;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export async function login(email: string, password: string, org: string): Promise<Session> {
  const body: Record<string, string> = { email, password };
  if (org.trim()) {
    body["organization_slug"] = org.trim();
  }

  const tok = await post<TokenResponse>("/auth/login", body);
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, tok.access_token);
  }

  const me = await get<UserResponse>("/auth/me");
  return storeSession({
    name: me.full_name ?? me.email,
    email: me.email,
    org: me.organization_slug,
    orgName: me.organization_name,
    role: me.role,
    userId: me.id,
  });
}

export async function register(u: {
  name: string;
  email: string;
  password: string;
  orgName: string;
  org: string;
  role: string;
}): Promise<Session> {
  await post<UserResponse>("/auth/register", {
    full_name: u.name,
    email: u.email,
    password: u.password,
    organization_name: u.orgName,
    organization_slug: u.org,
    role: u.role,
  });
  return login(u.email, u.password, u.org);
}

export async function exchangeCode(code: string): Promise<Session> {
  const tok = await post<TokenResponse>("/auth/google/exchange", { code });
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, tok.access_token);
  }
  const me = await get<UserResponse>("/auth/me");
  return storeSession({
    name: me.full_name ?? me.email,
    email: me.email,
    org: me.organization_slug,
    orgName: me.organization_name,
    role: me.role,
    userId: me.id,
  });
}

export async function bootstrapSession(): Promise<Session | null> {
  if (typeof window === "undefined") return null;
  const currentToken = localStorage.getItem(KEY);
  if (!currentToken) return null;

  try {
    const me = await get<UserResponse>("/auth/me");
    return storeSession({
      name: me.full_name ?? me.email,
      email: me.email,
      org: me.organization_slug,
      orgName: me.organization_name,
      role: me.role,
      userId: me.id,
    });
  } catch {
    logout();
    return null;
  }
}

export function googleLoginUrl(): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const frontendCallback = encodeURIComponent(`${origin}/auth/callback`);
  return `${BASE}/api/v1/auth/google/login?redirect_target=${frontendCallback}`;
}

export function logout() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(KEY);
    localStorage.removeItem(SESSION_KEY);
  }
}
