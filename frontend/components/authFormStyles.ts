import type { CSSProperties } from "react";

export const inputStyle: CSSProperties = {
  padding: "9px 12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-hairline-input)",
  background: "var(--color-canvas)", color: "var(--color-ink)", fontSize: 14, outline: "none",
};

export const submitBtnStyle: CSSProperties = {
  padding: "10px 16px", borderRadius: "var(--radius-pill)", background: "var(--color-primary)",
  color: "var(--color-on-primary)", border: "none", fontSize: 14, fontWeight: 500, cursor: "pointer",
  marginTop: 6,
};
