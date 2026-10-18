import type { SeriesMarker, Time } from "lightweight-charts";
import type { ChanlunResult, MmdType } from "../utils/chanlun";
import { toBusinessDay } from "./utils";

export const MMD_MARKER_TEXT: Record<MmdType, string> = {
  "1buy": "①买", "2buy": "②买", "3buy": "③买",
  "1sell": "①卖", "2sell": "②卖", "3sell": "③卖",
};

export function buildChanlunMarkers(
  chanlun: ChanlunResult,
  colors: { up: string; down: string },
  validDates: Set<string>,
): SeriesMarker<Time>[] {
  const markers: SeriesMarker<Time>[] = [];
  for (const mmd of chanlun.mmds) {
    const time = toBusinessDay(mmd.date);
    if (!time || !validDates.has(mmd.date)) continue;
    const isBuy = mmd.mmdType.endsWith("buy");
    markers.push({
      time,
      position: isBuy ? "belowBar" : "aboveBar",
      shape: isBuy ? "arrowUp" : "arrowDown",
      color: isBuy ? colors.up : colors.down,
      text: MMD_MARKER_TEXT[mmd.mmdType],
      size: 1,
    });
  }
  return markers;
}
