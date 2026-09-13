"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { inputStyle, submitBtnStyle } from "@/components/authFormStyles";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(email, password);
      router.push(user.role === "contractor" ? "/contractor" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center" style={{ minHeight: "70vh" }}>
      <div
        style={{
          width: "100%", maxWidth: 400, padding: 32,
          background: "var(--color-canvas)", border: "1px solid var(--color-hairline)",
          borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-1)",
        }}
      >
        <h1 style={{ fontSize: 24, fontWeight: 400, color: "var(--color-ink)", marginBottom: 4, fontFamily: "var(--font-display)" }}>
          Sign in
        </h1>
        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginBottom: 24 }}>
          InfraWatch — MPLADS Infrastructure Registry
        </p>

        {error && (
          <div style={{ padding: "10px 14px", background: "var(--color-danger-bg)", border: "1px solid var(--color-danger-border)", borderRadius: "var(--radius-md)", marginBottom: 16, fontSize: 13, color: "var(--color-danger-text)" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Email</span>
            <input
              type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              style={inputStyle} placeholder="you@example.com"
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 12, color: "var(--color-ink-mute)" }}>Password</span>
            <input
              type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              style={inputStyle} placeholder="••••••••"
            />
          </label>
          <button type="submit" disabled={submitting} style={submitBtnStyle}>
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p style={{ fontSize: 13, color: "var(--color-ink-mute)", marginTop: 20, textAlign: "center" }}>
          No account? <Link href="/register" style={{ color: "var(--color-primary)" }}>Register</Link>
        </p>
      </div>
    </div>
  );
}
