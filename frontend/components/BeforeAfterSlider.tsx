"use client";

import { useRef, useState, useCallback } from "react";

export interface ChangeRegion {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number;
  areaM2?: number;
}

interface BeforeAfterSliderProps {
  beforeUrl: string;
  afterUrl: string;
  beforeLabel: string;
  afterLabel: string;
  /** Detected change regions, in pixel coordinates of a square image
   * `imageSizePx` wide/tall (the space the detector actually ran in) —
   * converted here to percentages so they land correctly regardless of how
   * large the slider is rendered on screen. */
  regions?: ChangeRegion[];
  imageSizePx?: number;
}

/** Drag-to-reveal before/after satellite image comparison, with detected
 * change regions highlighted on top (hover a box for type/confidence/area).
 * No extra dependencies — a clip-path on the "before" layer plus pointer events. */
export default function BeforeAfterSlider({
  beforeUrl, afterUrl, beforeLabel, afterLabel, regions = [], imageSizePx,
}: BeforeAfterSliderProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pct, setPct] = useState(50);
  const [dragging, setDragging] = useState(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const updateFromClientX = useCallback((clientX: number) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const next = ((clientX - rect.left) / rect.width) * 100;
    setPct(Math.min(100, Math.max(0, next)));
  }, []);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    setDragging(true);
    updateFromClientX(e.clientX);
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    updateFromClientX(e.clientX);
  };
  const onPointerUp = () => setDragging(false);

  const badgeStyle: React.CSSProperties = {
    position: "absolute",
    padding: "4px 10px",
    borderRadius: "var(--radius-pill)",
    background: "rgba(13,37,61,0.75)",
    color: "#fff",
    fontSize: 11,
    fontWeight: 400,
    letterSpacing: "0.1px",
    pointerEvents: "none",
  };

  return (
    <div
      ref={containerRef}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
      className="relative overflow-hidden select-none"
      style={{
        aspectRatio: "1/1",
        borderRadius: "var(--radius-lg)",
        border: "1px solid var(--color-hairline)",
        background: "var(--color-canvas-soft)",
        cursor: "ew-resize",
        touchAction: "none",
      }}
    >
      {/* Full "after" image underneath */}
      <img
        src={afterUrl}
        alt={afterLabel}
        draggable={false}
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
      />

      {/* "before" image clipped to the left of the handle */}
      <img
        src={beforeUrl}
        alt={beforeLabel}
        draggable={false}
        style={{
          position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover",
          clipPath: `inset(0 ${100 - pct}% 0 0)`,
        }}
      />

      {/* Detected change-region highlights */}
      {imageSizePx && regions.map((r) => {
        const left = (r.x / imageSizePx) * 100;
        const top = (r.y / imageSizePx) * 100;
        const w = (r.width / imageSizePx) * 100;
        const h = (r.height / imageSizePx) * 100;
        const isHovered = hoveredId === r.id;
        return (
          <div
            key={r.id}
            onPointerEnter={(e) => { e.stopPropagation(); setHoveredId(r.id); }}
            onPointerLeave={(e) => { e.stopPropagation(); setHoveredId(null); }}
            style={{
              position: "absolute",
              left: `${left}%`, top: `${top}%`, width: `${w}%`, height: `${h}%`,
              border: `2px solid ${isHovered ? "#ea2261" : "#ffcc00"}`,
              background: isHovered ? "rgba(234,34,97,0.15)" : "rgba(255,204,0,0.08)",
              borderRadius: 3,
              cursor: "pointer",
              transition: "background-color 0.15s ease, border-color 0.15s ease",
              zIndex: 5,
            }}
          >
            {isHovered && (
              <div
                style={{
                  position: "absolute",
                  bottom: "100%", left: 0, marginBottom: 4,
                  padding: "5px 9px", borderRadius: 6,
                  background: "rgba(13,37,61,0.92)", color: "#fff",
                  fontSize: 11, lineHeight: 1.4, whiteSpace: "nowrap",
                  pointerEvents: "none", boxShadow: "0 2px 8px rgba(0,0,0,0.35)",
                }}
              >
                <div style={{ fontWeight: 500, textTransform: "capitalize" }}>{r.label.replace(/_/g, " ")}</div>
                <div>Confidence: {(r.confidence * 100).toFixed(0)}%{r.areaM2 ? ` · ~${Math.round(r.areaM2).toLocaleString()} m²` : ""}</div>
              </div>
            )}
          </div>
        );
      })}

      {/* Divider line */}
      <div
        style={{
          position: "absolute", top: 0, bottom: 0, left: `${pct}%`,
          width: 2, background: "#fff", transform: "translateX(-1px)",
          boxShadow: "0 0 6px rgba(0,0,0,0.4)",
        }}
      />

      {/* Drag handle */}
      <div
        style={{
          position: "absolute", top: "50%", left: `${pct}%`,
          transform: "translate(-50%, -50%)",
          width: 32, height: 32, borderRadius: "50%",
          background: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 10px rgba(0,0,0,0.35)",
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0d253d" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7L3 12l5 5M16 7l5 5-5 5" />
        </svg>
      </div>

      <span style={{ ...badgeStyle, top: 10, left: 10 }}>{beforeLabel}</span>
      <span style={{ ...badgeStyle, top: 10, right: 10 }}>{afterLabel}</span>
    </div>
  );
}
