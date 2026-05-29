export const pageContainerStyle = {
  maxWidth: 1280,
  margin: "0 auto",
  padding: "0 8px 24px",
};

export const pageHeaderStyle = {
  marginBottom: 20,
};

export const pageTitleStyle = {
  margin: 0,
  color: "#e5e7eb",
};

export const pageDescriptionStyle = {
  fontSize: 14,
  marginTop: 8,
  color: "#9ca3af",
};

export const gradientHeaderStyle = {
  background: "linear-gradient(135deg, #1e3a5f, #0f172a)",
  border: "1px solid #1e293b",
};

export const cardStyle = {
  borderRadius: 12,
  border: "1px solid #1e293b",
  boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
  background: "#111827",
};

export const softCardStyle = {
  borderRadius: 12,
  border: "1px solid #1e293b",
  boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
  background: "#0f1720",
};

export const mutedTextStyle = {
  color: "#9ca3af",
};

export const sectionCardBodyStyle = {
  padding: "18px 22px",
};

export const metricTileStyle = {
  padding: "14px 16px",
  background: "#1a2332",
  border: "1px solid #1e293b",
  borderRadius: 10,
  textAlign: "center" as const,
};

export const tagStyle = {
  marginBottom: 8,
  borderRadius: 999,
  paddingInline: 10,
};

export const fieldLabelStyle = {
  marginBottom: 4,
  color: "#9ca3af",
  fontSize: 12,
};

export const sectionHeaderStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 12px",
  borderRadius: 8,
  background: "#0f1720",
  border: "1px solid #1e293b",
  marginBottom: 12,
};

export const metricValueEmphasisStyle = {
  fontSize: 20,
  fontWeight: 700,
  color: "#e5e7eb",
  lineHeight: 1.2,
  letterSpacing: 0.1,
};

export const metricValueSecondaryStyle = {
  fontSize: 16,
  fontWeight: 600,
  color: "#e5e7eb",
  lineHeight: 1.2,
};

export const darkColors = {
  pageBg: "#0b1120",
  cardBg: "#111827",
  elevatedBg: "#1a2332",
  nestedBg: "#0f1720",
  primary: "#3b82f6",
  accent: "#6366f1",
  up: "#ef4444",
  down: "#22c55e",
  upBg: "rgba(239,68,68,0.15)",
  downBg: "rgba(34,197,94,0.15)",
  upCardGradient: "linear-gradient(135deg, #1a0f0f, #2d1518)",
  downCardGradient: "linear-gradient(135deg, #0f1a14, #152d1d)",
  textPrimary: "#e5e7eb",
  textSecondary: "#9ca3af",
  textMuted: "#6b7280",
  border: "#1e293b",
  headerGradient: "linear-gradient(135deg, #1e3a5f, #0f172a)",
  logoGradient: "linear-gradient(135deg, #3b82f6, #6366f1)",
} as const;
