"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { inputStyle, submitBtnStyle } from "@/components/authFormStyles";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [role, setRole] = useState<"analyst" | "contractor">("analyst");
  const [fullName, setFullName] = useState("");
  const [organization, setOrganization] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setSubmitting(true);
    try {
      const user = await register({ email, password, role, full_name: fullName, organization: organization || undefined });
      router.push(user.role === "contractor" ? "/contractor" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center" style={{ minHeight: "70vh" }}>
      <div
        style={{
          width: "100%", maxWidth: 440, padding: 32,
          background: "var(--color-canvas)", border: "1px solid var(--color-hairline)",
          borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-1)",
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 400, color: "var(--color-ink)", marginBottom: 4, fontFamily: "var(--font-display)" }}>
          Create an account
        </h1>
        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginBottom: 24 }}>
          InfraWatch — MPLADS Infrastructure Registry
        </p>

        {error && (
          <div style={{ padding: "10px 14px", background: "var(--color-danger-bg)", border: "1px solid var(--color-danger-border)", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "var(--color-danger-text)" }}>
            {error}
          </div>
        )}

        <div className="flex gap-2" style={{ marginBottom: 16 }}>
          {(["analyst", "contractor"] as const).map((r) => (
            <button
              key={r} type="button" onClick={() => setRole(r)}
              style={{
                flex: 1, padding: "10px 8px", borderRadius: "var(--radius-md)", fontSize: 13, fontWeight: 500,
                cursor: "pointer", border: role === r ? "1px solid var(--color-primary)" : "1px solid var(--color-hairline)",
                background: role === r ? "var(--color-primary-bg-sub)" : "transparent",
                color: role === r ? "var(--color-primary-deep)" : "var(--color-ink-mute)",
              }}
            >
              {r === "analyst" ? "Analyst" : "Contractor"}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 12, color: "var(--color-ink-mute)", marginTop: -10, marginBottom: 16 }}>
          {role === "analyst"
            ? "Analysts see the full project registry, review satellite evidence, and run analysis."
            : "Contractors register new projects (GPS coordinates required) or upload before/after evidence for legacy projects that have none."}
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Full name</span>
            <input required value={fullName} onChange={(e) => setFullName(e.target.value)} style={inputStyle} />
          </label>
          {role === "contractor" && (
            <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Organization (optional)</span>
              <input value={organization} onChange={(e) => setOrganization(e.target.value)} style={inputStyle} />
            </label>
          )}
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Email</span>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={inputStyle} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Password (min. 8 characters)</span>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
          </label>
          <button type="submit" disabled={submitting} style={submitBtnStyle}>
            {submitting ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginTop: 20, textAlign: "center" }}>
          Already have an account? <Link href="/login" style={{ color: "var(--color-primary)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
