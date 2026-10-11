export type Role = "ADMIN" | "SECURITY" | "AUDITOR" | "MANAGER" | "DEVELOPER";

function resolveBaseUrl(): string {
  const envUrl = import.meta.env["VITE_API_BASE_URL"];
  if (!envUrl) {
    if (import.meta.env.PROD) {
      throw new Error("Configuration error: VITE_API_BASE_URL is not defined in production environment.");
    }
    return "http://localhost:8000";
  }
  return envUrl.replace(/\/$/, "");
}

const BASE = resolveBaseUrl();
const API = `${BASE}/api/v1`;

function token(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ag_token");
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

const AUTH_PASS_PATHS = ["/auth/login", "/auth/register", "/auth/google/exchange"];

async function parse<T>(res: Response, path: string): Promise<T> {
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && !AUTH_PASS_PATHS.includes(path)) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("ag_token");
        localStorage.removeItem("ag_session");
        if (!window.location.pathname.startsWith("/login")) {
          window.location.href = "/login?expired=1";
        }
      }
    }
    const msg = body?.detail ?? `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return body as T;
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: headers() });
  return parse<T>(res, path);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method: "POST",
    headers: headers(),
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, init);
  return parse<T>(res, path);
}

export async function put<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method: "PUT",
    headers: headers(),
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, init);
  return parse<T>(res, path);
}

export async function patch<T>(path: string, body?: unknown): Promise<T> {
  const init: RequestInit = {
    method: "PATCH",
    headers: headers(),
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, init);
  return parse<T>(res, path);
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { method: "DELETE", headers: headers() });
  return parse<T>(res, path);
}

export { BASE, API };
