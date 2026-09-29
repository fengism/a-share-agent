import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import { apiGet } from "../../api/client";
import AnalysisReportVersions from "./AnalysisReportVersions";

vi.mock("../../api/client", () => ({ apiGet: vi.fn() }));
vi.mock("./ResearchFrameworkPanel", () => ({ default: ({ analysis }: { analysis: AnalysisResult }) => <div>版本正文：{analysis.report_id}</div> }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const analysis = { stock_code: "600519", analysis_date: "20260929", report_id: "b".repeat(32) } as AnalysisResult;
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><AnalysisReportVersions analysis={analysis} /></QueryClientProvider>);
  return client;
}

describe("same-day versions", () => {
  it("only requests versions on demand and opens the selected immutable snapshot", async () => {
    const id = "a".repeat(32);
    vi.mocked(apiGet).mockResolvedValueOnce([{ report_id: id, generated_at: "2026-09-29T10:00:00", overall_rating: 5 }])
      .mockResolvedValueOnce({ ...analysis, report_id: id, overall_summary: "早盘总结" });
    const client = setup();
    expect(apiGet).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "查看同日报告版本" }));
    fireEvent.mouseDown(await screen.findByRole("combobox", { name: "报告版本" }));
    fireEvent.click(await screen.findByText(/2026-09-29T10:00:00/));
    expect(await screen.findByText("早盘总结")).toBeInTheDocument();
    expect(screen.getByText(`版本正文：${id}`)).toBeInTheDocument();
    expect(apiGet).toHaveBeenLastCalledWith(`/analysis/600519/versions/20260929/${id}`, undefined, expect.anything());
    client.clear();
  });
  it("shows a retryable failure instead of an empty version list", async () => {
    vi.mocked(apiGet).mockRejectedValue(new Error("offline"));
    const client = setup();
    fireEvent.click(screen.getByRole("button", { name: "查看同日报告版本" }));
    expect(await screen.findByText("版本列表加载失败")).toBeInTheDocument();
    expect(screen.queryByText(/暂无独立版本/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /重.*试/ }));
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
    client.clear();
  });
});
