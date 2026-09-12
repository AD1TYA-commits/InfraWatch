"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { analyzeProject, getEvidence, getProject, resolveAssetUrl } from "@/lib/api";
import { generateFieldReport } from "@/lib/pdfReport";
import BeforeAfterSlider, { ChangeRegion } from "./BeforeAfterSlider";
import { AnalysisResult, Evidence, ProjectDetail } from "@/types/project";
import StatusBadge from "./StatusBadge";

const ProjectMap = dynamic(() => import("./ProjectMap"), { ssr: false });

export default function ProjectDetailView({ id }: { id: string }) {
  const [project, setProject]     = useState<ProjectDetail | null>(null);
  const [analysis, setAnalysis]   = useState<AnalysisResult | null>(null);
  const [evidence, setEvidence]   = useState<Evidence | null>(null);
  const [error, setError]         = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [activeTab, setActiveTab] = useState<"satellite" | "milestones" | "financials">("satellite");
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getProject(id)
      .then((p) => {
        setProject(p);
        getEvidence(id).then(setEvidence).catch(() => {});
        runAnalysis();
      })
      .catch((e) => setError(e.message));
  }, [id]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await analyzeProject(id);
      setAnalysis(result);
      setEvidence(await getEvidence(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis could not be completed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleIngestReal = async () => {
    setIngesting(true);
    setError(null);
    try {
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const res = await fetch(`${base}/api/projects/${id}/ingest`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Ingest failed");
      const updated = await getProject(id);
      setProject(updated);
      await runAnalysis();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sentinel-2 ingestion failed");
    } finally {
      setIngesting(false);
    }
  };

  const scrollToMap = () => {
    if (mapRef.current) mapRef.current.scrollIntoView({ behavior: "smooth" });
  };

  const handleExportPdf = async () => {
    if (!project || !analysis) return;
    setExportingPdf(true);
    setError(null);
    try {
      await generateFieldReport(project, analysis, evidence);
    } catch (e) {
      setError(e instanceof Error ? e.message : "PDF export failed");
    } finally {
      setExportingPdf(false);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "—";
    try {
      return new Date(dateStr).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" });
    } catch { return dateStr; }
  };

  // ── Error state ─────────────────────────────────────────────────
  if (error) {
    return (
      <div className="max-w-3xl mx-auto my-8 p-6" style={{ background: "#fff5f5", border: "1px solid #fecaca", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-1)" }}>
        <div className="flex items-start gap-4">
          <div className="p-2.5 rounded-lg flex-shrink-0" style={{ background: "#fee2e2", color: "#ea2261" }}>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="flex-1">
            <h3 style={{ fontSize: 16, fontWeight: 300, letterSpacing: "-0.22px", color: "var(--color-ink)", marginBottom: 6 }}>Project Telemetry Error</h3>
            <p style={{ fontSize: 14, color: "var(--color-ink-mute)", marginBottom: 12 }}>{error}</p>
            <Link href="/" style={{ padding: "7px 16px", borderRadius: "var(--radius-pill)", background: "var(--color-primary)", color: "#fff", fontSize: 13, fontWeight: 400, textDecoration: "none" }}>
              ← Return to Dashboard
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Loading state ───────────────────────────────────────────────
  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <div
          className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: "var(--color-primary)" }}
        />
        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", letterSpacing: "-0.39px", fontFeatureSettings: '"tnum"' }}>
          Loading project #{id} dataset…
        </p>
      </div>
    );
  }

  const t1 = analysis?.t1_scene;
  const t2 = analysis?.t2_scene;
  const ai = analysis?.ai_analysis;

  // The image space the detector actually ran in — bounding_boxes are in
  // these pixel coordinates (assumes a square analyzed image, true for both
  // the demo-mode and satellite-service pipelines).
  const imageSizePx = analysis?.total_pixel_count ? Math.round(Math.sqrt(analysis.total_pixel_count)) : undefined;

  // Match each bounding box to its richer GeoJSON properties (type/confidence/area) —
  // both arrays are built from the same ordered candidate list server-side.
  const changeRegions: ChangeRegion[] = (analysis?.bounding_boxes || []).map((box, i) => {
    const feature = analysis?.geojson_overlay?.features?.[i];
    const props = feature?.properties;
    return {
      id: feature?.id || `region-${i}`,
      x: box.x, y: box.y, width: box.width, height: box.height,
      label: props?.change_type || "change",
      confidence: props?.confidence ?? props?.ai_confidence ?? 0,
      areaM2: props?.estimated_area_m2,
    };
  });

  // ── Shared card style ────────────────────────────────────────────
  const cardStyle: React.CSSProperties = {
    background: "var(--color-canvas)",
    border: "1px solid var(--color-hairline)",
    borderRadius: "var(--radius-lg)",
    boxShadow: "var(--shadow-1)",
  };

  const pillBtn: React.CSSProperties = {
    padding: "8px 16px", borderRadius: "var(--radius-pill)",
    fontSize: 14, fontWeight: 400, lineHeight: 1, border: "none", cursor: "pointer",
    fontFeatureSettings: '"ss01"', transition: "opacity 0.15s ease",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Breadcrumb & Header ──────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <Link
            href="/"
            style={{ fontSize: 13, color: "var(--color-primary)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 10 }}
          >
            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Infrastructure Registry
          </Link>

          <div className="flex items-center gap-3 flex-wrap">
            <h1
              style={{
                fontSize: 32, fontWeight: 300, letterSpacing: "-0.64px", lineHeight: 1.1,
                color: "var(--color-ink)", fontFeatureSettings: '"ss01"',
              }}
            >
              {project.name}
            </h1>
            <StatusBadge status={project.status} />
          </div>

          <p
            className="tabular flex flex-wrap gap-x-3 mt-2"
            style={{ fontSize: 12, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}
          >
            <span>ID #{project.id}</span>
            <span>·</span>
            <span>{project.latitude.toFixed(4)}°N, {project.longitude.toFixed(4)}°E</span>
            <span>·</span>
            <span style={{ color: "var(--color-primary)", fontWeight: 400 }}>{project.project_type}</span>
          </p>
        </div>

        {/* Fetch Sentinel-2 button */}
        <div className="flex items-center gap-2">
          <button
            id="detail-ingest-btn"
            onClick={handleIngestReal}
            disabled={ingesting || analyzing}
            style={{
              ...pillBtn,
              background: "var(--color-canvas)",
              color: "var(--color-ink)",
              border: "1px solid var(--color-hairline)",
              display: "flex", alignItems: "center", gap: 8,
              opacity: ingesting || analyzing ? 0.5 : 1,
            }}
          >
            {ingesting ? (
              <>
                <span className="w-3 h-3 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: "var(--color-primary)" }} />
                Querying STAC (2026)...
              </>
            ) : (
              <>
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: "var(--color-primary)" }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
                Fetch Latest Sentinel-2 (STAC)
              </>
            )}
          </button>

          <button
            id="detail-export-pdf-btn"
            onClick={handleExportPdf}
            disabled={exportingPdf || !analysis}
            style={{
              ...pillBtn,
              background: "var(--color-canvas)",
              color: "var(--color-ink)",
              border: "1px solid var(--color-hairline)",
              display: "flex", alignItems: "center", gap: 8,
              opacity: exportingPdf || !analysis ? 0.5 : 1,
            }}
          >
            {exportingPdf ? (
              <>
                <span className="w-3 h-3 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: "var(--color-primary)" }} />
                Generating PDF...
              </>
            ) : (
              <>
                <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: "var(--color-primary)" }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3M12 4a8 8 0 100 16 8 8 0 000-16z" />
                </svg>
                Export Report (PDF)
              </>
            )}
          </button>
        </div>
      </div>

      {/* ── Overview Metric Cards ────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Reported Progress */}
        <div style={{ ...cardStyle, padding: 20 }}>
          <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>Reported Progress</p>
          <span className="tabular" style={{ fontSize: 26, fontWeight: 300, letterSpacing: "-0.26px", color: "var(--color-ink)", fontFeatureSettings: '"tnum"' }}>
            {project.reported_progress}%
          </span>
          <p style={{ fontSize: 10, color: "var(--color-ink-mute)", marginTop: 2 }}>Official Claim</p>
          <div style={{ width: "100%", height: 3, borderRadius: "var(--radius-pill)", background: "var(--color-hairline)", overflow: "hidden", marginTop: 10 }}>
            <div style={{ height: "100%", borderRadius: "var(--radius-pill)", width: `${Math.min(100, Math.max(0, project.reported_progress))}%`, background: "var(--color-primary)" }} />
          </div>
        </div>

        {/* Approved Budget */}
        <div style={{ ...cardStyle, padding: 20 }}>
          <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>Approved Budget</p>
          <p className="tabular" style={{ fontSize: 22, fontWeight: 300, letterSpacing: "-0.22px", color: "var(--color-ink)", fontFeatureSettings: '"tnum"' }}>
            {project.approved_cost ? `₹${project.approved_cost.toLocaleString("en-IN")}` : "—"}
          </p>
          <p style={{ fontSize: 10, color: "var(--color-ink-mute)", marginTop: 2 }}>MPLADS Sanction</p>
        </div>

        {/* T1 Baseline */}
        <div style={{ ...cardStyle, padding: 20 }}>
          <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>T1 Baseline Date</p>
          <p style={{ fontSize: 18, fontWeight: 300, letterSpacing: 0, color: "var(--color-ink)" }}>{formatDate(t1?.acquisition_date)}</p>
          <p style={{ fontSize: 10, color: "var(--color-ink-mute)", marginTop: 2 }}>{t1?.source || "Sentinel-2"}</p>
        </div>

        {/* T2 Observation */}
        <div style={{ ...cardStyle, padding: 20 }}>
          <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>T2 Latest Observation</p>
          <p className="tabular" style={{ fontSize: 18, fontWeight: 300, letterSpacing: 0, color: "var(--color-primary)", fontFeatureSettings: '"tnum"' }}>{formatDate(t2?.acquisition_date)}</p>
          <p style={{ fontSize: 10, color: "var(--color-ink-mute)", marginTop: 2 }}>{t2?.source || "Sentinel-2"}</p>
        </div>
      </div>

      {/* ── Project Scope ────────────────────────────────────────── */}
      <div style={{ ...cardStyle, padding: 20 }}>
        <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>Project Scope</p>
        <p style={{ fontSize: 15, fontWeight: 300, color: "var(--color-ink-secondary)", lineHeight: 1.5 }}>
          {project.description || "No description provided."}
        </p>
      </div>

      {/* ── Main Tab Panel ───────────────────────────────────────── */}
      <div style={{ ...cardStyle, overflow: "hidden" }}>
        {/* Tab header */}
        <div style={{ display: "flex", borderBottom: "1px solid var(--color-hairline)", padding: "8px 12px", gap: 6, background: "var(--color-canvas-soft)" }}>
          {[
            {
              id: "satellite",
              label: "AI Satellite Screening",
              icon: (
                <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              ),
            },
            {
              id: "milestones",
              label: `Milestones (${project.milestones?.length || 0})`,
              icon: (
                <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              ),
            },
            {
              id: "financials",
              label: `Financials (${project.financial_records?.length || 0})`,
              icon: (
                <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              ),
            },
          ].map((tab) => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                padding: "7px 16px", borderRadius: "var(--radius-pill)",
                fontSize: 13, fontWeight: 400, border: "none", cursor: "pointer",
                display: "flex", alignItems: "center", gap: 6,
                background: activeTab === tab.id ? "var(--color-primary)" : "transparent",
                color: activeTab === tab.id ? "var(--color-on-primary)" : "var(--color-ink-mute)",
                boxShadow: activeTab === tab.id ? "0 2px 8px rgba(83,58,253,0.25)" : "none",
                transition: "all 0.15s ease",
                fontFeatureSettings: '"ss01"',
              }}
            >
              <span className="flex items-center">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div style={{ padding: 24 }}>

          {/* ── Satellite Tab ──────────────────────────────────── */}
          {activeTab === "satellite" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

              {/* Control bar */}
              <div
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
                style={{ padding: 16, background: "var(--color-canvas-soft)", border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-md)" }}
              >
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 style={{ fontSize: 15, fontWeight: 300, letterSpacing: "-0.26px", color: "var(--color-ink)" }}>
                      Multimodal AI Vision &amp; GeoJSON Engine
                    </h4>
                    <span
                      style={{
                        padding: "2px 8px", borderRadius: "var(--radius-pill)",
                        background: "var(--color-primary-bg-sub)", color: "var(--color-primary-deep)",
                        fontSize: 10, fontWeight: 400, letterSpacing: "0.1px",
                      }}
                    >
                      {analysis?.ai_model || "gemini-2.5-flash-lite"}
                    </span>
                  </div>
                  <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginTop: 4 }}>
                    Extracts candidate crops via local OpenCV, applies Gemini Vision AI reasoning, and projects GeoJSON change polygons onto the map.
                  </p>
                </div>

                <button
                  id="btn-run-analysis"
                  onClick={runAnalysis}
                  disabled={analyzing}
                  style={{
                    ...pillBtn,
                    background: "var(--color-primary)", color: "var(--color-on-primary)",
                    display: "flex", alignItems: "center", gap: 8,
                    opacity: analyzing ? 0.6 : 1, flexShrink: 0,
                    boxShadow: "0 2px 10px rgba(83,58,253,0.3)",
                  }}
                >
                  {analyzing ? (
                    <>
                      <span className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      Analyzing Candidate Crops...
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      {analysis ? "Run Analysis Again" : "Run Image Analysis"}
                    </>
                  )}
                </button>
              </div>

              {/* Analysis results */}
              {analysis && (
                <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

                  {/* Status strip */}
                  <div
                    className="flex flex-wrap items-center justify-between gap-2"
                    style={{ padding: "10px 14px", background: "var(--color-canvas-soft)", border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-md)" }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full animate-pulse" style={{ background: "#10b981" }} />
                      <span style={{ fontSize: 12, color: "var(--color-ink-secondary)", fontWeight: 400 }}>Image comparison ready</span>
                    </div>
                    <span className="tabular" style={{ fontSize: 12, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                      {project.latitude.toFixed(4)}°N, {project.longitude.toFixed(4)}°E
                    </span>
                  </div>

                  {/* Before / after satellite image comparison */}
                  {analysis.before_image_url && analysis.after_image_url && (
                    <div>
                      <BeforeAfterSlider
                        beforeUrl={resolveAssetUrl(analysis.before_image_url)}
                        afterUrl={resolveAssetUrl(analysis.after_image_url)}
                        beforeLabel={`T1 · ${formatDate(t1?.acquisition_date)}`}
                        afterLabel={`T2 · ${formatDate(t2?.acquisition_date)}`}
                        regions={changeRegions}
                        imageSizePx={imageSizePx}
                      />
                      <p style={{ fontSize: 11, color: "var(--color-ink-mute)", marginTop: 8, textAlign: "center" }}>
                        Drag the handle to compare the baseline (T1) and latest observation (T2) satellite scenes.
                        {changeRegions.length > 0 && " Hover a highlighted region for details."}
                      </p>
                    </div>
                  )}

                  {/* AI reasoning box */}
                  {ai && (
                    <div style={{ border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
                      {/* AI panel header */}
                      <div
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                        style={{ padding: "14px 20px", borderBottom: "1px solid var(--color-hairline)", background: "var(--color-canvas-soft)" }}
                      >
                        <div className="flex items-center gap-2.5">
                          <span
                            className="flex items-center justify-center p-1.5 rounded"
                            style={{
                              background: "var(--color-primary-bg-sub)",
                              color: "var(--color-primary-deep)",
                            }}
                          >
                            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                            </svg>
                          </span>
                          <div>
                            <h4 style={{ fontSize: 14, fontWeight: 300, letterSpacing: "-0.26px", color: "var(--color-ink)" }}>
                              Gemini Vision AI Analysis
                            </h4>
                            <p className="tabular" style={{ fontSize: 11, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                              Model: {analysis.ai_model || "gemini-2.5-flash-lite"}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <div style={{ textAlign: "right" }}>
                            <span style={{ fontSize: 10, color: "var(--color-ink-mute)", display: "block", textTransform: "uppercase", letterSpacing: "0.1px" }}>AI Confidence</span>
                            <span className="tabular" style={{ fontSize: 20, fontWeight: 300, letterSpacing: "-0.26px", color: "var(--color-primary)", fontFeatureSettings: '"tnum"' }}>
                              {(ai.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          <button
                            id="btn-view-changes-map"
                            onClick={scrollToMap}
                            style={{
                              ...pillBtn,
                              background: "#ea2261", color: "#fff",
                              display: "flex", alignItems: "center", gap: 6,
                              boxShadow: "0 2px 8px rgba(234,34,97,0.3)",
                            }}
                          >
                            <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <circle cx="12" cy="12" r="10" />
                              <circle cx="12" cy="12" r="6" />
                              <circle cx="12" cy="12" r="2" />
                            </svg>
                            View Changes on Map ↓
                          </button>
                        </div>
                      </div>

                      {/* AI body */}
                      <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 16 }}>
                        <p style={{ fontSize: 15, fontWeight: 300, color: "var(--color-ink-secondary)", lineHeight: 1.6 }}>{ai.summary}</p>

                        {ai.changes && ai.changes.length > 0 && (
                          <div>
                            <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 8 }}>
                              Detected Change Categories
                            </p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {ai.changes.map((ch, idx) => (
                                <div
                                  key={idx}
                                  style={{ padding: "12px 14px", border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-md)", display: "flex", alignItems: "flex-start", gap: 10, background: "var(--color-canvas-soft)" }}
                                >
                                  <span
                                    style={{
                                      padding: "2px 8px", borderRadius: "var(--radius-pill)", flexShrink: 0,
                                      background: "var(--color-primary-bg-sub)", color: "var(--color-primary-deep)",
                                      fontSize: 10, fontWeight: 400, textTransform: "uppercase", letterSpacing: "0.1px",
                                    }}
                                  >
                                    {ch.type.replace(/_/g, " ")}
                                  </span>
                                  <div className="flex-1">
                                    <div className="flex items-center justify-between mb-1">
                                      <span style={{ fontSize: 13, fontWeight: 300, color: "var(--color-ink)", textTransform: "capitalize" }}>
                                        {ch.type.replace(/_/g, " ")}
                                      </span>
                                      <span className="tabular" style={{ fontSize: 13, fontWeight: 400, color: "var(--color-primary)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                                        {(ch.confidence * 100).toFixed(0)}%
                                      </span>
                                    </div>
                                    <p style={{ fontSize: 12, color: "var(--color-ink-mute)", lineHeight: 1.4 }}>{ch.description}</p>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* False positive risks */}
                        {ai.false_positive_risks && ai.false_positive_risks.length > 0 && (
                          <div className="flex items-center gap-2 flex-wrap" style={{ paddingTop: 12, borderTop: "1px solid var(--color-hairline)" }}>
                            <span style={{ fontSize: 11, color: "var(--color-ink-mute)" }}>False-Positive Risks Evaluated:</span>
                            {ai.false_positive_risks.map((risk, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-normal border bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60"
                              >
                                <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} className="flex-shrink-0">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span>{risk}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Recommendation banner — Verification Priority Scheme */}
                  {(() => {
                    const statusStr = project.status?.toLowerCase() || "";
                    const recStr = analysis.recommendation?.toLowerCase() || "";
                    const isHigh = statusStr === "least" || statusStr === "high" || statusStr === "critical" || recStr.includes("field verification");
                    const isReview = statusStr === "watch" || statusStr === "medium" || statusStr === "review" || recStr.includes("review");
                    const accentColor = isHigh ? "#ef4444" : isReview ? "#eab308" : "#10b981";
                    const priorityLabel = isHigh ? "Least Priority" : isReview ? "Medium Priority" : "Normal Priority";

                    return (
                      <div
                        className="rounded-xl border p-4 sm:p-5 flex items-start gap-3 transition-colors"
                        style={{
                          background: "var(--color-canvas-cream)",
                          borderColor: "var(--color-hairline)",
                        }}
                      >
                        <div
                          className="p-2 rounded-lg flex-shrink-0"
                          style={{
                            background: `${accentColor}18`,
                            color: accentColor,
                          }}
                        >
                          <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                            <span
                              className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full"
                              style={{
                                background: `${accentColor}20`,
                                color: accentColor,
                              }}
                            >
                              {priorityLabel}
                            </span>
                          </div>
                          <h4 style={{ fontSize: 15, fontWeight: 400, letterSpacing: "-0.26px", color: "var(--color-ink)", marginBottom: 4 }}>
                            {analysis.recommendation}
                          </h4>
                          <p style={{ fontSize: 13, color: "var(--color-ink-secondary)", lineHeight: 1.5 }}>
                            {analysis.explanation}
                          </p>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Interactive map */}
                  <div ref={mapRef} style={{ paddingTop: 4 }}>
                    <div className="flex items-center justify-between mb-3">
                      <h4 style={{ fontSize: 13, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)" }}>
                        Interactive Geospatial Map &amp; GeoJSON Candidate Overlay
                      </h4>
                      <span className="tabular" style={{ fontSize: 11, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>EPSG:4326</span>
                    </div>
                    <ProjectMap
                      projects={[project]}
                      geojsonOverlay={analysis.geojson_overlay}
                      selectedProjectId={project.id}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Milestones Tab ──────────────────────────────────── */}
          {activeTab === "milestones" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 4 }}>
                Target Schedule &amp; Milestones
              </p>
              {!project.milestones || project.milestones.length === 0 ? (
                <p style={{ fontSize: 13, color: "var(--color-ink-mute)", textAlign: "center", padding: "48px 0" }}>
                  No milestones recorded for this project.
                </p>
              ) : (
                project.milestones.map((m) => (
                  <div
                    key={m.id}
                    className="flex items-center justify-between gap-4"
                    style={{ padding: "14px 16px", border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-md)", background: "var(--color-canvas-soft)" }}
                  >
                    <div>
                      <p style={{ fontSize: 14, fontWeight: 300, color: "var(--color-ink)" }}>{m.description}</p>
                      <p className="tabular" style={{ fontSize: 11, color: "var(--color-ink-mute)", marginTop: 2, fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                        Target: {formatDate(m.milestone_date)}
                      </p>
                    </div>
                    <span className="tabular" style={{ fontSize: 14, fontWeight: 400, color: "var(--color-primary)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.42px", flexShrink: 0 }}>
                      {m.expected_progress}% expected
                    </span>
                  </div>
                ))
              )}
            </div>
          )}

          {/* ── Financials Tab ──────────────────────────────────── */}
          {activeTab === "financials" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <p style={{ fontSize: 10, fontWeight: 400, letterSpacing: "0.1px", textTransform: "uppercase", color: "var(--color-ink-mute)", marginBottom: 4 }}>
                Disbursement &amp; Expenditure Log
              </p>
              {!project.financial_records || project.financial_records.length === 0 ? (
                <p style={{ fontSize: 13, color: "var(--color-ink-mute)", textAlign: "center", padding: "48px 0" }}>
                  No financial records recorded for this project.
                </p>
              ) : (
                project.financial_records.map((f) => (
                  <div
                    key={f.id}
                    className="flex items-center justify-between gap-4"
                    style={{ padding: "14px 16px", border: "1px solid var(--color-hairline)", borderRadius: "var(--radius-md)", background: "var(--color-canvas-soft)" }}
                  >
                    <div>
                      <p style={{ fontSize: 14, fontWeight: 300, color: "var(--color-ink)" }}>{f.category}</p>
                      <p className="tabular" style={{ fontSize: 11, color: "var(--color-ink-mute)", marginTop: 2, fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                        Disbursed: {formatDate(f.date)}
                      </p>
                    </div>
                    <span className="tabular" style={{ fontSize: 16, fontWeight: 400, color: "var(--color-ink)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.42px", flexShrink: 0 }}>
                      ₹{f.amount.toLocaleString("en-IN")}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
