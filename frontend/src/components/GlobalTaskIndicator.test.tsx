import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAnalysisStore } from "../store/analysisStore";
import { useChatStore } from "../store/chatStore";
import { useIndustryChainWorkflowStore } from "../store/industryChainWorkflowStore";
import GlobalTaskIndicator from "./GlobalTaskIndicator";

const { useActiveWorkflows, useCancelWorkflow, stopChatRuntime, cancelWorkflow } = vi.hoisted(() => ({
  useActiveWorkflows: vi.fn(),
  useCancelWorkflow: vi.fn(),
  stopChatRuntime: vi.fn(),
  cancelWorkflow: vi.fn(),
}));
vi.mock("../api/queries", () => ({ useActiveWorkflows, useCancelWorkflow }));
vi.mock("../features/chat/chatRuntime", () => ({ stopChatRuntime }));

describe("GlobalTaskIndicator", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useChatStore.setState({ isStreaming: false, activeRunLabel: null });
    useAnalysisStore.getState().resetAnalysis();
    useIndustryChainWorkflowStore.getState().clear();
    useActiveWorkflows.mockReturnValue({ data: [] });
    useCancelWorkflow.mockReturnValue({ mutateAsync: cancelWorkflow, isPending: false, variables: undefined });
  });

  it("stays hidden when there are no active tasks", () => {
    render(<MemoryRouter><GlobalTaskIndicator /></MemoryRouter>);
    expect(screen.queryByRole("button", { name: /个任务运行中/ })).not.toBeInTheDocument();
  });

  it("shows chat work globally and stops it", async () => {
    useChatStore.setState({ isStreaming: true, activeRunLabel: "分析贵州茅台" });
    render(<MemoryRouter><GlobalTaskIndicator /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "1 个任务运行中" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "停止对话生成" })).toBeVisible());
    fireEvent.click(screen.getByRole("button", { name: "停止对话生成" }));
    expect(stopChatRuntime).toHaveBeenCalledOnce();
  });

  it("shows durable workflows and stops them through the API", async () => {
    cancelWorkflow.mockResolvedValue({ status: "cancelled" });
    useActiveWorkflows.mockReturnValue({
      data: [{
        id: "job-1",
        kind: "analysis",
        dedupe_key: "600519",
        request: { code: "600519" },
        status: "running",
        attempts: 1,
        max_attempts: 2,
        created_at: 1,
        updated_at: 2,
        completed_at: null,
        last_error: null,
      }],
    });
    render(<MemoryRouter><GlobalTaskIndicator /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "1 个任务运行中" }));
    const stop = await screen.findByRole("button", { name: "停止个股研究 · 600519" });
    fireEvent.click(stop);
    await waitFor(() => expect(cancelWorkflow).toHaveBeenCalledWith("job-1"));
  });
});
