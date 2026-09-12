import jsPDF from "jspdf";
import { AnalysisResult, Evidence, ProjectDetail } from "@/types/project";

const INK: [number, number, number] = [13, 37, 61];
const MUTE: [number, number, number] = [100, 116, 141];
const PRIMARY: [number, number, number] = [83, 58, 253];
const DANGER: [number, number, number] = [234, 34, 97];
const HAIRLINE: [number, number, number] = [225, 225, 232];

/** Fetches an image and returns it as a data URL, or null on any failure —
 * the report must still generate (minus the picture) if a fetch fails,
 * never throw and abandon the whole export. */
async function toDataUrl(url: string): Promise<string | null> {
  if (!url) return null;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const blob = await res.blob();
    return await new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = () => resolve(null);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

function formatDate(d?: string) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return d;
  }
}

/** Generates and downloads a field-verification PDF report for one project's
 * latest analysis. Runs entirely client-side (jsPDF) — no backend involved. */
export async function generateFieldReport(
  project: ProjectDetail,
  analysis: AnalysisResult,
  evidence: Evidence | null
): Promise<void> {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 16;
  const contentWidth = pageWidth - margin * 2;
  let y = margin;

  const ensureSpace = (needed: number) => {
    if (y + needed > pageHeight - margin) {
      doc.addPage();
      y = margin;
    }
  };

  // ── Header ──────────────────────────────────────────────
  doc.setFont("helvetica", "normal");
  doc.setFontSize(16);
  doc.setTextColor(...INK);
  doc.text("InfraWatch — Satellite Screening Report", margin, y);
  y += 6;
  doc.setFontSize(9);
  doc.setTextColor(...MUTE);
  doc.text(`SIH26102 · Generated ${new Date().toLocaleString("en-IN")}`, margin, y);
  y += 8;
  doc.setDrawColor(...HAIRLINE);
  doc.line(margin, y, pageWidth - margin, y);
  y += 8;

  // ── Project header ──────────────────────────────────────
  doc.setFontSize(14);
  doc.setTextColor(...INK);
  const nameLines = doc.splitTextToSize(project.name, contentWidth);
  doc.text(nameLines, margin, y);
  y += nameLines.length * 6 + 2;

  doc.setFontSize(9.5);
  doc.setTextColor(...MUTE);
  doc.text(
    `ID #${project.id}  ·  ${project.latitude.toFixed(4)}°N, ${project.longitude.toFixed(4)}°E  ·  ${project.project_type}`,
    margin, y
  );
  y += 8;

  // ── Metric row ──────────────────────────────────────────
  const metrics: [string, string][] = [
    ["Reported Progress", `${project.reported_progress}%`],
    ["Approved Budget", project.approved_cost ? `Rs. ${project.approved_cost.toLocaleString("en-IN")}` : "—"],
    ["T1 Baseline", formatDate(analysis.t1_scene?.acquisition_date)],
    ["T2 Observation", formatDate(analysis.t2_scene?.acquisition_date)],
  ];
  const colWidth = contentWidth / 4;
  metrics.forEach(([label, value], i) => {
    const x = margin + i * colWidth;
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTE);
    doc.text(label.toUpperCase(), x, y);
    doc.setFontSize(11);
    doc.setTextColor(...INK);
    doc.text(value, x, y + 5.5);
  });
  y += 14;
  doc.setDrawColor(...HAIRLINE);
  doc.line(margin, y, pageWidth - margin, y);
  y += 8;

  // ── Before / after images ───────────────────────────────
  const [beforeImg, afterImg] = await Promise.all([
    toDataUrl(analysis.before_image_url),
    toDataUrl(analysis.after_image_url),
  ]);

  if (beforeImg || afterImg) {
    ensureSpace(70);
    doc.setFontSize(10);
    doc.setTextColor(...INK);
    doc.text("Satellite Imagery Comparison", margin, y);
    y += 6;

    const imgSize = (contentWidth - 6) / 2;
    if (beforeImg) {
      try { doc.addImage(beforeImg, "PNG", margin, y, imgSize, imgSize); } catch { /* skip on decode failure */ }
    }
    if (afterImg) {
      try { doc.addImage(afterImg, "PNG", margin + imgSize + 6, y, imgSize, imgSize); } catch { /* skip */ }
    }
    doc.setFontSize(8);
    doc.setTextColor(...MUTE);
    doc.text(`T1 Baseline · ${formatDate(analysis.t1_scene?.acquisition_date)}`, margin, y + imgSize + 5);
    doc.text(`T2 Observation · ${formatDate(analysis.t2_scene?.acquisition_date)}`, margin + imgSize + 6, y + imgSize + 5);
    y += imgSize + 12;
  } else {
    doc.setFontSize(9);
    doc.setTextColor(...MUTE);
    doc.text("(Satellite imagery unavailable for this report)", margin, y);
    y += 8;
  }

  // ── AI summary ──────────────────────────────────────────
  ensureSpace(24);
  const ai = analysis.ai_analysis;
  doc.setFontSize(10);
  doc.setTextColor(...INK);
  doc.text(`AI Analysis (${analysis.ai_model || "model"})`, margin, y);
  y += 6;
  if (ai) {
    doc.setFontSize(9);
    doc.setTextColor(...MUTE);
    const summaryLines = doc.splitTextToSize(ai.summary, contentWidth);
    doc.text(summaryLines, margin, y);
    y += summaryLines.length * 4.5 + 2;
    doc.setTextColor(...INK);
    doc.text(`Confidence: ${(ai.confidence * 100).toFixed(0)}%`, margin, y);
    y += 8;
  }

  // ── Recommendation banner ───────────────────────────────
  ensureSpace(24);
  const severity = (evidence?.severity || "").toLowerCase();
  const bannerColor: [number, number, number] =
    severity === "field_verification" || severity === "least" || severity === "high" ? DANGER
    : severity === "normal" ? [16, 185, 129]
    : [234, 179, 8];
  doc.setFillColor(...bannerColor);
  doc.rect(margin, y, 3, 16, "F");
  doc.setFontSize(10.5);
  doc.setTextColor(...INK);
  doc.text(analysis.recommendation, margin + 6, y + 5.5);
  doc.setFontSize(8.5);
  doc.setTextColor(...MUTE);
  const explanationLines = doc.splitTextToSize(analysis.explanation, contentWidth - 6);
  doc.text(explanationLines, margin + 6, y + 11);
  y += Math.max(16, 8 + explanationLines.length * 4) + 8;

  // ── Detected change regions table ───────────────────────
  if (analysis.bounding_boxes.length > 0) {
    ensureSpace(14);
    doc.setFontSize(10);
    doc.setTextColor(...INK);
    doc.text(`Detected Change Regions (${analysis.bounding_boxes.length})`, margin, y);
    y += 6;

    const rowH = 6;
    const cols = [
      { label: "#", w: 10 },
      { label: "Type", w: 55 },
      { label: "Confidence", w: 30 },
      { label: "Est. Area (m²)", w: contentWidth - 95 },
    ];

    doc.setFontSize(8);
    doc.setTextColor(...MUTE);
    let x = margin;
    cols.forEach((c) => { doc.text(c.label, x, y); x += c.w; });
    y += 2;
    doc.setDrawColor(...HAIRLINE);
    doc.line(margin, y, pageWidth - margin, y);
    y += 4;

    const features = analysis.geojson_overlay?.features || [];
    analysis.bounding_boxes.forEach((_, i) => {
      ensureSpace(rowH + 2);
      const props = features[i]?.properties;
      const cells = [
        `${i + 1}`,
        (props?.change_type || "change").replace(/_/g, " "),
        props ? `${(props.confidence * 100).toFixed(0)}%` : "—",
        props?.estimated_area_m2 ? Math.round(props.estimated_area_m2).toLocaleString() : "—",
      ];
      doc.setFontSize(8.5);
      doc.setTextColor(...INK);
      let cx = margin;
      cells.forEach((cell, ci) => { doc.text(String(cell), cx, y); cx += cols[ci].w; });
      y += rowH;
    });
    y += 4;
  }

  // ── Footer disclaimer (every page) ──────────────────────
  const pageCount = doc.getNumberOfPages();
  for (let p = 1; p <= pageCount; p++) {
    doc.setPage(p);
    doc.setFontSize(7.5);
    doc.setTextColor(...MUTE);
    doc.text(
      "This report is a screening recommendation for human field verification only — it is not a finding of fraud or guilt.",
      margin, pageHeight - 10
    );
    doc.text(`Page ${p} of ${pageCount}`, pageWidth - margin, pageHeight - 10, { align: "right" });
  }

  const filenameSafe = project.name.replace(/[^a-z0-9]+/gi, "_").slice(0, 60);
  doc.save(`InfraWatch_Report_${project.id}_${filenameSafe}.pdf`);
}
