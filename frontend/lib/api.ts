import { AnalysisResult, Evidence, ProjectSummary, ProjectDetail, KPISummary } from "@/types/project";

const rawApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
// Normalize localhost to 127.0.0.1 to eliminate Windows IPv6 (::1) 30s connection timeout
export const API_BASE = rawApiBase.replace("localhost", "127.0.0.1");

/** Resolve an image/asset path returned by the backend into a full URL.
 * Demo-mode assets come back as a backend-relative path (e.g. "/demo-assets/x.png");
 * real satellite-service results come back already-absolute (e.g. "http://localhost:8001/data/...").
 * Returns "" for empty/missing input so callers can safely check truthiness. */
export function resolveAssetUrl(url?: string | null): string {
  if (!url) return "";
  return /^https?:\/\//i.test(url) ? url : `${API_BASE}${url}`;
}

async function fetchJson<T>(path: string, init?: RequestInit, timeoutMs = 8000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      signal: controller.signal,
      ...init,
    });
    if (!res.ok) {
      throw new Error(`Request to ${path} failed with status ${res.status}`);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function getProjects(): Promise<ProjectSummary[]> {
  return fetchJson<ProjectSummary[]>("/api/projects");
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
