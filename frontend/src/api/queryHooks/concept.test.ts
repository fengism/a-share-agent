import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useConceptConstituents, useConceptIndex } from "./concept";

const openApiGet = vi.hoisted(() => vi.fn());

vi.mock("../openapiClient", () => ({ openApiGet }));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(QueryClientProvider, { client }, children);
}

beforeEach(() => {
  openApiGet.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useConceptIndex", () => {
  it("requests the concept and range", async () => {
    openApiGet.mockResolvedValue({ concept: "机器人概念", items: [] });
    const { result } = renderHook(() => useConceptIndex("机器人概念", 365), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/market/concept/{concept}/index", {
      path: { concept: "机器人概念" },
      query: { days: 365 },
    });
  });

  it("does not fire before a concept is known", () => {
    openApiGet.mockResolvedValue({ items: [] });
    renderHook(() => useConceptIndex("", 365), { wrapper });
    expect(openApiGet).not.toHaveBeenCalled();
  });

  /**
   * 回归：长区间首次合成要几秒，若 data 变undefined，前端会把图表换成骨架屏，
   * 用户看到的是整图消失再重载。placeholderData 应让上一批数据一直留在画面上。
   */
  it("keeps the previous range on screen while a new range is loading", async () => {
    let resolveSecond: ((value: unknown) => void) | undefined;
    openApiGet
      .mockResolvedValueOnce({ concept: "X", items: [{ date: "2026-01-02", close: 100 }] })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );

    const { result, rerender } = renderHook(
      ({ days }: { days: number }) => useConceptIndex("X", days),
      { wrapper, initialProps: { days: 365 } },
    );

    await waitFor(() => expect(result.current.data?.items).toHaveLength(1));

    rerender({ days: 3650 });
    await waitFor(() => expect(result.current.isFetching).toBe(true));

    // 旧数据仍在，界面不会塌成骨架屏
    expect(result.current.data?.items).toHaveLength(1);
    expect(result.current.data?.items[0].close).toBe(100);

    // 新数据到达后正常替换
    resolveSecond?.({ concept: "X", items: [{ date: "2026-01-02", close: 100 }, { date: "2026-01-03", close: 101 }] });
    await waitFor(() => expect(result.current.data?.items).toHaveLength(2));
  });
});

describe("useConceptConstituents", () => {
  it("requests the concept", async () => {
    openApiGet.mockResolvedValue({ concept: "X", total: 1, items: [] });
    const { result } = renderHook(() => useConceptConstituents("X"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    // 不传 codes = 只取本地身份列表，零上游行情调用
    expect(openApiGet).toHaveBeenCalledWith("/api/market/concept/{concept}/constituents", {
      path: { concept: "X" },
      query: { codes: "" },
    });
  });

  /** 回归：按需加载行情时只把请求的代码集传给后端，避免全量拉上游行情。 */
  it("scopes the request to the requested quote window", async () => {
    openApiGet.mockResolvedValue({ concept: "X", total: 2, items: [] });
    const { result } = renderHook(() => useConceptConstituents("X", ["000002", "600519"]), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/market/concept/{concept}/constituents", {
      path: { concept: "X" },
      query: { codes: "000002,600519" },
    });
  });

  it("keeps the previous concept's rows while switching", async () => {
    let resolveSecond: ((value: unknown) => void) | undefined;
    openApiGet
      .mockResolvedValueOnce({ concept: "A", total: 1, items: [{ code: "000001", name: "甲" }] })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveSecond = resolve;
          }),
      );

    const { result, rerender } = renderHook(
      ({ concept }: { concept: string }) => useConceptConstituents(concept),
      { wrapper, initialProps: { concept: "A" } },
    );
    await waitFor(() => expect(result.current.data?.items).toHaveLength(1));

    rerender({ concept: "B" });
    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data?.items[0].name).toBe("甲");

    resolveSecond?.({ concept: "B", total: 1, items: [{ code: "000002", name: "乙" }] });
    await waitFor(() => expect(result.current.data?.items[0].name).toBe("乙"));
  });
});