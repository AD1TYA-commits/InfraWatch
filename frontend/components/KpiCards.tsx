"use client";

import { KPISummary } from "@/types/project";

interface CardConfig {
  key: keyof KPISummary;
  label: string;
  subLabel: string;
  dotColor: string;
  icon: React.ReactNode;
}

const CARDS: CardConfig[] = [
  {
    key: "total_projects",
    label: "Total Projects",
    subLabel: "Monitored locations",
    dotColor: "#533afd",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
      </svg>
    ),
  },
  {
    key: "normal",
    label: "Normal Progress",
    subLabel: "On-schedule work",
    dotColor: "#10b981",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    key: "watch",
    label: "Medium Priority",
    subLabel: "Moderate variance / review",
    dotColor: "#eab308",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
  },
  {
    key: "high",
    label: "Least Priority",
    subLabel: "Field verification recommended",
    dotColor: "#ef4444",
    icon: (
      <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

export default function KpiCards({ kpi }: { kpi: KPISummary }) {
  const highRiskCount = kpi.high + (kpi.critical || 0);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map((card) => {
        const val = card.key === "high" ? highRiskCount : kpi[card.key];
        const pct =
          card.key !== "total_projects" && kpi.total_projects > 0
            ? Math.round((val / kpi.total_projects) * 100)
            : null;

        return (
          <div
            key={card.key}
            className="relative overflow-hidden transition-all duration-200 hover:-translate-y-0.5"
            style={{
              background: "var(--color-canvas)",
              border: "1px solid var(--color-hairline)",
              borderRadius: "var(--radius-lg)",
              padding: 24,
              boxShadow: "var(--shadow-1)",
            }}
          >
            {/* Header row */}
            <div className="flex items-start justify-between mb-4">
              <div>
                {/* micro-cap label */}
                <p
                  style={{
                    fontSize: 10,
                    fontWeight: 400,
                    letterSpacing: "0.1px",
                    lineHeight: 1.15,
                    textTransform: "uppercase",
                    color: "var(--color-ink-mute)",
                    fontFeatureSettings: '"ss01"',
                  }}
                >
                  {card.label}
                </p>
                <p
                  style={{
                    fontSize: 11,
                    color: "var(--color-ink-mute)",
                    marginTop: 2,
                    lineHeight: 1.4,
                    fontWeight: 300,
                  }}
                >
                  {card.subLabel}
                </p>
              </div>
              {/* Icon */}
              <div
                className="flex-shrink-0"
                style={{ color: card.dotColor, opacity: 0.85 }}
              >
                {card.icon}
              </div>
            </div>

            {/* Value row */}
            <div className="flex items-baseline justify-between">
              <span
                className="tabular"
                style={{
                  fontSize: 26,
                  fontWeight: 300,
                  letterSpacing: "-0.26px",
                  lineHeight: 1.12,
                  color: "var(--color-ink)",
                  fontFeatureSettings: '"tnum"',
                }}
              >
                {val}
              </span>

              {pct !== null && (
                <span
                  style={{
                    background: "var(--color-canvas-soft)",
                    border: "1px solid var(--color-hairline)",
                    borderRadius: "var(--radius-pill)",
                    padding: "2px 8px",
                    fontSize: 11,
                    fontWeight: 400,
                    color: "var(--color-ink-mute)",
                    fontFeatureSettings: '"tnum"',
                    letterSpacing: "-0.39px",
                  }}
                >
                  {pct}% of total
                </span>
              )}
            </div>

            {/* Bottom color accent bar */}
            <div
              className="absolute bottom-0 left-0 right-0 h-[3px] rounded-b"
              style={{ background: card.dotColor, opacity: 0.4 }}
            />
          </div>
        );
      })}
    </div>
  );
}
