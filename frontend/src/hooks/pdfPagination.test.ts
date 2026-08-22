import { describe, expect, it } from "vitest";
import { calculatePdfCanvasSlices } from "./pdfPagination";

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

  it("returns no slices for invalid dimensions", () => {
    expect(calculatePdfCanvasSlices({
      canvasWidth: 0,
      canvasHeight: 100,
      pageWidth: 210,
      pageHeight: 297,
    })).toEqual([]);
  });
});
