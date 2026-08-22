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
}

export function calculatePdfCanvasSlices({
  canvasWidth,
  canvasHeight,
  pageWidth,
  pageHeight,
}: PdfCanvasDimensions): PdfCanvasSlice[] {
  if (canvasWidth <= 0 || canvasHeight <= 0 || pageWidth <= 0 || pageHeight <= 0) return [];
  const maxSourceHeight = Math.max(1, Math.floor(canvasWidth * pageHeight / pageWidth));
  const slices: PdfCanvasSlice[] = [];

  for (let sourceY = 0; sourceY < canvasHeight; sourceY += maxSourceHeight) {
    const sourceHeight = Math.min(maxSourceHeight, canvasHeight - sourceY);
    slices.push({
      sourceY,
      sourceHeight,
      renderedHeight: sourceHeight * pageWidth / canvasWidth,
    });
  }

  return slices;
}
