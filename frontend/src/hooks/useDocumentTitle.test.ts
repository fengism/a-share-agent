import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  formatPageTitle,
  resolveRouteTitle,
  useDocumentTitle,
} from "./useDocumentTitle";

describe("useDocumentTitle", () => {
  it("formats title correctly with app suffix", () => {
    expect(formatPageTitle("大盘看板")).toBe("大盘看板 - A-Share Agent");
    expect(formatPageTitle("")).toBe("A-Share Agent");
    expect(formatPageTitle(null)).toBe("A-Share Agent");
    expect(formatPageTitle(undefined)).toBe("A-Share Agent");
  });

  it("resolves route titles for predefined routes and dynamic patterns", () => {
    expect(resolveRouteTitle("/")).toBe("大盘看板");
    expect(resolveRouteTitle("/screener")).toBe("智能多因子选股");
    expect(resolveRouteTitle("/stock/600519")).toBe("标的详情 (600519)");
    expect(resolveRouteTitle("/industry-chain/%E5%85%89%E4%BC%8F")).toBe("光伏产业链");
    expect(resolveRouteTitle("/unknown-page")).toBeUndefined();
  });

  it("sets document title and restores on unmount when requested", () => {
    document.title = "Original Title";
    const { unmount } = renderHook(() =>
      useDocumentTitle("自选股监控", { restoreOnUnmount: true }),
    );

    expect(document.title).toBe("自选股监控 - A-Share Agent");

    unmount();
    expect(document.title).toBe("Original Title");
  });
});
