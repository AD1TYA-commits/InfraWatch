"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { getProjects, getKpiSummary } from "@/lib/api";
import { ProjectSummary, KPISummary, RiskStatus } from "@/types/project";
import KpiCards from "./KpiCards";
import StatusBadge from "./StatusBadge";
import { useTheme } from "./ThemeProvider";

const ProjectMap = dynamic(() => import("./ProjectMap"), { ssr: false });

export default function Dashboard() {
  const { theme } = useTheme();
  const [projects, setProjects]   = useState<ProjectSummary[] | null>(null);
  const [kpi, setKpi]             = useState<KPISummary | null>(null);
  const [error, setError]         = useState<string | null>(null);
  const [loading, setLoading]     = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRisk, setSelectedRisk] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");

  const loadData = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      getProjects(),
      getKpiSummary().catch(() => null),
    ])
      .then(([p, k]) => {
        setProjects(p);
        if (k) setKpi(k);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []);

  const projectTypes = useMemo(() => {
    if (!projects) return [];
    return Array.from(new Set(projects.map((p) => p.project_type)));
  }, [projects]);

  const derivedKpi: KPISummary = useMemo(() => {
    if (!projects) return kpi || { total_projects: 0, normal: 0, watch: 0, high: 0, critical: 0 };
    let normal = 0, watch = 0, high = 0, critical = 0;
    projects.forEach((p) => {
      const st = (p.status || "").toLowerCase().trim();
      if (st === "least" || st === "high") high++;
      else if (st === "critical") critical++;
      else if (st === "medium" || st === "watch" || st === "review") watch++;
      else normal++;
    });
    return {
      total_projects: projects.length,
      normal,
      watch,
      high,
      critical,
    };
  }, [projects, kpi]);

  const filteredProjects = useMemo(() => {
    if (!projects) return [];
    return projects.filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.project_type.toLowerCase().includes(searchQuery.toLowerCase());
      const pStatus = p.status.toLowerCase();
      let matchesRisk = true;
      if (selectedRisk === "normal") {
        matchesRisk = pStatus === "normal";
      } else if (selectedRisk === "medium" || selectedRisk === "review") {
        matchesRisk = pStatus === "watch" || pStatus === "medium" || pStatus === "review";
      } else if (selectedRisk === "least" || selectedRisk === "high") {
        matchesRisk = pStatus === "least" || pStatus === "high" || pStatus === "critical";
      } else if (selectedRisk !== "all") {
        matchesRisk = pStatus === selectedRisk.toLowerCase();
      }
      const matchesType = selectedType === "all" || p.project_type.toLowerCase() === selectedType.toLowerCase();
      return matchesSearch && matchesRisk && matchesType;
    });
  }, [projects, searchQuery, selectedRisk, selectedType]);

  const meshStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    background: theme === "dark"
      ? `
        radial-gradient(ellipse 60% 80% at 0% 50%,   rgba(255, 255, 255, 0.03) 0%, transparent 55%),
        radial-gradient(ellipse 45% 70% at 30% 20%,  rgba(255, 255, 255, 0.02) 0%, transparent 50%),
        radial-gradient(ellipse 50% 80% at 65% 10%,  rgba(255, 255, 255, 0.015) 0%, transparent 55%),
        radial-gradient(ellipse 55% 70% at 95% 40%,  rgba(244, 63, 94, 0.05) 0%,   transparent 50%),
        radial-gradient(ellipse 40% 60% at 50% 80%,  rgba(0, 0, 0, 0.95) 0%,       transparent 60%)
      `
      : `
        radial-gradient(ellipse 60% 80% at 0% 50%,   #f5e9d4 0%,  transparent 55%),
        radial-gradient(ellipse 45% 70% at 30% 20%,  #e0d8ff 0%,  transparent 50%),
        radial-gradient(ellipse 50% 80% at 65% 10%,  #b9b9f9 0%,  transparent 55%),
        radial-gradient(ellipse 55% 70% at 95% 40%,  #ffd6ea 0%,  transparent 50%),
        radial-gradient(ellipse 40% 60% at 50% 80%,  #f0eaff 0%,  transparent 60%)
      `,
    opacity: theme === "dark" ? 0.75 : 0.9,
    pointerEvents: "none",
  };

  // ── Error state ───────────────────────────────────────────────────
  if (error) {
    return (
      <div
        className="max-w-3xl mx-auto my-12 p-6"
        style={{
          background: "#fff5f5",
          border: "1px solid #fecaca",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-1)",
        }}
      >
        <div className="flex items-start gap-4">
          <div
            className="p-2.5 rounded-lg flex-shrink-0"
            style={{ background: "#fee2e2", color: "#ea2261" }}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h3 style={{ fontSize: 16, fontWeight: 300, letterSpacing: "-0.22px", color: "var(--color-ink)", marginBottom: 6 }}>
              Unable to reach InfraWatch Backend
            </h3>
            <p style={{ fontSize: 14, color: "var(--color-ink-mute)", marginBottom: 4 }}>{error}</p>
            <p style={{ fontSize: 12, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"' }}>
              Ensure FastAPI backend is running on http://localhost:8000
            </p>
            <button
              onClick={loadData}
              id="error-retry-btn"
              style={{
                marginTop: 14, padding: "7px 16px", borderRadius: "var(--radius-pill)",
                background: "var(--color-primary)", color: "#fff",
                fontSize: 13, fontWeight: 400, border: "none", cursor: "pointer",
              }}
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading state (only while projects are pending) ────────────────
  if ((loading && !projects) || (!projects && !error)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div className="relative w-10 h-10">
          <div
            className="absolute inset-0 rounded-full border-2 animate-ping"
            style={{ borderColor: "var(--color-primary)", opacity: 0.25 }}
          />
          <div
            className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
            style={{ borderColor: "var(--color-primary)" }}
          />
        </div>
        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", letterSpacing: "-0.39px", fontFeatureSettings: '"tnum"' }}>
          Loading projects…
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* ── Hero banner with gradient mesh ─────────────────────────── */}
      <div
        className="relative overflow-hidden"
        style={{
          borderRadius: "var(--radius-xl)",
          border: "1px solid var(--color-hairline)",
          background: "var(--color-canvas)",
          boxShadow: "var(--shadow-1)",
          minHeight: 140,
        }}
      >
        {/* Mesh backdrop */}
        <div style={meshStyle} />

        {/* Content layer */}
        <div
          className="relative flex flex-col md:flex-row md:items-center justify-between gap-4"
          style={{ padding: "32px 32px" }}
        >
          <div>
            {/* Eyebrow tag */}
            <span
              style={{
                display: "inline-flex", alignItems: "center",
                padding: "3px 10px", borderRadius: "var(--radius-pill)",
                background: "var(--color-primary-bg-sub)", color: "var(--color-primary-deep)",
                fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase",
                marginBottom: 10,
              }}
            >
              AI Decision Support · SIH26102
            </span>

            <h1
              style={{
                fontSize: 32, fontWeight: 300, lineHeight: 1.1,
                letterSpacing: "-0.64px", color: "var(--color-ink)",
                fontFeatureSettings: '"ss01"',
              }}
            >
              MPLADS Infrastructure Monitoring
            </h1>
            <p
              style={{
                fontSize: 15, fontWeight: 300, color: "var(--color-ink-mute)",
                lineHeight: 1.5, marginTop: 8, maxWidth: 560,
              }}
            >
              AI-assisted satellite change detection screening for human field officer inspection.
            </p>
          </div>

          <div className="flex flex-col items-start md:items-end gap-2 flex-shrink-0">
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-lg"
              style={{ background: "var(--color-canvas-soft)", border: "1px solid var(--color-hairline)", backdropFilter: "blur(8px)" }}
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: "#10b981" }} />
                <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: "#10b981" }} />
              </span>
              <span style={{ fontSize: 11, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                DEMO IMAGE PAIRS
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI Cards ───────────────────────────────────────────────── */}
      <KpiCards kpi={derivedKpi} />

      {/* ── Map Section ─────────────────────────────────────────────── */}
      <div
        style={{
          background: "var(--color-canvas)",
          border: "1px solid var(--color-hairline)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-1)",
          overflow: "hidden",
        }}
      >
        {/* Map header */}
        <div
          className="flex items-center justify-between"
          style={{ padding: "20px 24px 16px", borderBottom: "1px solid var(--color-hairline)" }}
        >
          <div>
            <h2
              style={{
                fontSize: 18, fontWeight: 300, letterSpacing: 0, lineHeight: 1.4,
                color: "var(--color-ink)", fontFeatureSettings: '"ss01"',
                display: "flex", alignItems: "center", gap: 8,
              }}
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} style={{ color: "var(--color-primary)", flexShrink: 0 }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Geospatial Map Overview
            </h2>
            <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginTop: 2 }}>
              Click any project marker to preview risk status &amp; launch change analysis.
            </p>
          </div>
          <span
            style={{
              padding: "3px 10px", borderRadius: "var(--radius-pill)",
              background: "var(--color-primary-bg-sub)", color: "var(--color-primary-deep)",
              fontSize: 11, fontWeight: 400, letterSpacing: "-0.39px", fontFeatureSettings: '"tnum"',
              flexShrink: 0,
            }}
          >
            {filteredProjects.length} pin{filteredProjects.length === 1 ? "" : "s"}
          </span>
        </div>

        <div style={{ padding: 16 }}>
          <ProjectMap projects={filteredProjects} />
        </div>
      </div>

      {/* ── Project Table Section ────────────────────────────────────── */}
      <div
        style={{
          background: "var(--color-canvas)",
          border: "1px solid var(--color-hairline)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-1)",
          overflow: "hidden",
        }}
      >
        {/* Controls bar */}
        <div style={{ padding: "20px 24px 16px", borderBottom: "1px solid var(--color-hairline)" }}>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h2
              style={{
                fontSize: 18, fontWeight: 300, letterSpacing: 0, lineHeight: 1.4,
                color: "var(--color-ink)", fontFeatureSettings: '"ss01"',
                display: "flex", alignItems: "center", gap: 8,
              }}
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} style={{ color: "var(--color-primary)", flexShrink: 0 }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
              Project Registry
            </h2>

            {/* Search input */}
            <div className="relative" style={{ minWidth: 240 }}>
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2"
                width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                style={{ color: "var(--color-ink-mute)" }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                id="dashboard-search"
                type="text"
                placeholder="Search projects or sector…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%", paddingLeft: 36, paddingRight: 12, paddingTop: 8, paddingBottom: 8,
                  background: "var(--color-canvas)",
                  border: "1px solid var(--color-hairline-input)",
                  borderRadius: "var(--radius-sm)",
                  fontSize: 14, fontWeight: 300, color: "var(--color-ink)",
                  outline: "none",
                  fontFeatureSettings: '"ss01"',
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-primary)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-hairline-input)"; }}
              />
            </div>
          </div>

          {/* Filter pills */}
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)", marginRight: 4 }}>Priority:</span>
            {[
              { id: "all", label: "All" },
              { id: "least", label: "Least (Red)" },
              { id: "medium", label: "Medium (Yellow)" },
              { id: "normal", label: "Normal (Green)" },
            ].map(({ id, label }) => (
              <button
                key={id}
                id={`filter-priority-${id}`}
                onClick={() => setSelectedRisk(id)}
                style={{
                  padding: "4px 12px",
                  borderRadius: "var(--radius-pill)",
                  fontSize: 11, fontWeight: 400,
                  letterSpacing: "0.1px",
                  border: selectedRisk === id ? "none" : "1px solid var(--color-hairline)",
                  background: selectedRisk === id ? "var(--color-primary-bg-sub)" : "transparent",
                  color: selectedRisk === id ? "var(--color-primary-deep)" : "var(--color-ink-mute)",
                  cursor: "pointer", transition: "all 0.15s ease",
                  fontFeatureSettings: '"ss01"',
                }}
              >
                {label}
              </button>
            ))}

            {projectTypes.length > 0 && (
              <>
                <div style={{ width: 1, height: 16, background: "var(--color-hairline)", margin: "0 4px" }} />
                <span style={{ fontSize: 12, color: "var(--color-ink-mute)", marginRight: 4 }}>Sector:</span>
                <select
                  id="filter-sector"
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                  style={{
                    background: "var(--color-canvas)", border: "1px solid var(--color-hairline)",
                    borderRadius: "var(--radius-sm)", color: "var(--color-ink)",
                    fontSize: 12, padding: "4px 8px", cursor: "pointer", outline: "none",
                    fontFeatureSettings: '"ss01"',
                  }}
                >
                  <option value="all">All Sectors</option>
                  {projectTypes.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--color-hairline)", background: "var(--color-canvas-soft)" }}>
                {["ID", "Project Name", "Sector", "Reported Progress", "Verification Priority", ""].map((col) => (
                  <th
                    key={col}
                    style={{
                      padding: "10px 20px",
                      fontSize: 10, fontWeight: 400, letterSpacing: "0.1px",
                      textTransform: "uppercase", color: "var(--color-ink-mute)",
                      fontFeatureSettings: '"ss01"',
                      textAlign: col === "" ? "right" : "left",
                    }}
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredProjects.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    style={{ padding: "48px 20px", textAlign: "center", fontSize: 14, color: "var(--color-ink-mute)" }}
                  >
                    No projects found matching current filters.
                  </td>
                </tr>
              ) : (
                filteredProjects.map((p, i) => (
                  <tr
                    key={p.id}
                    className="transition-colors"
                    style={{
                      borderBottom: i < filteredProjects.length - 1 ? "1px solid var(--color-hairline)" : "none",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-canvas-soft)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    {/* ID */}
                    <td style={{ padding: "14px 20px" }}>
                      <span
                        className="tabular"
                        style={{ fontSize: 12, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}
                      >
                        #{p.id}
                      </span>
                    </td>

                    {/* Name */}
                    <td style={{ padding: "14px 20px" }}>
                      <Link
                        href={`/projects/${p.id}`}
                        style={{
                          fontSize: 14, fontWeight: 300, color: "var(--color-primary)",
                          textDecoration: "none", letterSpacing: "-0.26px", fontFeatureSettings: '"ss01"',
                          display: "block",
                        }}
                      >
                        {p.name}
                      </Link>
                      <span
                        className="tabular"
                        style={{ fontSize: 11, color: "var(--color-ink-mute)", display: "block", marginTop: 2, fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}
                      >
                        {p.latitude.toFixed(4)}°N, {p.longitude.toFixed(4)}°E
                      </span>
                    </td>

                    {/* Sector */}
                    <td style={{ padding: "14px 20px" }}>
                      <span
                        style={{
                          padding: "3px 10px", borderRadius: "var(--radius-pill)",
                          background: "var(--color-canvas-soft)", border: "1px solid var(--color-hairline)",
                          fontSize: 12, color: "var(--color-ink-secondary)", fontFeatureSettings: '"ss01"',
                        }}
                      >
                        {p.project_type}
                      </span>
                    </td>

                    {/* Progress */}
                    <td style={{ padding: "14px 20px" }}>
                      <div style={{ width: 120 }}>
                        <div className="flex justify-between mb-1">
                          <span
                            className="tabular"
                            style={{ fontSize: 13, fontWeight: 400, color: "var(--color-ink)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.42px" }}
                          >
                            {p.reported_progress}%
                          </span>
                        </div>
                        <div
                          style={{
                            width: "100%", height: 4, borderRadius: "var(--radius-pill)",
                            background: "var(--color-hairline)", overflow: "hidden",
                          }}
                        >
                          <div
                            style={{
                              height: "100%", borderRadius: "var(--radius-pill)",
                              width: `${Math.min(100, Math.max(0, p.reported_progress))}%`,
                              background: p.reported_progress >= 80 ? "#10b981" : p.reported_progress >= 50 ? "#eab308" : "#ef4444",
                              transition: "width 0.5s ease",
                            }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Status */}
                    <td style={{ padding: "14px 20px" }}>
                      <StatusBadge status={p.status} />
                    </td>

                    {/* Action */}
                    <td style={{ padding: "14px 20px", textAlign: "right" }}>
                      <Link
                        href={`/projects/${p.id}`}
                        id={`table-analyze-${p.id}`}
                        style={{
                          display: "inline-block",
                          padding: "6px 14px", borderRadius: "var(--radius-pill)",
                          background: "var(--color-primary)", color: "var(--color-on-primary)",
                          fontSize: 12, fontWeight: 400, textDecoration: "none",
                          fontFeatureSettings: '"ss01"',
                          transition: "opacity 0.15s ease",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.85")}
                        onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
                      >
                        Analyze →
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
