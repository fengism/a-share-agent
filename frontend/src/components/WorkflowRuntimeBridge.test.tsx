import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WorkflowRuntimeBridge from "./WorkflowRuntimeBridge";

const { useActiveWorkflows, resumeAnalysisWorkflow, resumeIndustryChainWorkflow } = vi.hoisted(() => ({
  useActiveWorkflows: vi.fn(),
  resumeAnalysisWorkflow: vi.fn(),
  resumeIndustryChainWorkflow: vi.fn(),
}));
vi.mock("../api/queries", () => ({ useActiveWorkflows }));
vi.mock("../features/workflows/workflowRuntime", () => ({
  resumeAnalysisWorkflow,
  resumeIndustryChainWorkflow,
}));

const analysisJob = {
  id: "analysis-1",
  kind: "analysis",
  request: { code: "600519" },
};
const industryJob = {
  id: "industry-1",
  kind: "industry_chain",
  request: { name: "半导体", scope: {} },
};

describe("WorkflowRuntimeBridge", () => {
  beforeEach(() => vi.clearAllMocks());

  it("reattaches supported active workflows once", async () => {
    useActiveWorkflows.mockReturnValue({ data: [analysisJob, industryJob], isSuccess: true });
    const { rerender } = render(<WorkflowRuntimeBridge />);

    await waitFor(() => expect(resumeAnalysisWorkflow).toHaveBeenCalledWith(analysisJob));
    expect(resumeIndustryChainWorkflow).toHaveBeenCalledWith(industryJob);
    rerender(<WorkflowRuntimeBridge />);
    expect(resumeAnalysisWorkflow).toHaveBeenCalledOnce();
    expect(resumeIndustryChainWorkflow).toHaveBeenCalledOnce();
  });
});
