import { describe, expect, it } from "vitest";
import { buildKlineTradeMarkers } from "./klineMarkers";

describe("buildKlineTradeMarkers", () => {
  it("maps buy and sell trades to semantic candle markers", () => {
    const markers = buildKlineTradeMarkers(
      [
        { date: "2026-01-03", side: "sell", label: "卖 100" },
        { date: "2026-01-02", side: "buy", label: "买 100" },
      ],
      { buy: "#f00", sell: "#0a0" },
      new Set(["2026-01-02", "2026-01-03"]),
    );

    expect(markers).toEqual([
      expect.objectContaining({ position: "belowBar", shape: "arrowUp", color: "#f00", text: "买 100" }),
      expect.objectContaining({ position: "aboveBar", shape: "arrowDown", color: "#0a0", text: "卖 100" }),
    ]);
  });

  it("drops invalid dates and trades outside the loaded K-line range", () => {
    const markers = buildKlineTradeMarkers(
      [
        { date: "invalid", side: "buy" },
        { date: "2026-01-02", side: "sell" },
      ],
      { buy: "#f00", sell: "#0a0" },
      new Set(["2026-01-03"]),
    );

    expect(markers).toEqual([]);
  });
});
