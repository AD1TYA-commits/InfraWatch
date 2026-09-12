import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import ThemeToggle from "@/components/ThemeToggle";

export const metadata: Metadata = {
  title: "InfraWatch — AI-Powered Infrastructure Monitoring",
  description:
    "AI-assisted decision-support system for MPLADS infrastructure anomaly and progress monitoring (SIH26102). Satellite change detection screening for human field verification.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* Inter — Stripi's open-source Sohne substitute, weights 300 + 400 */}
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>

      {/* canvas-soft page background */}
      <body
        className="min-h-screen flex flex-col antialiased transition-colors duration-200"
        style={{ background: "var(--color-canvas-soft)", color: "var(--color-ink)" }}
      >
        <ThemeProvider>
          {/* ── Navigation bar ────────────────────────────────────────── */}
          <header
            className="sticky top-0 z-[1100] transition-colors duration-200"
            style={{
              background: "var(--color-canvas)",
              borderBottom: "1px solid var(--color-hairline)",
              boxShadow: "var(--shadow-1)",
            }}
          >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
              {/* Logo */}
              <Link href="/" className="flex items-center gap-3 group" id="nav-logo">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "var(--color-primary)" }}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                  </svg>
                </div>
                <div>
                  <span
                    className="font-light tracking-tight"
                    style={{
                      fontSize: 20,
                      letterSpacing: "-0.2px",
                      color: "var(--color-ink)",
                      fontFeatureSettings: '"ss01"',
                    }}
                  >
                    InfraWatch
                  </span>
                  <p
                    className="hidden sm:block"
                    style={{ fontSize: 11, color: "var(--color-ink-mute)", letterSpacing: 0, lineHeight: 1.4 }}
                  >
                    MPLADS AI Decision-Support
                  </p>
                </div>

                {/* Version pill */}
                <span
                  className="hidden sm:inline-flex items-center px-2 py-0.5 rounded-full"
                  style={{
                    background: "var(--color-primary-bg-sub)",
                    color: "var(--color-primary-deep)",
                    fontSize: 10,
                    fontWeight: 400,
                    letterSpacing: "0.1px",
                    borderRadius: "var(--radius-pill)",
                  }}
                >
                  v0.1.0
                </span>
              </Link>

              {/* Right side nav */}
              <div className="flex items-center gap-3">
                {/* System status indicator */}
                <div
                  className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full"
                  style={{ border: "1px solid var(--color-hairline)", background: "var(--color-canvas-soft)" }}
                >
                  <span className="relative flex h-2 w-2">
                    <span
                      className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                      style={{ background: "#10b981" }}
                    />
                    <span className="relative inline-flex rounded-full h-2 w-2" style={{ background: "#10b981" }} />
                  </span>
                  <span style={{ fontSize: 11, color: "var(--color-ink-mute)", letterSpacing: "-0.39px", fontFeatureSettings: '"tnum"' }}>
                    SYSTEM READY
                  </span>
                </div>

                {/* Dark/Light mode theme toggle */}
                <ThemeToggle />

                {/* Primary CTA pill */}
                <Link
                  href="/"
                  id="nav-dashboard-btn"
                  className="transition-opacity hover:opacity-90"
                  style={{
                    padding: "8px 16px",
                    borderRadius: "var(--radius-pill)",
                    background: "var(--color-primary)",
                    color: "var(--color-on-primary)",
                    fontSize: 14,
                    fontWeight: 400,
                    lineHeight: 1,
                    letterSpacing: 0,
                    fontFeatureSettings: '"ss01"',
                    textDecoration: "none",
                    display: "inline-block",
                  }}
                >
                  Dashboard
                </Link>
              </div>
            </div>
          </header>

          {/* ── Main content ──────────────────────────────────────────── */}
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
        </ThemeProvider>


        {/* ── Footer (footer-light) ─────────────────────────────────── */}
        <footer
          style={{
            background: "var(--color-canvas)",
            borderTop: "1px solid var(--color-hairline)",
            padding: "40px 24px",
          }}
        >
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-3">
            <p style={{ fontSize: 13, color: "var(--color-ink-mute)", letterSpacing: "-0.39px", fontFeatureSettings: '"tnum"' }}>
              <span style={{ fontWeight: 400, color: "var(--color-ink-secondary)" }}>SIH26102 Decision Support Prototype</span>
              {" "}— Synthetic &amp; Sentinel-2 satellite change detection.
            </p>
            <p style={{ fontSize: 11, color: "var(--color-ink-mute)", textAlign: "right" }}>
              Outputs are recommendations for human field verification only.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
