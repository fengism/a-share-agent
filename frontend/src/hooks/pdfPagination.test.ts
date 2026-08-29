import { describe, expect, it } from "vitest";
import { calculatePdfCanvasScale, calculatePdfCanvasSlices } from "./pdfPagination";

describe("calculatePdfCanvasScale", () => {
  it("uses the preferred scale for normal report sections", () => {
    expect(calculatePdfCanvasScale({ width: 1100, height: 4000 })).toBe(1.5);
    expect(calculatePdfCanvasScale({ width: 1100, height: 4000, preferredScale: 2 })).toBe(2);
  });

  it("keeps long captures within the browser canvas dimension limit", () => {
    const scale = calculatePdfCanvasScale({ width: 1100, height: 30_000 });
    expect(30_000 * scale).toBeLessThanOrEqual(16_384);
  });

  it("keeps large captures within the pixel budget", () => {
    const scale = calculatePdfCanvasScale({ width: 10_000, height: 10_000 });
    expect(10_000 * scale * 10_000 * scale).toBeCloseTo(48_000_000);
  });
});

describe("calculatePdfCanvasSlices", () => {
  it("keeps a short canvas on one PDF page", () => {
    expect(calculatePdfCanvasSlices({
      canvasWidth: 1000,
      canvasHeight: 800,
      pageWidth: 210,
      pageHeight: 297,
    })).toEqual([{
      sourceY: 0,
      sourceHeight: 800,
      renderedHeight: 168,
    }]);
  });

  it("splits a long canvas into contiguous page-sized slices", () => {
    const slices = calculatePdfCanvasSlices({
      canvasWidth: 1000,
      canvasHeight: 3000,
      pageWidth: 210,
      pageHeight: 297,
    });

    expect(slices.map(({ sourceY, sourceHeight }) => ({ sourceY, sourceHeight }))).toEqual([
      { sourceY: 0, sourceHeight: 1414 },
      { sourceY: 1414, sourceHeight: 1414 },
      { sourceY: 2828, sourceHeight: 172 },
    ]);
    expect(slices.every((slice) => slice.renderedHeight <= 297)).toBe(true);
    expect(slices.reduce((height, slice) => height + slice.sourceHeight, 0)).toBe(3000);
  });

  it("prefers semantic section boundaries near the bottom of a page", () => {
    const slices = calculatePdfCanvasSlices({
      canvasWidth: 1000,
      canvasHeight: 3000,
      pageWidth: 210,
      pageHeight: 297,
      preferredBreaks: [1200, 2400],
    });

    expect(slices.map(({ sourceY, sourceHeight }) => ({ sourceY, sourceHeight }))).toEqual([
      { sourceY: 0, sourceHeight: 1200 },
      { sourceY: 1200, sourceHeight: 1200 },
      { sourceY: 2400, sourceHeight: 600 },
    ]);
  });

  it("returns no slices for invalid dimensions", () => {
    expect(calculatePdfCanvasSlices({
      canvasWidth: 0,
      canvasHeight: 100,
      pageWidth: 210,
      pageHeight: 297,
    })).toEqual([]);
  });
});
