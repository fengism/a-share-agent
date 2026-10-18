import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_TIMEOUTS, apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import { usePotentialRun, usePotentialRunStatus } from "./potential";

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn(), apiPost: vi.fn() };
});

function makeWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("potential run hooks", () => {
  afterEach(() => {
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiGet).mockReset();
  });

  it("starts the background run without waiting for the whole mining", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      running: true,
      status: "running",
      date: null,
      started_at: null,
      finished_at: null,
      error: null,
    });

    const { wrapper } = makeWrapper();
    const { result } = renderHook(() => usePotentialRun(), { wrapper });
    result.current.mutate(false);

    await waitFor(() => expect(apiPost).toHaveBeenCalled());
    expect(apiPost).toHaveBeenCalledWith("/potential/run", {}, { timeoutMs: API_TIMEOUTS.DEFAULT });
  });

  it("polls the run status while running and stops after completion", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      running: false,
      status: "completed",
      date: "2026-10-16",
      started_at: null,
      finished_at: null,
      error: null,
    });

    const { queryClient, wrapper } = makeWrapper();
    renderHook(() => usePotentialRunStatus(true), { wrapper });

    await waitFor(() => expect(apiGet).toHaveBeenCalledWith("/potential/run/status"));
    const options = queryClient
      .getQueryCache()
      .find({ queryKey: queryKeys.potential.runStatus })?.options as
      | { refetchInterval?: unknown }
      | undefined;
    const interval = options?.refetchInterval as
      | ((query: { state: { data?: { running?: boolean } } }) => number | false)
      | undefined;
    expect(interval?.({ state: { data: { running: true } } })).toBe(5000);
    expect(interval?.({ state: { data: { running: false } } })).toBe(false);
  });
});
