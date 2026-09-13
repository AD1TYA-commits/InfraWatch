"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/components/AuthProvider";
import { getMyProjects, createProject, uploadManualEvidence, getProjects } from "@/lib/api";
import { ProjectSummary } from "@/types/project";

const cardStyle: React.CSSProperties = {
  background: "var(--color-canvas)", border: "1px solid var(--color-hairline)",
  borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-1)", padding: 24,
};
const inputStyle: React.CSSProperties = {
  padding: "9px 12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-hairline-input)",
  background: "var(--color-canvas)", color: "var(--color-ink)", fontSize: 14, outline: "none", width: "100%",
};
const labelStyle: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--color-ink-mute)" };
const btnStyle: React.CSSProperties = {
  padding: "9px 18px", borderRadius: "var(--radius-pill)", background: "var(--color-primary)",
  color: "var(--color-on-primary)", border: "none", fontSize: 13, fontWeight: 500, cursor: "pointer",
};
const tabBtn = (active: boolean): React.CSSProperties => ({
  padding: "8px 16px", borderRadius: "var(--radius-pill)", fontSize: 13, fontWeight: 500, cursor: "pointer",
  border: "none", background: active ? "var(--color-primary)" : "transparent",
  color: active ? "var(--color-on-primary)" : "var(--color-ink-mute)",
});

export default function ContractorPage() {
  const { user, loading } = useRequireAuth("contractor");
  const [tab, setTab] = useState<"mine" | "register" | "evidence">("mine");
  const [myProjects, setMyProjects] = useState<ProjectSummary[] | null>(null);

  const refreshMine = () => getMyProjects().then(setMyProjects).catch(() => setMyProjects([]));

  useEffect(() => {
    if (user) refreshMine();
  }, [user]);

  if (loading || !user) {
    return <p style={{ padding: 40, textAlign: "center", color: "var(--color-ink-mute)" }}>Loading...</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 26, fontWeight: 400, color: "var(--color-ink)", fontFamily: "var(--font-display)" }}>
          Contractor Dashboard
        </h1>
        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginTop: 4 }}>
          Welcome, {user.full_name}{user.organization ? ` · ${user.organization}` : ""}
        </p>
      </div>

      <div className="flex gap-2">
        <button style={tabBtn(tab === "mine")} onClick={() => setTab("mine")}>My Projects</button>
        <button style={tabBtn(tab === "register")} onClick={() => setTab("register")}>Register New Project</button>
        <button style={tabBtn(tab === "evidence")} onClick={() => setTab("evidence")}>Upload Evidence</button>
      </div>

      {tab === "mine" && <MyProjectsTab projects={myProjects} />}
      {tab === "register" && <RegisterProjectTab onCreated={() => { refreshMine(); setTab("mine"); }} />}
      {tab === "evidence" && <UploadEvidenceTab onUploaded={refreshMine} />}
    </div>
  );
}

