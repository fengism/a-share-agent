import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PushRequest, PushResponse } from "../types/stock";
import { useWorkflowPush } from "./useWorkflowPush";

const mocks = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
}));

vi.mock("../api/queries", () => ({
  usePush: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
}));

vi.mock("antd", () => ({
  message: { success: mocks.success, error: mocks.error },
}));

const request: PushRequest = {
  target: "notion",
  type: "analysis",
  code: "600519",
};

const response: PushResponse = {
  success: true,
  target: "notion",
  url: "https://example.com/report",
  title: "分析报告",
  message: "ok",
};

describe("useWorkflowPush", () => {
  beforeEach(() => {
    mocks.mutateAsync.mockReset();
    mocks.success.mockReset();
    mocks.error.mockReset();
  });

  it("keeps only one push request in flight", async () => {
    let resolvePush!: (value: PushResponse) => void;
    mocks.mutateAsync.mockImplementation(() => new Promise<PushResponse>((resolve) => {
      resolvePush = resolve;
    }));
    const { result } = renderHook(() => useWorkflowPush());

    let firstPush!: Promise<PushResponse | null>;
    let secondPush!: Promise<PushResponse | null>;
    act(() => {
      firstPush = result.current.push(request);
      secondPush = result.current.push(request);
    });

    await expect(secondPush).resolves.toBeNull();
    expect(mocks.mutateAsync).toHaveBeenCalledOnce();

    await act(async () => {
      resolvePush(response);
      await expect(firstPush).resolves.toEqual(response);
    });
    expect(mocks.success).toHaveBeenCalledWith("已转存 Notion：分析报告");
  });

  it("keeps backend error details in the shared failure message", async () => {
    mocks.mutateAsync.mockRejectedValue({ response: { data: { detail: "接收人无效" } } });
    const { result } = renderHook(() => useWorkflowPush());

    let pushResult: PushResponse | null = response;
    await act(async () => {
      pushResult = await result.current.push(request);
    });

    expect(pushResult).toBeNull();
    expect(mocks.error).toHaveBeenCalledWith("推送失败: 接收人无效");
  });
});
