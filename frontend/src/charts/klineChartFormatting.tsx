import { hexToRgba } from "./utils";

export function formatVolume(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

export function formatAmount(val: number | null | undefined): string {
  if (val == null || isNaN(val)) return "-";
  if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
  if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(2)}万`;
  return val.toFixed(0);
}

export function renderVolumeRatioBadge(
  val: number | null | undefined,
  maVal: number | null | undefined,
  colors?: { up?: string; down?: string; muted?: string; secondary?: string },
) {
  if (val == null || maVal == null || maVal <= 0 || val <= 0) return null;
  const ratio = val / maVal;
  const upColor = colors?.up ?? "#ef4444";
  const downColor = colors?.down ?? "#10b981";
  const mutedColor = colors?.muted ?? "#888888";
  const secondaryColor = colors?.secondary ?? "#aaaaaa";
  if (ratio >= 2.0) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(upColor, 0.15), color: upColor, fontWeight: 700, lineHeight: "14px" }}
      >
        爆量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio >= 1.3) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(upColor, 0.12), color: upColor, fontWeight: 600, lineHeight: "14px" }}
      >
        放量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio <= 0.6) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(downColor, 0.12), color: downColor, fontWeight: 600, lineHeight: "14px" }}
      >
        地量 {ratio.toFixed(1)}x
      </span>
    );
  }
  if (ratio <= 0.8) {
    return (
      <span
        title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
        style={{ fontSize: "10px", padding: "0 4px", borderRadius: 2, background: hexToRgba(mutedColor, 0.15), color: secondaryColor, fontWeight: 500, lineHeight: "14px" }}
      >
        缩量 {ratio.toFixed(1)}x
      </span>
    );
  }
  return (
    <span
      title={`量比: ${(ratio * 100).toFixed(0)}% (对比5日均值)`}
      style={{ fontSize: "10px", padding: "0 3px", borderRadius: 2, color: mutedColor, lineHeight: "14px" }}
    >
      平量
    </span>
  );
}
