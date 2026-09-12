"use client";

import { useState, useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, GeoJSON, useMap } from "react-leaflet";
import { useRouter } from "next/navigation";
import "leaflet/dist/leaflet.css";
import { ProjectSummary, GeoJSONFeatureCollection } from "@/types/project";
import StatusBadge from "./StatusBadge";
import { useTheme } from "./ThemeProvider";

// Semantic dot colors that read on the map tiles
// Least / High / Critical -> Red (#ef4444), Medium / Watch / Review -> Yellow (#eab308), Normal -> Green (#10b981)
const STATUS_COLOR: Record<string, string> = {
  normal:   "#10b981", // green
  medium:   "#eab308", // yellow
  watch:    "#eab308", // yellow
  review:   "#eab308", // yellow
  least:    "#ef4444", // red
  high:     "#ef4444", // red
  critical: "#ef4444", // red
};

function ChangeView({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

interface ProjectMapProps {
  projects: ProjectSummary[];
  geojsonOverlay?: GeoJSONFeatureCollection | null;
  selectedProjectId?: number;
}

export default function ProjectMap({ projects, geojsonOverlay, selectedProjectId }: ProjectMapProps) {
  const router = useRouter();
  const { theme } = useTheme();
  const [satelliteView, setSatelliteView] = useState(false);
  const [showChangesToggle, setShowChangesToggle] = useState(true);

  const selectedProj = projects.find((p) => p.id === selectedProjectId);
  const center: [number, number] = selectedProj
    ? [selectedProj.latitude, selectedProj.longitude]
    : projects.length > 0
    ? [projects[0].latitude, projects[0].longitude]
    : [28.47, 77.50];
  const zoomLevel = selectedProj ? 15 : 12;

  const onEachFeature = (feature: any, layer: any) => {
    if (!feature.properties) return;
    const p = feature.properties;
    const conf = (p.ai_confidence * 100).toFixed(0);
    const cv   = (p.cv_confidence  * 100).toFixed(0);
    const area = p.estimated_area_m2 ? p.estimated_area_m2.toLocaleString() : "—";
    const type = p.change_type?.replace(/_/g, " ") || "Construction";
    layer.bindPopup(`
      <div style="padding:12px 14px;min-width:180px;font-family:'Inter',system-ui,sans-serif">
        <div style="font-size:10px;font-weight:400;letter-spacing:0.1px;text-transform:uppercase;color:#64748d;margin-bottom:4px">AI Candidate</div>
        <div style="font-size:14px;font-weight:300;letter-spacing:-0.26px;color:#0d253d;margin-bottom:8px;text-transform:capitalize">${p.label || type}</div>
        <div style="display:flex;flex-direction:column;gap:4px;font-size:12px;color:#64748d;font-feature-settings:'tnum';letter-spacing:-0.39px">
          <div style="display:flex;justify-content:space-between"><span>Type</span><span style="color:#273951;font-weight:400;text-transform:capitalize">${type}</span></div>
          <div style="display:flex;justify-content:space-between"><span>AI Confidence</span><span style="color:#273951;font-weight:400">${conf}%</span></div>
          <div style="display:flex;justify-content:space-between"><span>CV Confidence</span><span style="color:#273951;font-weight:400">${cv}%</span></div>
          <div style="display:flex;justify-content:space-between"><span>Area</span><span style="color:#273951;font-weight:400">${area} m²</span></div>
        </div>
      </div>
    `);
  };

  const rawApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";
  const apiBase = rawApiUrl.replace("localhost", "127.0.0.1");

  // ─── Shared pill button style ────────────────────────────────────
  const pillBase: React.CSSProperties = {
    padding: "5px 12px",
    borderRadius: 9999,
    fontSize: 12,
    fontWeight: 400,
    lineHeight: 1,
    cursor: "pointer",
    border: "none",
    transition: "all 0.15s ease",
    fontFeatureSettings: '"ss01"',
  };

  const pillActive: React.CSSProperties = {
    ...pillBase,
    background: "var(--color-primary)",
    color: "var(--color-on-primary)",
    boxShadow: "0 2px 8px rgba(83,58,253,0.25)",
  };

  const pillInactive: React.CSSProperties = {
    ...pillBase,
    background: "transparent",
    color: "var(--color-ink-mute)",
  };

  const pillDanger: React.CSSProperties = {
    ...pillBase,
    background: showChangesToggle ? "#ea2261" : "transparent",
    color: showChangesToggle ? "#fff" : "var(--color-ink-mute)",
  };

  // Select base map tile layer matching current theme
  const lightMapTileUrl =
    process.env.NEXT_PUBLIC_MAP_LIGHT_TILE_URL ||
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
  const darkMapTileUrl =
    process.env.NEXT_PUBLIC_MAP_DARK_TILE_URL ||
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}";
  const baseMapUrl = theme === "dark" ? darkMapTileUrl : lightMapTileUrl;

  return (
    <div
      className="relative overflow-hidden"
      style={{ borderRadius: "var(--radius-lg)", border: "1px solid var(--color-hairline)" }}
    >
      {/* ── Map Control Bar ────────────────────────────────────── */}
      <div
        className="absolute top-3 right-3 z-[1000] flex items-center gap-1"
        style={{
          background: "var(--color-canvas)",
          border: "1px solid var(--color-hairline)",
          borderRadius: "var(--radius-pill)",
          padding: "4px 6px",
          boxShadow: "var(--shadow-2)",
        }}
      >
        {geojsonOverlay && (
          <>
            <button
              id="map-toggle-changes"
              onClick={() => setShowChangesToggle(!showChangesToggle)}
              style={pillDanger}
              className="flex items-center gap-1.5"
            >
              <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
              </svg>
              <span>Changes {showChangesToggle ? "ON" : "OFF"}</span>
            </button>
            <div style={{ width: 1, height: 16, background: "var(--color-hairline)", margin: "0 2px" }} />
          </>
        )}
        <button
          id="map-btn-base"
          onClick={() => setSatelliteView(false)}
          style={!satelliteView ? pillActive : pillInactive}
        >
          Map
        </button>
        <button
          id="map-btn-satellite"
          onClick={() => setSatelliteView(true)}
          style={satelliteView ? pillActive : pillInactive}
        >
          Satellite
        </button>
      </div>

      <MapContainer center={center} zoom={zoomLevel} scrollWheelZoom style={{ height: "460px", width: "100%" }}>
        <ChangeView center={center} zoom={zoomLevel} />

        {satelliteView ? (
          <TileLayer
            key="satellite-layer"
            attribution="&copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
            url={process.env.NEXT_PUBLIC_SATELLITE_TILE_URL || "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"}
          />
        ) : (
          <TileLayer
            key={`base-map-${theme}`}
            attribution='&copy; <a href="https://www.esri.com/">Esri</a> &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), and the GIS User Community'
            url={baseMapUrl}
          />
        )}

        {/* GeoJSON change candidate overlay */}
        {showChangesToggle && geojsonOverlay && geojsonOverlay.features && (
          <GeoJSON
            key={JSON.stringify(geojsonOverlay)}
            data={geojsonOverlay as any}
            style={{
              color: "#533afd",
              weight: 2,
              fillColor: "#ea2261",
              fillOpacity: 0.35,
            }}
            onEachFeature={onEachFeature}
          />
        )}

        {/* Project location markers */}
        {projects.map((p) => {
          const statusKey = p.status?.toLowerCase()?.trim() || "";
          const pinColor =
            STATUS_COLOR[statusKey] ||
            (p.reported_progress >= 80 ? "#10b981" : p.reported_progress >= 50 ? "#eab308" : "#ef4444");

          return (
            <CircleMarker
              key={p.id}
              center={[p.latitude, p.longitude]}
              radius={10}
              pathOptions={{
                color: "#fff",
                fillColor: pinColor,
                fillOpacity: 1,
                weight: 2,
              }}
            >
              <Popup>
                <div style={{ padding: "12px 14px", minWidth: 220, fontFamily: "'Inter', system-ui, sans-serif" }}>
                  {/* Header */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <h4 style={{ fontSize: 15, fontWeight: 300, letterSpacing: "-0.26px", color: "var(--color-ink)", lineHeight: 1.3 }}>
                      {p.name}
                    </h4>
                    <StatusBadge status={p.status} />
                  </div>

                  {/* Meta */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 10 }}>
                    <p className="flex items-center gap-1.5" style={{ fontSize: 11, fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px", color: "var(--color-primary)", fontWeight: 400 }}>
                      <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span>{p.latitude.toFixed(4)}°N, {p.longitude.toFixed(4)}°E</span>
                    </p>
                    <p style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>
                      <span style={{ fontWeight: 400, color: "var(--color-ink-secondary)" }}>Type:</span> {p.project_type}
                    </p>
                    <p style={{ fontSize: 12, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"', letterSpacing: "-0.39px" }}>
                      <span style={{ fontWeight: 400, color: "var(--color-ink-secondary)" }}>Progress:</span>{" "}
                      <strong style={{ color: "var(--color-primary)", fontWeight: 400 }}>{p.reported_progress}%</strong> reported
                    </p>
                  </div>

                  {/* Satellite image */}
                  <div
                    className="relative overflow-hidden"
                    style={{
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--color-hairline)",
                      background: "var(--color-canvas-soft)",
                      aspectRatio: "16/9",
                      marginBottom: 10,
                    }}
                  >
                    <img
                      src={`${apiBase}/demo-assets/project_${p.id}_after.png`}
                      alt={p.name}
                      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                    />
                    <span
                      style={{
                        position: "absolute", bottom: 5, right: 5,
                        background: "rgba(13,37,61,0.75)",
                        color: "#fff", fontSize: 9, padding: "2px 6px",
                        borderRadius: "var(--radius-xs)", fontFeatureSettings: '"tnum"',
                      }}
                    >
                      Demo image
                    </span>
                  </div>

                  {/* CTA */}
                  <button
                    onClick={() => router.push(`/projects/${p.id}`)}
                    id={`map-popup-analyze-${p.id}`}
                    style={{
                      width: "100%", display: "block", textAlign: "center",
                      padding: "8px 16px", borderRadius: "var(--radius-pill)",
                      background: "var(--color-primary)", color: "var(--color-on-primary)",
                      fontSize: 13, fontWeight: 400, lineHeight: 1, border: "none",
                      cursor: "pointer", fontFeatureSettings: '"ss01"',
                    }}
                  >
                    View Satellite Analysis →
                  </button>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* ── Priority Status Bar below map ────────────────────── */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5"
        style={{
          background: "var(--color-canvas)",
          borderTop: "1px solid var(--color-hairline)",
          fontFamily: "'Inter', system-ui, sans-serif",
        }}
      >
        <div className="flex items-center gap-4 text-xs">
          <span style={{ color: "var(--color-ink-mute)", fontWeight: 400 }}>Map Priority Legend:</span>
          <span className="flex items-center gap-1.5" style={{ color: "var(--color-ink)" }}>
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "#ef4444" }} />
            <span style={{ fontWeight: 400 }}>Least (Red)</span>
          </span>
          <span className="flex items-center gap-1.5" style={{ color: "var(--color-ink)" }}>
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "#eab308" }} />
            <span style={{ fontWeight: 400 }}>Medium (Yellow)</span>
          </span>
          <span className="flex items-center gap-1.5" style={{ color: "var(--color-ink)" }}>
            <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: "#10b981" }} />
            <span style={{ fontWeight: 400 }}>Normal (Green)</span>
          </span>
        </div>
        <div style={{ fontSize: 11, color: "var(--color-ink-mute)", fontFeatureSettings: '"tnum"' }}>
          {projects.length} project locations mapped
        </div>
      </div>
    </div>
  );
}
