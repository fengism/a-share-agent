import { useCallback, useRef, useState, type RefObject } from "react";
import { calculatePdfCanvasSlices } from "./pdfPagination";

interface UsePdfExportOptions {
  targetRef: RefObject<HTMLElement | null>;
  filename: () => string;
  backgroundColor: string;
  beforeCapture?: () => Promise<void> | void;
  onStart?: () => void;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export function usePdfExport({
  targetRef,
  filename,
  backgroundColor,
  beforeCapture,
  onStart,
  onSuccess,
  onError,
}: UsePdfExportOptions) {
  const [isExporting, setIsExporting] = useState(false);
  const isExportingRef = useRef(false);

  const exportPdf = useCallback(async () => {
    if (!targetRef.current || isExportingRef.current) return;
    isExportingRef.current = true;
    setIsExporting(true);
    onStart?.();
    try {
      await beforeCapture?.();
      await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(targetRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor,
      });
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const slices = calculatePdfCanvasSlices({
        canvasWidth: canvas.width,
        canvasHeight: canvas.height,
        pageWidth,
        pageHeight,
      });
      if (slices.length === 0) throw new Error("报告画布尺寸无效");

      slices.forEach((slice, index) => {
        const pageCanvas = document.createElement("canvas");
        pageCanvas.width = canvas.width;
        pageCanvas.height = slice.sourceHeight;
        const context = pageCanvas.getContext("2d");
        if (!context) throw new Error("无法创建 PDF 分页画布");
        context.drawImage(
          canvas,
          0,
          slice.sourceY,
          canvas.width,
          slice.sourceHeight,
          0,
          0,
          canvas.width,
          slice.sourceHeight,
        );
        if (index > 0) pdf.addPage();
        pdf.addImage(pageCanvas.toDataURL("image/png"), "PNG", 0, 0, pageWidth, slice.renderedHeight);
        pageCanvas.width = 0;
        pageCanvas.height = 0;
      });
      pdf.save(filename());
      onSuccess?.();
    } catch (error) {
      onError?.(error);
    } finally {
      isExportingRef.current = false;
      setIsExporting(false);
    }
  }, [backgroundColor, beforeCapture, filename, onError, onStart, onSuccess, targetRef]);

  return { exportPdf, isExporting };
}
