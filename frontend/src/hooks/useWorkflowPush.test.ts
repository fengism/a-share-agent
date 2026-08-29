import type { ReactNode } from "react";
import { act, render, renderHook, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PushRequest, PushResponse } from "../types/stock";
import { useWorkflowPush } from "./useWorkflowPush";

const mocks = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
}));

vi.mock("../api/queries", () => ({
  usePush: () => ({ mutateAsync: mocks.mutateAsync, isPending: false }),
}));

vi.mock("antd", () => ({
  message: { success: mocks.success, warning: mocks.warning, error: mocks.error },
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
    mocks.warning.mockReset();
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
    const successConfig = mocks.success.mock.calls[0][0] as { content: ReactNode; duration: number };
    expect(successConfig.duration).toBe(6);
    render(successConfig.content);
    expect(screen.getByText("已转存 Notion：分析报告")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开" })).toHaveAttribute("href", response.url);
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

  it("shows a document link when Feishu message delivery partially fails", async () => {
    mocks.mutateAsync.mockResolvedValue({
      ...response,
      success: false,
      target: "feishu",
      message: "文档已创建，但消息通知失败",
    });
    const { result } = renderHook(() => useWorkflowPush());

    let pushResult: PushResponse | null = null;
    await act(async () => {
      pushResult = await result.current.push({ ...request, target: "feishu" });
    });

    expect(pushResult).toMatchObject({ success: false, url: response.url });
    const warningConfig = mocks.warning.mock.calls[0][0] as { content: ReactNode; duration: number };
    expect(warningConfig.duration).toBe(8);
    render(warningConfig.content);
    expect(screen.getByText("文档已创建，但消息通知失败")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开文档" })).toHaveAttribute("href", response.url);
    expect(mocks.success).not.toHaveBeenCalled();
  });
});
