import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { usePdfExport } from "./usePdfExport";

describe("usePdfExport", () => {
  it("ignores concurrent export attempts before React state updates", async () => {
    const captureError = new Error("capture stopped");
    const beforeCapture = vi.fn().mockRejectedValue(captureError);
    const onStart = vi.fn();
    const onError = vi.fn();
    const targetRef = { current: document.createElement("div") };
    const { result } = renderHook(() => usePdfExport({
      targetRef,
      filename: () => "report.pdf",
      backgroundColor: "#fff",
      beforeCapture,
      onStart,
      onError,
    }));

    let firstExport!: Promise<void>;
    let secondExport!: Promise<void>;
    act(() => {
      firstExport = result.current.exportPdf();
      secondExport = result.current.exportPdf();
    });
    await act(async () => {
      await Promise.all([firstExport, secondExport]);
    });

    expect(beforeCapture).toHaveBeenCalledOnce();
    expect(onStart).toHaveBeenCalledOnce();
    expect(onError).toHaveBeenCalledWith(captureError);
    expect(result.current.isExporting).toBe(false);
  });
});
