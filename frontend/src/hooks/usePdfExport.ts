import { useCallback, useRef, useState, type RefObject } from "react";
import { calculatePdfCanvasScale, calculatePdfCanvasSlices } from "./pdfPagination";

interface UsePdfExportOptions {
  targetRef: RefObject<HTMLElement | null>;
  filename: () => string;
  backgroundColor: string;
  beforeCapture?: () => Promise<void> | void;
  captureSelector?: string;
  sectionSelector?: string;
  preferredScale?: number;
  imageFormat?: "JPEG" | "PNG";
  imageQuality?: number;
  pageMargin?: number;
  showPageNumbers?: boolean;
  isCaptureReady?: () => boolean;
  captureReadyTimeoutMs?: number;
  onStart?: () => void;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export function usePdfExport({
  targetRef,
  filename,
  backgroundColor,
  beforeCapture,
  captureSelector,
  sectionSelector,
  preferredScale = 1.5,
  imageFormat = "JPEG",
  imageQuality = 0.9,
  pageMargin = 0,
  showPageNumbers = false,
  isCaptureReady,
  captureReadyTimeoutMs = 8_000,
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
    try {
      onStart?.();
      await beforeCapture?.();
      if ("fonts" in document) await document.fonts.ready;
      const images = Array.from(targetRef.current.querySelectorAll("img"));
      await Promise.all(images.map(async (image) => {
        if (image.complete) {
          await image.decode?.().catch(() => undefined);
          return;
        }
        await new Promise<void>((resolve) => {
          image.addEventListener("load", () => resolve(), { once: true });
          image.addEventListener("error", () => resolve(), { once: true });
        });
      }));
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null))));
      if (isCaptureReady) {
        const deadline = performance.now() + captureReadyTimeoutMs;
        while (!isCaptureReady()) {
          if (performance.now() >= deadline) throw new Error("等待 PDF 内容渲染超时");
          await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
        }
      }
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = Math.max(0, Math.min(pageMargin, pageWidth / 4, pageHeight / 4));
      const contentWidth = pageWidth - margin * 2;
      const contentHeight = pageHeight - margin * 2;
      const captureTargets = captureSelector
        ? Array.from(targetRef.current.querySelectorAll<HTMLElement>(captureSelector))
        : [targetRef.current];
      if (captureTargets.length === 0) throw new Error("未找到可导出的报告内容");

      let hasPdfPage = false;
      let currentPageY = 0;
      const sectionGap = 3;
      for (const captureTarget of captureTargets) {
        const targetRect = captureTarget.getBoundingClientRect();
        const captureWidth = Math.max(captureTarget.scrollWidth, Math.ceil(targetRect.width));
        const captureHeight = Math.max(captureTarget.scrollHeight, Math.ceil(targetRect.height));
        const scale = calculatePdfCanvasScale({
          width: captureWidth,
          height: captureHeight,
          preferredScale,
        });
        if (scale <= 0) continue;

        const sectionOffsets = sectionSelector
          ? Array.from(captureTarget.querySelectorAll<HTMLElement>(sectionSelector)).map(
            (section) => Math.round(section.getBoundingClientRect().top - targetRect.top),
          )
          : [];
        const canvas = await html2canvas(captureTarget, {
          scale,
          useCORS: true,
          backgroundColor,
          logging: false,
          width: captureWidth,
          height: captureHeight,
          windowWidth: Math.max(window.innerWidth, captureWidth),
          windowHeight: Math.max(window.innerHeight, captureHeight),
        });
        const slices = calculatePdfCanvasSlices({
          canvasWidth: canvas.width,
          canvasHeight: canvas.height,
          pageWidth: contentWidth,
          pageHeight: contentHeight,
          preferredBreaks: sectionOffsets.map((offset) => Math.round(offset * canvas.width / captureWidth)),
        });

        const pageBottom = pageHeight - margin;
        for (const [sliceIndex, slice] of slices.entries()) {
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
          const gap = hasPdfPage && sliceIndex === 0 ? sectionGap : 0;
          let renderedY = hasPdfPage ? currentPageY + gap : margin;
          if (hasPdfPage && currentPageY + gap + slice.renderedHeight > pageBottom) {
            pdf.addPage();
            currentPageY = margin;
            renderedY = margin;
          }
          const imageData = imageFormat === "PNG"
            ? pageCanvas.toDataURL("image/png")
            : pageCanvas.toDataURL("image/jpeg", imageQuality);
          pdf.addImage(
            imageData,
            imageFormat,
            margin,
            renderedY,
            contentWidth,
            slice.renderedHeight,
            undefined,
            "FAST",
          );
          hasPdfPage = true;
          currentPageY = renderedY + slice.renderedHeight;
          pageCanvas.width = 0;
          pageCanvas.height = 0;
        }
        canvas.width = 0;
        canvas.height = 0;
      }
      if (!hasPdfPage) throw new Error("报告画布尺寸无效");
      if (showPageNumbers) {
        const pageCount = pdf.getNumberOfPages();
        pdf.setFontSize(8);
        pdf.setTextColor(120);
        for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
          pdf.setPage(pageNumber);
          pdf.text(`${pageNumber} / ${pageCount}`, pageWidth / 2, pageHeight - 3, { align: "center" });
        }
      }
      pdf.save(filename());
      onSuccess?.();
    } catch (error) {
      onError?.(error);
    } finally {
      isExportingRef.current = false;
      setIsExporting(false);
    }
  }, [
    backgroundColor,
    beforeCapture,
    captureSelector,
    filename,
    imageFormat,
    imageQuality,
    isCaptureReady,
    pageMargin,
    onError,
    onStart,
    onSuccess,
    preferredScale,
    sectionSelector,
    showPageNumbers,
    targetRef,
    captureReadyTimeoutMs,
  ]);

  return { exportPdf, isExporting };
}
