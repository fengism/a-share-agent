import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});

function renderReport(ui: React.ReactElement) {
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}
import type { IndustryChainResult } from "../../types/stock";
import IndustryReport from "./IndustryReport";

vi.mock("@ant-design/icons", () => ({
  AimOutlined: () => <span />,
  ApartmentOutlined: () => <span />,
  BankOutlined: () => <span />,
  CloudUploadOutlined: () => <span />,
  DatabaseOutlined: () => <span />,
  FileTextOutlined: () => <span />,
  FullscreenOutlined: () => <span />,
  RiseOutlined: () => <span />,
  SendOutlined: () => <span />,
  WarningOutlined: () => <span />,
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => true,
}));

const result: IndustryChainResult = {
  name: "AI 芯片",
  summary: "产业链摘要",
  upstream: [],
  midstream: [],
  downstream: [],
  drivers: [],
  risks: [],
  key_stocks: [],
  llm_review: "报告正文",
  charts: [],
};

describe("IndustryReport", () => {
  it("passes the edited Feishu receiver to the push action", async () => {
    const onPush = vi.fn().mockResolvedValue(undefined);
    renderReport(
      <IndustryReport
        result={result}
        activeName="AI 芯片"
        archiveId="archive-1"
        defaultReceiver="ou_default"
        isPushing={false}
        pushResult={null}
        onPush={onPush}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "推送" }));
    const receiverInput = await screen.findByDisplayValue("ou_default");
    fireEvent.change(receiverInput, { target: { value: "  ou_custom  " } });
    fireEvent.click(screen.getByRole("button", { name: /推送到飞书/ }));

    await waitFor(() => expect(onPush).toHaveBeenCalledWith("feishu", "ou_custom"));
  });

  it("renders the structured industry research sections", () => {
    const structuredResult: IndustryChainResult = {
      ...result,
      aliases: ["AI Server"],
      positioning: "连接上游算力芯片与下游云厂商",
      market_metrics: [{ label: "全球市场规模", value: "2050 亿美元", period: "2024", growth: "+30%", source: "IDC" }],
      competition: [{
        market: "中国市场",
        summary: "头部厂商集中",
        companies: [{ name: "浪潮信息", code: "000977", role: "服务器整机", market_share: "30.8%" }],
      }],
      technology_routes: [{ title: "液冷", detail: "高功率机柜的关键散热路线", source: "液冷白皮书", source_url: "https://example.com/cooling" }],
      upstream: [{ name: "算力芯片", companies: ["海光信息"], source: "公司公告", source_url: "https://example.com/chip" }],
      midstream: [{ name: "服务器集成", companies: ["浪潮信息"] }],
      downstream: [{ name: "云计算", companies: ["阿里云"] }],
      trends: [
        { title: "机架级交付", detail: "整机向系统交付升级" },
        { title: "液冷渗透", detail: "高密度机柜加速液冷采用" },
        { title: "高速互连", detail: "集群规模提升网络价值量" },
        { title: "算电协同", detail: "能源系统成为扩容约束" },
      ],
      capital_moves: [{ title: "扩产", detail: "头部厂商扩建产线" }],
      key_events: [{ date: "2026-01", title: "运营商集采", impact: "拉动国产服务器需求" }],
      key_stocks: [
        { name: "浪潮信息", code: "000977", description: "整机龙头" },
        { name: "中科曙光", code: "603019", description: "服务器厂商" },
        { name: "海光信息", code: "688041", description: "国产算力芯片" },
        { name: "工业富联", code: "601138", description: "AI服务器制造" },
        { name: "中际旭创", code: "300308", description: "高速光模块" },
        { name: "新易盛", code: "300502", description: "高速光模块" },
        { name: "英维克", code: "002837", description: "液冷温控" },
      ],
      drivers: ["算力资本开支增长"],
      risks: ["上游芯片供应波动"],
      sources: [{ title: "服务器市场报告", publisher: "IDC", date: "2025" }],
      evidence_catalog: [{
        evidence_id: "ev_report",
        tool_name: "fetch_url",
        arguments: '{"url":"https://example.com/report"}',
        title: "服务器产业白皮书",
        source_urls: ["https://example.com/report"],
        published_at: "2026-08-01",
        fetched_at: "2026-08-18T10:00:00Z",
        truncated: false,
        content_preview: "服务器产业链正文摘要",
      }],
      evidence_stats: {
        total_count: 8,
        unique_count: 6,
        selected_count: 4,
        omitted_count: 4,
        failed_count: 1,
        prompt_characters: 18000,
      },
      research_scope: {
        region: "global",
        start_date: "2026-02-16",
        end_date: "2026-08-18",
        company_scope: "all_public",
      },
      coverage: { market: "partial", chain: "complete", companies: "missing" },
      missing_evidence: ["缺少中国市场实际规模"],
      conflicts: [{
        topic: "全球市场规模",
        values: ["100 亿美元", "130 亿美元"],
        reason: "统计范围不同",
        evidence_ids: ["ev_report"],
      }],
    };

    renderReport(
      <IndustryReport
        result={structuredResult}
        activeName="AI 服务器"
        archiveId="archive-2"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    expect(screen.getByText("市场规模与增长")).toBeInTheDocument();
    expect(screen.getByText("竞争格局")).toBeInTheDocument();
    expect(screen.getByText("产业链地图")).toBeInTheDocument();
    expect(screen.getByText("关键趋势与催化剂")).toBeInTheDocument();
    expect(screen.getByText("算电协同")).toBeInTheDocument();
    expect(screen.getByText("运营商集采")).toBeInTheDocument();
    expect(screen.getByText("英维克")).toBeInTheDocument();
    expect(screen.getByText("数据来源与口径")).toBeInTheDocument();
    expect(screen.getByText(/研究范围：全球 · 2026-02-16 至 2026-08-18 · 全部公开公司/)).toBeInTheDocument();
    expect(screen.getByText("重点公司")).toBeInTheDocument();
    expect(screen.getByText("研究覆盖与证据缺口")).toBeInTheDocument();
    expect(screen.getByText("缺少中国市场实际规模")).toBeInTheDocument();
    expect(screen.getByText("统计范围不同")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "来源：液冷白皮书" })).toHaveAttribute("href", "https://example.com/cooling");
    expect(screen.getByRole("link", { name: "来源：公司公告" })).toHaveAttribute("href", "https://example.com/chip");
    expect(screen.getByText("工具证据目录")).toBeInTheDocument();
    expect(screen.getByText("服务器产业白皮书")).toBeInTheDocument();
    expect(screen.getByText("ev_report")).toBeInTheDocument();
    expect(screen.getByText(/共 8 次调用 · 去重后 6 条 · 合成使用 4 条/)).toBeInTheDocument();

    const detailedResearch = screen.getByRole("region", { name: "详细分析" });
    expect(detailedResearch.querySelectorAll(".ant-card")).toHaveLength(0);
    expect(detailedResearch.querySelector(".industry-chain-flow")).toBeInTheDocument();
    expect(detailedResearch.querySelectorAll(".industry-chain-node.is-framed")).toHaveLength(7);
    const moreDisclosures = detailedResearch.querySelectorAll("details.industry-research-more");
    expect(moreDisclosures).toHaveLength(0);

    const researchAudit = screen.getByRole("region", { name: "研究依据" });
    const auditDisclosures = researchAudit.querySelectorAll("details.industry-research-audit");
    expect(auditDisclosures).toHaveLength(3);
    auditDisclosures.forEach((disclosure) => expect(disclosure).not.toHaveAttribute("open"));
  });

  it("organizes the decision summary before detailed research", () => {
    const structuredResult: IndustryChainResult = {
      ...result,
      positioning: "连接上游算力芯片与下游云厂商",
      market_metrics: [
        { label: "全球市场规模", value: "2050 亿美元", growth: "+30%" },
      ],
      driver_insights: [{
        title: "资本开支持续扩张",
        detail: "云厂商继续增加基础设施投入",
        confidence: "high",
      }],
      risk_insights: [{
        title: "利用率不及预期",
        detail: "供需错配可能压低资产回报",
        confidence: "medium",
      }],
      key_stocks: [{
        name: "浪潮信息",
        code: "000977",
        role: "服务器整机",
      }],
      coverage: {
        market: "complete",
        competition: "partial",
        technology: "partial",
        chain: "complete",
        companies: "complete",
        events: "partial",
      },
    };

    const { container } = renderReport(
      <IndustryReport
        result={structuredResult}
        activeName="AI 芯片"
        archiveId="archive-3"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    const conclusion = screen.getByRole("region", { name: "产业链结论摘要" });
    expect(within(conclusion).getByRole("heading", { name: "结论摘要" })).toBeInTheDocument();
    expect(within(conclusion).getByText("01 · 产业研判")).toBeInTheDocument();
    expect(within(conclusion).getByText("产业链摘要")).toBeInTheDocument();
    expect(within(conclusion).getByText("全球市场规模")).toBeInTheDocument();
    expect(within(conclusion).getByText("资本开支持续扩张")).toBeInTheDocument();
    expect(within(conclusion).getByText("利用率不及预期")).toBeInTheDocument();
    expect(within(conclusion).getByText("浪潮信息")).toBeInTheDocument();
    expect(within(conclusion).getByText("证据部分覆盖")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "详细分析" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "研究依据" })).toBeInTheDocument();
    expect(screen.getByText(/项要点/)).toBeInTheDocument();
    expect(screen.getAllByText(/个模块/)).toHaveLength(2);

    const chapterNav = screen.getByRole("navigation", { name: "报告章节导航" });
    expect(within(chapterNav).getByRole("link", { name: /01.*产业研判/ })).toHaveAttribute("href", "#industry-judgment");
    expect(within(chapterNav).getByRole("link", { name: /02.*详细分析/ })).toHaveAttribute("href", "#industry-detail");
    expect(within(chapterNav).getByRole("link", { name: /03.*研究依据/ })).toHaveAttribute("href", "#industry-audit");
    expect(within(chapterNav).getByRole("link", { name: /04.*完整正文/ })).toHaveAttribute("href", "#industry-full-report");

    const fullReport = screen.getByText("04 · 完整研究正文").closest(".ant-collapse-item");
    expect(fullReport).not.toHaveClass("ant-collapse-item-active");
    expect(container.querySelector(".industry-conclusion")).toBeInTheDocument();
  });

  it("shows degraded quality and archive warnings", () => {
    renderReport(
      <IndustryReport
        result={{
          ...result,
          quality_status: "degraded",
          archive_status: "failed",
          warnings: ["报告已生成，但保存失败"],
        }}
        activeName="AI 芯片"
        archiveId=""
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    expect(screen.getByText("报告未保存")).toBeInTheDocument();
    expect(screen.getByText("报告已生成，但保存失败")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "推送" })).toBeDisabled();
  });
});
