export type ThemeKey = "stellar-blue" | "jade-green" | "twilight-purple" | "light";

export interface ThemeColors {
  pageBg: string;
  cardBg: string;
  elevatedBg: string;
  nestedBg: string;
  primary: string;
  accent: string;
  up: string;
  down: string;
  upBg: string;
  downBg: string;
  upCardGradient: string;
  downCardGradient: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  border: string;
  headerGradient: string;
  logoGradient: string;
}

export interface ThemeMeta {
  key: ThemeKey;
  label: string;
  labelEn: string;
  isLight: boolean;
  colors: ThemeColors;
  antToken: {
    colorPrimary: string;
    colorBgContainer: string;
    colorBgElevated: string;
    colorBorder: string;
    colorText: string;
    colorTextSecondary: string;
  };
  siderBg: string;
  headerBg: string;
}

export const themes: Record<ThemeKey, ThemeMeta> = {
  "stellar-blue": {
    key: "stellar-blue",
    label: "星空蓝",
    labelEn: "Stellar Blue",
    isLight: false,
    siderBg: "#0f172a",
    headerBg: "#0f172a",
    colors: {
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
    },
    antToken: {
      colorPrimary: "#3b82f6",
      colorBgContainer: "#111827",
      colorBgElevated: "#1a2332",
      colorBorder: "#1e293b",
      colorText: "#e5e7eb",
      colorTextSecondary: "#9ca3af",
    },
  },

  "jade-green": {
    key: "jade-green",
    label: "翡翠绿",
    labelEn: "Jade Green",
    isLight: false,
    siderBg: "#0b1a14",
    headerBg: "#0b1a14",
    colors: {
      pageBg: "#0a1410",
      cardBg: "#0f1e18",
      elevatedBg: "#162a22",
      nestedBg: "#0c1a14",
      primary: "#10b981",
      accent: "#059669",
      up: "#ef4444",
      down: "#22c55e",
      upBg: "rgba(239,68,68,0.15)",
      downBg: "rgba(34,197,94,0.15)",
      upCardGradient: "linear-gradient(135deg, #1a0f0f, #2d1518)",
      downCardGradient: "linear-gradient(135deg, #0f1a14, #152d1d)",
      textPrimary: "#e2e8f0",
      textSecondary: "#94a3b8",
      textMuted: "#64748b",
      border: "#1e3a2f",
      headerGradient: "linear-gradient(135deg, #1a3a2a, #0f172a)",
      logoGradient: "linear-gradient(135deg, #10b981, #059669)",
    },
    antToken: {
      colorPrimary: "#10b981",
      colorBgContainer: "#0f1e18",
      colorBgElevated: "#162a22",
      colorBorder: "#1e3a2f",
      colorText: "#e2e8f0",
      colorTextSecondary: "#94a3b8",
    },
  },

  "twilight-purple": {
    key: "twilight-purple",
    label: "暮光紫",
    labelEn: "Twilight Purple",
    isLight: false,
    siderBg: "#13101e",
    headerBg: "#13101e",
    colors: {
      pageBg: "#100d1a",
      cardBg: "#171225",
      elevatedBg: "#221a35",
      nestedBg: "#13101e",
      primary: "#a78bfa",
      accent: "#7c3aed",
      up: "#ef4444",
      down: "#22c55e",
      upBg: "rgba(239,68,68,0.15)",
      downBg: "rgba(34,197,94,0.15)",
      upCardGradient: "linear-gradient(135deg, #1a0f0f, #2d1518)",
      downCardGradient: "linear-gradient(135deg, #0f1a14, #152d1d)",
      textPrimary: "#e8e3f3",
      textSecondary: "#a5a0b8",
      textMuted: "#716d85",
      border: "#2d2545",
      headerGradient: "linear-gradient(135deg, #2a1e4a, #13101e)",
      logoGradient: "linear-gradient(135deg, #a78bfa, #7c3aed)",
    },
    antToken: {
      colorPrimary: "#a78bfa",
      colorBgContainer: "#171225",
      colorBgElevated: "#221a35",
      colorBorder: "#2d2545",
      colorText: "#e8e3f3",
      colorTextSecondary: "#a5a0b8",
    },
  },

  "light": {
    key: "light",
    label: "清晨白",
    labelEn: "Morning Light",
    isLight: true,
    siderBg: "#ffffff",
    headerBg: "#ffffff",
    colors: {
      pageBg: "#f5f7fa",
      cardBg: "#ffffff",
      elevatedBg: "#f0f2f5",
      nestedBg: "#f8f9fb",
      primary: "#1677ff",
      accent: "#722ed1",
      up: "#cf1322",
      down: "#3f8600",
      upBg: "rgba(207,19,34,0.08)",
      downBg: "rgba(63,134,0,0.08)",
      upCardGradient: "linear-gradient(135deg, #fff1f0, #ffe7e6)",
      downCardGradient: "linear-gradient(135deg, #f6ffed, #e6ffec)",
      textPrimary: "#1d2129",
      textSecondary: "#4e5969",
      textMuted: "#86909c",
      border: "#e5e6eb",
      headerGradient: "linear-gradient(135deg, #e8f4fd, #f0f2f5)",
      logoGradient: "linear-gradient(135deg, #1677ff, #722ed1)",
    },
    antToken: {
      colorPrimary: "#1677ff",
      colorBgContainer: "#ffffff",
      colorBgElevated: "#ffffff",
      colorBorder: "#e5e6eb",
      colorText: "#1d2129",
      colorTextSecondary: "#4e5969",
    },
  },
};

export const THEME_LIST = Object.values(themes);
