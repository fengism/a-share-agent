import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import InvestmentResearch from ".";
import { stopAgentProcess, type AgentProcessState } from "../../features/agent-process/agentProcess";

const {
  useAnalysisPageData,
  useAnalysisHistorySnapshot,
  useAnalysisWorkflowController,
  useDeleteAnalysisHistory,
  usePdfExport,
  ensureFundamentalData,
  exportPdf,
  queryClient,
} = vi.hoisted(() => ({
  useAnalysisPageData: vi.fn(),
  useAnalysisHistorySnapshot: vi.fn(),
  useAnalysisWorkflowController: vi.fn(),
  useDeleteAnalysisHistory: vi.fn(),
  usePdfExport: vi.fn(),
  ensureFundamentalData: vi.fn(),
  exportPdf: vi.fn(),
  queryClient: {},
}));

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => queryClient,
}));
vi.mock("../../api/queries", () => ({
  ensureFundamentalData,
  useAnalysisPageData,
  useAnalysisHistorySnapshot,
  useDeleteAnalysisHistory,
  useInfiniteAllAnalysisHistory: () => ({ data: { pages: [] }, isLoading: false, isError: false }),
}));
vi.mock("../../hooks/useAnalysisWorkflowController", () => ({ useAnalysisWorkflowController }));
vi.mock("../../hooks/usePdfExport", () => ({
  usePdfExport,
}));
vi.mock("../../features/investment-research/AnalysisHistoryRail", () => ({
  default: () => <div>研究历史列表</div>,
}));
vi.mock("../../features/investment-research/ResearchFrameworkPanel", () => ({
  default: ({ analysis, onOpenValuation }: { analysis: AnalysisResult; onOpenValuation: () => void }) => (
    <div>
      <span>{analysis.research_framework ? "结构化研究报告" : "旧版研究报告"}</span>
      <button type="button" onClick={onOpenValuation}>查看估值明细</button>
    </div>
  ),
}));
vi.mock("../../features/investment-research/FinancialDataSections", () => ({
  default: ({ isExportingPdf }: { isExportingPdf: boolean }) => (
    <div data-pdf-financial-ready="true">
      <span>营收与毛利构成</span>
      <span>关键财务指标</span>
      <span>盈利与增长</span>
      <span>资产健康</span>
      <span>现金质量</span>
      <span data-pdf-revenue-ready="true" data-pdf-revenue-row-count="1">
        {isExportingPdf ? "财务导出模式" : "财务阅读模式"}
      </span>
      <span data-testid="pdf-key-financial-metrics" data-pdf-row-count="19" />
    </div>
  ),
}));
vi.mock("../../components/workflows/WorkflowWorkspace", () => ({
  default: ({ children, history }: { children: React.ReactNode; history: React.ReactNode }) => (
    <div>{children}<aside>{history}</aside></div>
  ),
}));

const analysis = {
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "20260826",
  research_framework: {},
} as unknown as AnalysisResult;

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}{location.hash}</span>;
}

