import { StrictMode, type ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryChainResult } from "../../types/stock";
import { useIndustryArchiveAutoLoader } from "./useIndustryArchiveAutoLoader";

const archiveResult: IndustryChainResult = {
  name: "人形机器人",
  summary: "产业链摘要",
  upstream: [],
  midstream: [],
  downstream: [],
  drivers: [],
  risks: [],
  key_stocks: [],
  llm_review: "研究结论",
  charts: [],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => {
    resolve = resolver;
  });
  return { promise, resolve };
}

const strictWrapper = ({ children }: { children: ReactNode }) => (
  <StrictMode>{children}</StrictMode>
);

describe("useIndustryArchiveAutoLoader", () => {
  it("loads the same latest archive only once across rerenders", async () => {
    const pending = deferred<IndustryChainResult>();
    const requestArchive = vi.fn(
      (request: { name: string; archiveId: string }) => {
        void request;
        return pending.promise;
      },
    );
    const applyArchive = vi.fn();

    const { rerender } = renderHook(
      ({ renderVersion }) => {
        const loadArchive = (request: { name: string; archiveId: string }) => {
          void renderVersion;
          return requestArchive(request);
        };
        const loadResult = (name: string, result: IndustryChainResult, archiveId: string) => {
          applyArchive(name, result, archiveId);
        };
        useIndustryArchiveAutoLoader({
          activeName: "人形机器人",
          latestArchiveId: "20260902_185451",
          isLatestLoading: false,
          isAnalyzing: false,
          hasDisplayedResult: false,
          hasCurrentRouteError: false,
          loadArchive,
          loadResult,
        });
      },
      { initialProps: { renderVersion: 0 }, wrapper: strictWrapper },
    );

    rerender({ renderVersion: 1 });
    rerender({ renderVersion: 2 });
    rerender({ renderVersion: 3 });

    expect(requestArchive).toHaveBeenCalledTimes(1);
    expect(requestArchive).toHaveBeenCalledWith({
      name: "人形机器人",
      archiveId: "20260902_185451",
    });

    await act(async () => {
      pending.resolve(archiveResult);
      await pending.promise;
    });

    await waitFor(() => {
      expect(applyArchive).toHaveBeenCalledTimes(1);
      expect(applyArchive).toHaveBeenCalledWith(
        "人形机器人",
        archiveResult,
        "20260902_185451",
      );
    });
  });

  it("allows a new latest archive id to load", async () => {
    const requestArchive = vi.fn().mockResolvedValue(archiveResult);
    const applyArchive = vi.fn();

    const { rerender } = renderHook(
      ({ archiveId }) => useIndustryArchiveAutoLoader({
        activeName: "人形机器人",
        latestArchiveId: archiveId,
        isLatestLoading: false,
        isAnalyzing: false,
        hasDisplayedResult: false,
        hasCurrentRouteError: false,
        loadArchive: requestArchive,
        loadResult: applyArchive,
      }),
      { initialProps: { archiveId: "archive-1" } },
    );

    await waitFor(() => expect(requestArchive).toHaveBeenCalledTimes(1));
    rerender({ archiveId: "archive-2" });
    await waitFor(() => expect(requestArchive).toHaveBeenCalledTimes(2));
  });
});
