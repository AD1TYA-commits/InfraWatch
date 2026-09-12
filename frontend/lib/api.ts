import { AnalysisResult, Evidence, ProjectSummary, ProjectDetail, KPISummary } from "@/types/project";

const rawApiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
// Normalize localhost to 127.0.0.1 to eliminate Windows IPv6 (::1) 30s connection timeout
const API_BASE = rawApiBase.replace("localhost", "127.0.0.1");

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
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
  return fetchJson<AnalysisResult>(`/api/projects/${id}/analyze`, { method: "POST" });
}

export function getEvidence(id: number | string): Promise<Evidence> {
  return fetchJson<Evidence>(`/api/projects/${id}/evidence`);
}