function renderPage(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/stock/:code" element={<LocationProbe />} />
        <Route path="/investment-research/:code" element={<><InvestmentResearch /><LocationProbe /></>} />
        <Route path="/analysis/:code" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

function setupController(displayResult: AnalysisResult | null = null) {
  useAnalysisWorkflowController.mockReturnValue({
    displayResult,
    isAnalyzing: false,
    isCancelling: false,
    analysisError: null,
    stages: [],
    currentStageIndex: 0,
    agentProcess: { status: "", toolCalls: [], rounds: [] },
    runAnalysis: vi.fn(),
    cancelAnalysis: vi.fn(),
  });
}

describe("InvestmentResearch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    usePdfExport.mockReturnValue({ exportPdf, isExporting: false });
    useDeleteAnalysisHistory.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useAnalysisPageData.mockReturnValue({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() });
    useAnalysisHistorySnapshot.mockReturnValue({ data: undefined, isLoading: false, isError: false, refetch: vi.fn() });
    setupController();
  });

  it("presents the legacy deep link as a focused report view", () => {
    setupController(analysis);
    useAnalysisPageData.mockReturnValue({
      data: { stock_info: { code: "600519", name: "贵州茅台" }, cached_analysis: analysis },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderPage("/investment-research/600519");

    expect(screen.getByRole("heading", { name: /投资研究报告/ })).toBeInTheDocument();
    expect(screen.getByText("结构化研究报告")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /开始研究|重新研究|取消研究/ })).not.toBeInTheDocument();
  });

  it("renders a report and opens valuation in the full analysis page", () => {
    setupController(analysis);
    useAnalysisPageData.mockReturnValue({
      data: { stock_info: { code: "600519", name: "贵州茅台" }, cached_analysis: analysis },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderPage("/investment-research/600519?date=20260826");

    expect(screen.getByText("结构化研究报告")).toBeInTheDocument();
    expect(screen.getByText("历史快照 · 2026-08-26")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "查看估值明细" }));
    expect(screen.getByTestId("location")).toHaveTextContent(
      "/stock/600519?tab=valuation&date=20260826#stock-details",
    );
  });

  it("includes revenue breakdown and key financial metrics in the exported report", async () => {
    usePdfExport.mockReturnValue({ exportPdf, isExporting: true });
    setupController(analysis);
    useAnalysisPageData.mockReturnValue({
      data: { stock_info: { code: "600519", name: "贵州茅台" }, cached_analysis: analysis },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderPage("/investment-research/600519");

    expect(screen.getByText("营收与毛利构成")).toBeInTheDocument();
    expect(screen.getByText("关键财务指标")).toBeInTheDocument();
    expect(screen.getByText("盈利与增长")).toBeInTheDocument();
    expect(screen.getByText("资产健康")).toBeInTheDocument();
    expect(screen.getByText("现金质量")).toBeInTheDocument();
    expect(screen.getByText("财务导出模式")).toBeInTheDocument();
    const options = usePdfExport.mock.calls[0][0];
    expect(options.captureSelector).toBe("[data-pdf-group]");
    expect(options.isCaptureReady()).toBe(true);
    await options.beforeCapture();
    expect(ensureFundamentalData).toHaveBeenCalledWith(expect.anything(), "600519");
  });

  it("does not load the current aggregate while viewing a history snapshot", () => {
    setupController(analysis);
    renderPage("/investment-research/600519?date=20260826");

    expect(useAnalysisPageData).toHaveBeenCalledWith("600519", { enabled: false });
  });

  it("returns to the unified stock research workspace", () => {
    const runAnalysis = vi.fn();
    useAnalysisWorkflowController.mockReturnValue({
      displayResult: analysis,
      isAnalyzing: false,
      isCancelling: false,
      analysisError: null,
      stages: [],
      currentStageIndex: 0,
      agentProcess: { status: "", toolCalls: [], rounds: [] },
      runAnalysis,
      cancelAnalysis: vi.fn(),
    });
    useAnalysisPageData.mockReturnValue({
      data: { stock_info: { code: "600519", name: "贵州茅台" }, cached_analysis: analysis },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    });

    renderPage("/investment-research/600519");
    fireEvent.click(screen.getByRole("button", { name: /返回个股研究/ }));

    expect(screen.getByTestId("location")).toHaveTextContent("/analysis/600519?panel=research");
    expect(runAnalysis).not.toHaveBeenCalled();
  });

  it("canonicalizes invalid history dates", async () => {
    renderPage("/investment-research/600519?date=20260230");

    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent("/investment-research/600519");
      expect(screen.getByTestId("location")).not.toHaveTextContent("date=");
    });
  });

  it("points an empty report back to the unified workspace", () => {
    const runAnalysis = vi.fn();
    useAnalysisWorkflowController.mockReturnValue({
      displayResult: null,
      isAnalyzing: false,
      analysisError: null,
      stages: [],
      currentStageIndex: 0,
      agentProcess: { status: "", toolCalls: [], rounds: [] },
      runAnalysis,
      cancelAnalysis: vi.fn(),
    });

    renderPage("/investment-research/600519");
    expect(screen.getAllByRole("button", { name: /返回个股研究/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /返回个股研究/ }));

    expect(screen.getByTestId("location")).toHaveTextContent("/analysis/600519?panel=research");
    expect(runAnalysis).not.toHaveBeenCalled();
  });
  it.each(["cancelled", "detached"] as const)("preserves stopped research UI in the report view: %s", (termination) => {
    const process: AgentProcessState = {
      status: "采集证据中", toolCalls: [], activeRoundIndex: 1,
      rounds: [{
        roundIndex: 1, roundTotal: 3, status: "running", objective: "证据核验", evidenceGaps: [],
        toolNames: ["web_fetch"], toolSelectionReason: "获取正文", evidenceAdded: [], judgmentBasis: [],
        conclusion: "", nextStep: "", statusText: "执行中",
        toolCalls: [{ id: "fetch", name: "web_fetch", arguments: "{}", isExecuting: true }],
      }],
    };
    useAnalysisWorkflowController.mockReturnValue({
      displayResult: null, isAnalyzing: false, isCancelling: false, analysisError: null,
      stages: [{ stage: 1, name: "数据采集与证据校验", status: "started" }, null, null],
      currentStageIndex: 0, agentProcess: stopAgentProcess(process, termination, "研究已停止"),
    });
    const { container } = renderPage("/investment-research/600519");
    const toggle = screen.getByRole("button", { name: /Agent 思考与执行/ });
    expect(within(toggle).getByText(termination === "cancelled" ? "已停止" : "已停止等待")).toBeInTheDocument();
    fireEvent.click(toggle);
    expect(screen.getByText("数据采集与证据校验")).toBeInTheDocument();
    expect(screen.getByLabelText("第 1 轮调研")).toBeInTheDocument();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
    expect(container.querySelector(".ant-spin-spinning")).toBeNull();
    expect(container.querySelector(".ant-steps-item-process")).toBeNull();
  });

});
