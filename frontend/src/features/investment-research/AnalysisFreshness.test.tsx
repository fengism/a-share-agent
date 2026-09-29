import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import AnalysisFreshness from "./AnalysisFreshness";

afterEach(cleanup);
describe("analysis freshness", () => {
  it("does not claim old reports contain fresh data", () => {
    render(<AnalysisFreshness analysis={{}} />);
    expect(screen.getByText(/旧报告未记录数据时效/)).toBeInTheDocument();
  });
  it("distinguishes generation time, report period and unknown cache", async () => {
    render(<AnalysisFreshness analysis={{ generated_at: "2026-09-29T12:00:00", report_id: "a".repeat(32), provenance: {
      research_started_at: "2026-09-29T11:00:00", research_completed_at: "2026-09-29T11:50:00", report_regenerated: true,
      freshness_note: "重新生成不保证全部数据实时刷新", evidence: [
        { evidence_id: "e1", tool_name: "财报", sources: ["官方"], data_dates: [], report_periods: ["2026Q2"], cache_status: "unknown" },
      ],
    } }} />);
    fireEvent.click(screen.getByText(/查看 1 项证据/));
    expect(await screen.findByText("缓存状态未披露")).toBeInTheDocument();
    expect(screen.getByText("报告期：2026Q2")).toBeInTheDocument();
    expect(screen.getByText("数据/来源日期：未披露")).toBeInTheDocument();
  });
});
