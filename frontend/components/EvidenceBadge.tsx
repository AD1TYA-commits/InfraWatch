import { EvidenceSource } from "@/types/project";

// Distinguishes how a project's before/after evidence was actually obtained —
// a real Sentinel-2 satellite pass vs. a contractor-supplied photo comparison
// vs. nothing on record yet. Kept as one shared component so this shows up
// identically everywhere (registry table, map popups, project detail).
interface EvidenceStyle {
  label: string;
  shortLabel: string;
  icon: string;
  className: string;
}

const STYLES: Record<string, EvidenceStyle> = {
  satellite: {
    label: "Satellite (GIS-verified)",
    shortLabel: "Satellite",
    icon: "\u{1F6F0}️", // 🛰️
    className: "bg-sky-100 text-sky-900 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800/60",
  },
  manual_upload: {
    label: "Manual Photo Comparison",
    shortLabel: "Manual Upload",
    icon: "\u{1F4F7}", // 📷
    className: "bg-violet-100 text-violet-900 border-violet-200 dark:bg-violet-950/60 dark:text-violet-300 dark:border-violet-800/60",
  },
  unavailable: {
    label: "Awaiting Evidence",
    shortLabel: "No Evidence Yet",
    icon: "—", // —
    className: "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/60 dark:text-slate-400 dark:border-slate-700/60",
  },
};

export default function EvidenceBadge({
  source,
  compact = false,
}: {
  source: EvidenceSource | string | null | undefined;
  compact?: boolean;
}) {
  const key = (source || "unavailable").toLowerCase();
  const cfg = STYLES[key] || STYLES.unavailable;

  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2.5 py-0.5 rounded-full text-[11px] font-normal tracking-[0.1px] leading-tight whitespace-nowrap ${cfg.className}`}
      style={{ fontFeatureSettings: '"ss01"' }}
      title={cfg.label}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {compact ? cfg.shortLabel : cfg.label}
    </span>
  );
}
