import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import AnalysisProgressSteps from "./AnalysisProgressSteps";

afterEach(cleanup);
describe("analysis stages", () => {
  it("names pending validation and archive stages while research runs", () => {
    render(<AnalysisProgressSteps stages={[{ stage: 1, name: "Agent 调研与证据校验", status: "started" }, null, null, null, null]} currentStageIndex={0} status="running" />);
    expect(screen.getByText("结果校验与数据时效")).toBeInTheDocument();
    expect(screen.getByText("报告归档与历史更新")).toBeInTheDocument();
  });
  it("shows persistence failure on the final stage", () => {
    render(<AnalysisProgressSteps stages={[null, null, null, null, { stage: 5, name: "报告归档与历史更新", status: "failed", detail: "保存失败，未完成" }]} currentStageIndex={4} status="error" />);
    expect(screen.getByText("保存失败，未完成")).toBeInTheDocument();
  });
});
