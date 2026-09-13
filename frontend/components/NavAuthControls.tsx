"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";

export default function NavAuthControls() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);

  if (loading) return null;

  if (!user) {
    return (
      <div className="flex items-center gap-2">
        <Link
          href="/login"
          style={{
            padding: "7px 14px", borderRadius: "var(--radius-pill)", fontSize: 13, fontWeight: 500,
            color: "var(--color-ink)", textDecoration: "none", border: "1px solid var(--color-hairline)",
          }}
        >
          Sign in
        </Link>
        <Link
          href="/register"
          style={{
            padding: "7px 14px", borderRadius: "var(--radius-pill)", fontSize: 13, fontWeight: 500,
            background: "var(--color-primary)", color: "var(--color-on-primary)", textDecoration: "none",
          }}
        >
          Register
        </Link>
      </div>
    );
  }

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
    router.push("/login");
  };

  return (
    <div className="relative">
      <button
        onClick={() => setMenuOpen((v) => !v)}
        style={{
          display: "flex", alignItems: "center", gap: 8, padding: "6px 12px",
          borderRadius: "var(--radius-pill)", border: "1px solid var(--color-hairline)",
          background: "var(--color-canvas-soft)", cursor: "pointer",
        }}
      >
        <span
          style={{
            width: 24, height: 24, borderRadius: "50%", background: "var(--color-primary)",
            color: "var(--color-on-primary)", fontSize: 11, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          {user.full_name?.[0]?.toUpperCase() || "U"}
        </span>
        <span style={{ fontSize: 12, color: "var(--color-ink)" }}>{user.full_name}</span>
        <span
          style={{
            fontSize: 9, textTransform: "uppercase", letterSpacing: "0.05em", padding: "1px 6px",
            borderRadius: "var(--radius-pill)", background: "var(--color-gold-bg-sub)", color: "var(--color-gold-deep)",
          }}
        >
          {user.role}
        </span>
      </button>

      {menuOpen && (
        <div
          style={{
            position: "absolute", right: 0, top: "calc(100% + 6px)", minWidth: 160, zIndex: 1200,
            background: "var(--color-canvas)", border: "1px solid var(--color-hairline)",
            borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-2)", overflow: "hidden",
          }}
        >
          <Link
            href={user.role === "contractor" ? "/contractor" : "/"}
            onClick={() => setMenuOpen(false)}
            style={{ display: "block", padding: "10px 14px", fontSize: 13, color: "var(--color-ink)", textDecoration: "none" }}
          >
            {user.role === "contractor" ? "Contractor dashboard" : "Analyst dashboard"}
          </Link>
          <button
            onClick={handleLogout}
            style={{
              display: "block", width: "100%", textAlign: "left", padding: "10px 14px", fontSize: 13,
              color: "var(--color-ruby)", background: "none", border: "none", borderTop: "1px solid var(--color-hairline)", cursor: "pointer",
            }}
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
