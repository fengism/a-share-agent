import { describe, expect, it } from "vitest";
import { SVGRenderer } from "echarts/renderers";
import echarts from "./echarts-setup";

describe("echarts-setup", () => {
  it("renders candlestick series without missing package errors", () => {
    echarts.use([SVGRenderer]);
    const chart = echarts.init(null, null, {
      renderer: "svg",
      ssr: true,
      width: 400,
      height: 300,
    });

    chart.setOption({
      xAxis: { type: "category", data: ["2026-10-10"] },
      yAxis: { type: "value" },
      series: [
        {
          type: "candlestick",
          data: [[900, 905, 895, 910]],
        },
      ],
    });

    const svg = chart.renderToSVGString();
    expect(svg).toBeTruthy();
    // Candlestick rendering creates candle body/wick SVG paths
    expect(svg).toContain("<path");

    chart.dispose();
  });
});
