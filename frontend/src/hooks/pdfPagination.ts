export interface PdfCanvasSlice {
  sourceY: number;
  sourceHeight: number;
  renderedHeight: number;
}

interface PdfCanvasDimensions {
  canvasWidth: number;
  canvasHeight: number;
  pageWidth: number;
  pageHeight: number;
  preferredBreaks?: number[];
}

interface PdfCanvasScaleOptions {
  width: number;
  height: number;
  preferredScale?: number;
  maxDimension?: number;
  maxPixels?: number;
}

export function calculatePdfCanvasScale({
  width,
  height,
  preferredScale = 1.5,
  maxDimension = 16_384,
  maxPixels = 48_000_000,
}: PdfCanvasScaleOptions): number {
  if (width <= 0 || height <= 0) return 0;
  return Math.min(
    preferredScale,
    maxDimension / Math.max(width, height),
    Math.sqrt(maxPixels / (width * height)),
  );
}

export function calculatePdfCanvasSlices({
  canvasWidth,
  canvasHeight,
  pageWidth,
  pageHeight,
  preferredBreaks = [],
}: PdfCanvasDimensions): PdfCanvasSlice[] {
  if (canvasWidth <= 0 || canvasHeight <= 0 || pageWidth <= 0 || pageHeight <= 0) return [];
  const maxSourceHeight = Math.max(1, Math.floor(canvasWidth * pageHeight / pageWidth));
  const breaks = [...new Set(preferredBreaks)]
    .filter((value) => Number.isFinite(value) && value > 0 && value < canvasHeight)
    .sort((left, right) => left - right);
  const slices: PdfCanvasSlice[] = [];
  let sourceY = 0;

  while (sourceY < canvasHeight) {
    const hardEnd = Math.min(canvasHeight, sourceY + maxSourceHeight);
    const candidates = breaks.filter((value) => value > sourceY && value <= hardEnd);
    const preferredEnd = candidates[candidates.length - 1];
    const sourceEnd = preferredEnd && preferredEnd - sourceY >= maxSourceHeight * 0.45
      ? preferredEnd
      : hardEnd;
    const sourceHeight = sourceEnd - sourceY;
    slices.push({
      sourceY,
      sourceHeight,
      renderedHeight: sourceHeight * pageWidth / canvasWidth,
    });
    sourceY = sourceEnd;
  }

  return slices;
}
