import { RiskStatus } from "@/types/project";

// Stripi-aligned status badge styles with light and dark mode support
// Priority scheme:
// least / high / critical -> Red (#ef4444)
// medium / watch / review -> Yellow (#eab308)
// normal                  -> Green (#10b981)
interface StatusStyle {
  className: string;
  dotColor: string;
  label: string;
}

const STYLES: Record<string, StatusStyle> = {
  normal: {
    className: "bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800/60",
    dotColor: "#10b981",
    label: "Normal",
  },
  watch: {
    className: "bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60",
    dotColor: "#eab308",
    label: "Medium",
  },
  medium: {
    className: "bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60",
    dotColor: "#eab308",
    label: "Medium",
  },
  review: {
    className: "bg-amber-100 text-amber-900 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60",
    dotColor: "#eab308",
    label: "Medium",
  },
  least: {
    className: "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60",
    dotColor: "#ef4444",
    label: "Least",
  },
  high: {
    className: "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60",
    dotColor: "#ef4444",
    label: "Least",
  },
  critical: {
    className: "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60",
    dotColor: "#ef4444",
    label: "Least",
  },
};

export default function StatusBadge({ status }: { status: RiskStatus | string }) {
  const normKey = status ? status.toLowerCase().trim() : "normal";
  const cfg = STYLES[normKey] || STYLES.normal;

  return (
    <span
      className={`inline-flex items-center gap-1.5 border px-2.5 py-0.5 rounded-full text-[11px] font-normal tracking-[0.1px] leading-tight uppercase whitespace-nowrap ${cfg.className}`}
      style={{
        fontFeatureSettings: '"ss01"',
      }}
    >
      <span
        className="inline-block rounded-full flex-shrink-0"
        style={{ width: 6, height: 6, background: cfg.dotColor }}
      />
      {cfg.label}
    </span>
  );
}
