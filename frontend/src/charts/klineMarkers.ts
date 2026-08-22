import type { SeriesMarker, Time } from "lightweight-charts";
import { toBusinessDay } from "./utils";

export interface KlineTradeMarker {
  date: string;
  side: "buy" | "sell";
  label?: string;
}

export function buildKlineTradeMarkers(
  markers: KlineTradeMarker[],
  colors: { buy: string; sell: string },
  availableDates?: ReadonlySet<string>,
): SeriesMarker<Time>[] {
  return [...markers]
    .sort((left, right) => `${left.date}-${left.side}`.localeCompare(`${right.date}-${right.side}`))
    .flatMap<SeriesMarker<Time>>((marker) => {
      if (availableDates && !availableDates.has(marker.date)) return [];
      const time = toBusinessDay(marker.date);
      if (!time) return [];
      const isBuy = marker.side === "buy";
      return [{
        time,
        position: isBuy ? "belowBar" : "aboveBar",
        shape: isBuy ? "arrowUp" : "arrowDown",
        color: isBuy ? colors.buy : colors.sell,
        text: marker.label || (isBuy ? "买" : "卖"),
      }];
    });
}