function MyProjectsTab({ projects }: { projects: ProjectSummary[] | null }) {
  if (projects === null) return <p style={{ color: "var(--color-ink-mute)" }}>Loading...</p>;
  if (projects.length === 0) {
    return (
      <div style={cardStyle}>
        <p style={{ color: "var(--color-ink-mute)", fontSize: 14 }}>
          You haven&apos;t registered any projects yet — use &quot;Register New Project&quot; above.
        </p>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {projects.map((p) => (
        <Link
          key={p.id} href={`/projects/${p.id}`}
          style={{ ...cardStyle, display: "block", textDecoration: "none", padding: 16 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p style={{ fontSize: 15, color: "var(--color-ink)", fontWeight: 500 }}>{p.name}</p>
              <p style={{ fontSize: 12, color: "var(--color-ink-mute)", marginTop: 2 }}>
                {p.project_type} · {p.evidence_source === "satellite" ? "Satellite-screened" : p.evidence_source === "manual_upload" ? "Manual evidence" : "Awaiting evidence"}
              </p>
            </div>
            <span style={{ fontSize: 13, color: "var(--color-primary)" }}>View →</span>
          </div>
        </Link>
      ))}
    </div>
  );
}

function RegisterProjectTab({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState({ name: "", project_type: "Roads", description: "", latitude: "", longitude: "", reported_progress: "0" });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    const lat = parseFloat(form.latitude);
    const lon = parseFloat(form.longitude);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      setError("Latitude and longitude are required and must be valid numbers — every new project gets real satellite screening from day one.");
      return;
    }
    setSubmitting(true);
    try {
      await createProject({
        name: form.name, project_type: form.project_type, description: form.description,
        latitude: lat, longitude: lon, reported_progress: parseFloat(form.reported_progress) || 0,
      });
      setSuccess(true);
      setForm({ name: "", project_type: "Roads", description: "", latitude: "", longitude: "", reported_progress: "0" });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={cardStyle}>
      <h2 style={{ fontSize: 16, fontWeight: 500, color: "var(--color-ink)", marginBottom: 4 }}>Register a new project</h2>
      <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginBottom: 20 }}>
        GPS coordinates are mandatory here — every new project is real-satellite-screened automatically from the moment it&apos;s created.
        For an existing project with no coordinate on record, use &quot;Upload Evidence&quot; instead.
      </p>
      {error && <div style={{ padding: "10px 14px", background: "var(--color-danger-bg)", border: "1px solid var(--color-danger-border)", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "var(--color-danger-text)" }}>{error}</div>}
      {success && <div style={{ padding: "10px 14px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "#166534" }}>Project registered — check &quot;My Projects&quot;.</div>}
      <form onSubmit={handleSubmit} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <label style={{ ...labelStyle, gridColumn: "1 / -1" }}>
          <span>Project name</span>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={inputStyle} />
        </label>
        <label style={labelStyle}>
          <span>Sector</span>
          <select value={form.project_type} onChange={(e) => setForm({ ...form, project_type: e.target.value })} style={inputStyle}>
            {["Roads", "Healthcare", "Education", "Water Supply", "Public Buildings", "Sports & Recreation", "Agriculture"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label style={labelStyle}>
          <span>Reported progress (%)</span>
          <input type="number" min={0} max={100} value={form.reported_progress} onChange={(e) => setForm({ ...form, reported_progress: e.target.value })} style={inputStyle} />
        </label>
        <label style={labelStyle}>
          <span>Latitude</span>
          <input required type="number" step="any" placeholder="e.g. 28.6139" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} style={inputStyle} />
        </label>
        <label style={labelStyle}>
          <span>Longitude</span>
          <input required type="number" step="any" placeholder="e.g. 77.2090" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} style={inputStyle} />
        </label>
        <label style={{ ...labelStyle, gridColumn: "1 / -1" }}>
          <span>Description</span>
          <textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} style={{ ...inputStyle, resize: "vertical" }} />
        </label>
        <div style={{ gridColumn: "1 / -1" }}>
          <button type="submit" disabled={submitting} style={btnStyle}>{submitting ? "Registering..." : "Register project"}</button>
        </div>
      </form>
    </div>
  );
}

function UploadEvidenceTab({ onUploaded }: { onUploaded: () => void }) {
  const [candidates, setCandidates] = useState<ProjectSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [before, setBefore] = useState<File | null>(null);
  const [after, setAfter] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getProjects({ evidence_source: "unavailable", page_size: 100 }).then(setCandidates).catch(() => setCandidates([]));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!selectedId || !before || !after) {
      setError("Choose a project and both a before and after photo.");
      return;
    }
    setSubmitting(true);
    try {
      const res: any = await uploadManualEvidence(selectedId, before, after);
      setResult(`Uploaded. Model detected ${res.observable_change_percent}% observable change across ${res.candidate_count} region(s).`);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={cardStyle}>
      <h2 style={{ fontSize: 16, fontWeight: 500, color: "var(--color-ink)", marginBottom: 4 }}>Upload before/after evidence</h2>
      <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginBottom: 20 }}>
        For a legacy project with no GPS coordinate on record — a common situation for older, already-registered
        works. Upload two photos (e.g. Google Maps/Earth screenshots) showing the site before and after. The same
        real change-detection model used for satellite imagery scores these — not a placeholder number.
      </p>
      {error && <div style={{ padding: "10px 14px", background: "var(--color-danger-bg)", border: "1px solid var(--color-danger-border)", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "var(--color-danger-text)" }}>{error}</div>}
      {result && <div style={{ padding: "10px 14px", background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "#166534" }}>{result}</div>}
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <label style={labelStyle}>
          <span>Project (no coordinate on record)</span>
          <select required value={selectedId ?? ""} onChange={(e) => setSelectedId(Number(e.target.value))} style={inputStyle}>
            <option value="" disabled>Select a project...</option>
            {(candidates || []).map((p) => (
              <option key={p.id} value={p.id}>#{p.id} — {p.name}</option>
            ))}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label style={labelStyle}>
            <span>Before photo</span>
            <input required type="file" accept="image/*" onChange={(e) => setBefore(e.target.files?.[0] || null)} style={inputStyle} />
          </label>
          <label style={labelStyle}>
            <span>After photo</span>
            <input required type="file" accept="image/*" onChange={(e) => setAfter(e.target.files?.[0] || null)} style={inputStyle} />
          </label>
        </div>
        <div>
          <button type="submit" disabled={submitting} style={btnStyle}>{submitting ? "Analyzing (this can take up to a minute)..." : "Upload & analyze"}</button>
        </div>
      </form>
    </div>
  );
}
