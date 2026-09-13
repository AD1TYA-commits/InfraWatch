import {
  AnalysisResult, Evidence, ProjectSummary, ProjectDetail, KPISummary,
  AuthToken, User, Risk,
} from "@/types/project";

const rawApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
// Normalize localhost to 127.0.0.1 to eliminate Windows IPv6 (::1) 30s connection timeout
export const API_BASE = rawApiBase.replace("localhost", "127.0.0.1");

const TOKEN_KEY = "infrawatch_token";

/** Resolve an image/asset path returned by the backend into a full URL.
 * Manually-uploaded evidence photos come back as a backend-relative path
 * (e.g. "/manual-evidence/x.png"); real satellite-service results come back
 * already-absolute (e.g. "http://localhost:8001/data/...").
 * Returns "" for empty/missing input so callers can safely check truthiness. */
export function resolveAssetUrl(url?: string | null): string {
  if (!url) return "";
  return /^https?:\/\//i.test(url) ? url : `${API_BASE}${url}`;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // localStorage can throw in private-browsing contexts — losing the
    // token just means the user gets logged out, not a crash.
  }
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const token = getToken();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      signal: controller.signal,
      ...init,
      headers: {
        ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
    });
    if (!res.ok) {
      let detail = `Request to ${path} failed with status ${res.status}`;
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
      } catch {
        // response wasn't JSON — keep the generic message
      }
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ── Auth ─────────────────────────────────────────────────────────────────

export function register(payload: {
  email: string; password: string; role: "analyst" | "contractor"; full_name: string; organization?: string;
}): Promise<AuthToken> {
  return fetchJson<AuthToken>("/api/auth/register", { method: "POST", body: JSON.stringify(payload) });
}

export function login(email: string, password: string): Promise<AuthToken> {
  return fetchJson<AuthToken>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export function getMe(): Promise<User> {
  return fetchJson<User>("/api/auth/me");
}

// ── Projects ─────────────────────────────────────────────────────────────

export function getProjects(params?: {
  page?: number; page_size?: number; data_source?: string; evidence_source?: string;
}): Promise<ProjectSummary[]> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  if (params?.data_source) qs.set("data_source", params.data_source);
  if (params?.evidence_source) qs.set("evidence_source", params.evidence_source);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return fetchJson<ProjectSummary[]>(`/api/projects${suffix}`);
}

export function getMyProjects(): Promise<ProjectSummary[]> {
  return fetchJson<ProjectSummary[]>("/api/projects/mine");
}

export function createProject(payload: {
  name: string; project_type: string; description?: string; latitude: number; longitude: number;
  reported_progress?: number; approved_cost?: number;
}): Promise<ProjectDetail> {
  return fetchJson<ProjectDetail>("/api/projects", { method: "POST", body: JSON.stringify(payload) });
}

export function uploadManualEvidence(id: number | string, before: File, after: File) {
  const form = new FormData();
  form.append("before", before);
  form.append("after", after);
  return fetchJson(`/api/projects/${id}/evidence/upload`, { method: "POST", body: form }, 120000);
}

export function getProject(id: number | string): Promise<ProjectDetail> {
  return fetchJson<ProjectDetail>(`/api/projects/${id}`);
}

export function getKpiSummary(): Promise<KPISummary> {
  return fetchJson<KPISummary>("/api/projects/kpi-summary");
}

export function analyzeProject(id: number | string): Promise<AnalysisResult> {
  // Real satellite-service analysis (fetch + model) genuinely takes 10-30s,
  // well past the 8s default meant for quick DB-only reads.
  return fetchJson<AnalysisResult>(`/api/projects/${id}/analyze`, { method: "POST" }, 120000);
}

export function getEvidence(id: number | string): Promise<Evidence> {
  return fetchJson<Evidence>(`/api/projects/${id}/evidence`);
}

export function getRisk(id: number | string): Promise<Risk> {
  return fetchJson<Risk>(`/api/projects/${id}/risk`);
}
