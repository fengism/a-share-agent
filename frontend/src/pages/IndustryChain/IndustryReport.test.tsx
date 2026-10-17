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
  FileSearchOutlined: () => <span />,
  AimOutlined: () => <span />,
  ApartmentOutlined: () => <span />,
  BankOutlined: () => <span />,
  CloudUploadOutlined: () => <span />,
  CopyOutlined: () => <span />,
  DatabaseOutlined: () => <span />,
  DownOutlined: () => <span />,
  DownloadOutlined: () => <span />,
  FileMarkdownOutlined: () => <span />,
  FilePdfOutlined: () => <span />,
  FileTextOutlined: () => <span />,
  FullscreenOutlined: () => <span />,
  HistoryOutlined: () => <span />,
  RiseOutlined: () => <span />,
  SendOutlined: () => <span />,
  TableOutlined: () => <span />,
  TrophyOutlined: () => <span />,
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
        tool_name: "web_fetch",
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
    expect(within(screen.getByRole("region", { name: "关系传导与公司验证" })).getByText("英维克")).toBeInTheDocument();
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
    expect(screen.queryByText(/ev_report/)).not.toBeInTheDocument();
    expect(screen.getByText("资料 1")).toBeInTheDocument();
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

  it("keeps long conclusion content inside shrinkable wrapping containers", () => {
    const longChinese = "产业链核心驱动来自需求增长与供给改善并需要持续跟踪验证".repeat(6);
    const longEnglish = "ContinuousUnbrokenCompanyIdentifier".repeat(8);
    const longEvidenceTitle = "VeryLongEvidenceSourceTitleWithoutNaturalBreakpoints".repeat(6);
    const longUrl = `https://example.com/${"long-path-segment".repeat(12)}`;
    const wrappingResult: IndustryChainResult = {
      ...result,
      positioning: longChinese,
      driver_insights: [{
        title: "需求增长（证据 ev_long_title）",
        detail: `${longChinese} ${longUrl}`,
        confidence: "high",
      }],
      key_stocks: [{
        name: longEnglish,
        code: "000001",
        description: longChinese,
      }],
      evidence_catalog: [{
        evidence_id: "ev_long_title",
        tool_name: "web_fetch",
        arguments: JSON.stringify({ url: longUrl }),
        title: longEvidenceTitle,
        source_urls: [longUrl],
        fetched_at: "2026-09-02T12:00:00Z",
        truncated: false,
      }],
    };

    renderReport(
      <IndustryReport
        result={wrappingResult}
        activeName="AI 芯片"
        archiveId="archive-long-content"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    const conclusion = screen.getByRole("region", { name: "产业链结论摘要" });
    const evidenceLink = within(conclusion).getByRole("link", { name: longEvidenceTitle });
    const insightHeading = evidenceLink.closest(".industry-conclusion__item-heading");

    expect(evidenceLink).toHaveClass("industry-evidence-link");
    expect(evidenceLink.closest("strong")).toHaveClass("industry-conclusion__item-title");
    expect(insightHeading).toBeInTheDocument();
    expect(within(insightHeading as HTMLElement).getByText("高置信度")).toHaveClass(
      "industry-conclusion__confidence",
    );
    expect(within(conclusion).getByText(longEnglish)).toHaveClass(
      "industry-conclusion__item-title",
    );
    expect(within(conclusion).getAllByText(longChinese).length).toBeGreaterThan(0);
  });

  it("marks long chain, stock, table, header, and evidence content as wrappable", async () => {
    const longMetric = "营收同比增长与海外业务占比持续提升".repeat(8);
    const longMarketShare = "全球细分市场占有率与国内市场占有率".repeat(6);
    const longRole = "核心零部件研发制造与全球供应链协同".repeat(6);
    const longCompany = "ContinuousUnbrokenCompanyIdentifier".repeat(7);
    const longAlias = "VeryLongIndustryAliasWithoutNaturalBreakpoints".repeat(5);
    const longEvidenceId = `ev_${"longidentifier".repeat(12)}`;
    const longReportName = "VeryLongIndustryReportNameWithoutNaturalBreakpoints".repeat(5);
    const longMetricLabel = "VeryLongMetricLabelWithoutNaturalBreakpoints".repeat(5);
    const longMetricValue = "VeryLongMetricValueWithoutNaturalBreakpoints".repeat(5);
    const longMetricPeriod = "VeryLongMetricPeriodWithoutNaturalBreakpoints".repeat(5);
    const longSource = "VeryLongSourcePublisherWithoutNaturalBreakpoints".repeat(5);
    const longSourceTitle = "VeryLongSourceTitleWithoutNaturalBreakpoints".repeat(5);
    const longWarning = "VeryLongQualityWarningWithoutNaturalBreakpoints".repeat(5);
    const wrappingResult: IndustryChainResult = {
      ...result,
      name: longReportName,
      aliases: [longAlias],
      warnings: [longWarning],
      market_metrics: [{
        label: longMetricLabel,
        value: longMetricValue,
        period: longMetricPeriod,
        source: longSource,
      }],
      sources: [{
        title: longSourceTitle,
        publisher: longSource,
        date: longMetricPeriod,
      }],
      research_scope: {
        company_scope: "a_share",
        region_scope: "中国大陆与全球供应链市场".repeat(5),
      },
      upstream: [{
        name: "超长上游环节名称".repeat(8),
        role: longRole,
        companies: [longCompany],
        market_share: longMarketShare,
        metric: longMetric,
        evidence_ids: [longEvidenceId],
      }],
      key_stocks: [{
        name: "超长重点公司名称".repeat(8),
        code: "000001",
        role: longRole,
        companies: [longCompany],
        market_share: longMarketShare,
        metric: longMetric,
      }],
      evidence_catalog: [{
        evidence_id: longEvidenceId,
        tool_name: "VeryLongToolProviderNameWithoutNaturalBreakpoints".repeat(4),
        title: "超长证据标题".repeat(12),
        source_urls: [],
        fetched_at: "2026-09-02T12:00:00Z",
        truncated: false,
      }],
    };

    const { container } = renderReport(
      <IndustryReport
        result={wrappingResult}
        activeName="AI 芯片"
        archiveId="archive-wrapping-content"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    expect(container.querySelector(".industry-report__title")).toHaveTextContent(
      `${longReportName} 产业链`,
    );
    expect(screen.getByText(longAlias)).toHaveClass("industry-report__wrap-tag");
    expect(screen.getByText(/研究范围：/)).toHaveClass("industry-report__scope-summary");
    expect(screen.getByText(longWarning)).toHaveClass("industry-report__warning");
    expect(
      screen.getAllByText(longMetricLabel).filter((element) =>
        element.classList.contains("industry-conclusion__metric-label"),
      ),
    ).toHaveLength(1);
    expect(
      screen.getAllByText(longMetricValue).filter((element) =>
        element.classList.contains("industry-conclusion__metric-value"),
      ),
    ).toHaveLength(1);
    expect(screen.getByText(longSourceTitle)).toHaveClass("industry-source-list__title");
    expect(screen.getByText(`${longSource} · ${longMetricPeriod}`)).toHaveClass(
      "industry-source-list__meta",
    );
    screen.getAllByText(`来源：${longSource}`).forEach((source) => {
      expect(source).toHaveClass("industry-source-label");
    });
    expect(screen.getAllByText(`${longMarketShare} · ${longMetric}`)).toHaveLength(2);
    screen.getAllByText(`${longMarketShare} · ${longMetric}`).forEach((metric) => {
      expect(metric).toHaveClass("industry-chain-node__metric");
    });
    expect(
      screen.getAllByText(longRole).filter((role) =>
        role.classList.contains("industry-chain-node__tag"),
      ),
    ).toHaveLength(2);
    expect(screen.getAllByText(`${longCompany} ↗`).every((company) => company.classList.contains("industry-chain-node__tag"))).toBe(true);
    expect(screen.queryByText(new RegExp(longEvidenceId))).not.toBeInTheDocument();
    expect(screen.getByText("关联 1 项资料")).toHaveClass("industry-wrap-tag");

    fireEvent.click(screen.getByText("📋 环节清单"));

    await waitFor(() => {
      expect(container.querySelector(".industry-chain-table")).toBeInTheDocument();
    });
    const chainTable = container.querySelector(".industry-chain-table") as HTMLElement;
    expect(within(chainTable).getByText(`${longMarketShare} · ${longMetric}`)).toHaveClass(
      "industry-chain-table__tag",
    );
    expect(within(chainTable).getByText(longRole)).toHaveClass("industry-chain-table__tag");
    expect(within(chainTable).getByText(`${longCompany} ↗`)).toHaveClass(
      "industry-chain-table__tag",
    );
  });

  it("renders topic resolution, report changes, opportunity map, and runtime metadata", async () => {
    const enhancedResult: IndustryChainResult = {
      ...result,
      topic_resolution: {
        requested_name: "AI 芯片",
        normalized_name: "智能算力芯片",
        possible_topics: ["人工智能", "半导体"],
        boundary_note: "当前主题可能对应多个板块口径，请确认研究边界。",
      },
      changes: {
        previous_archive_id: "archive-previous",
        has_changes: true,
        added_count: 1,
        removed_count: 0,
        updated_count: 0,
        items: [{
          category: "company",
          change_type: "added",
          title: "新增公司",
          after: "产业链新增标的",
        }],
      },
      opportunities: [{
        name: "示例公司",
        code: "000001",
        role: "核心供应商",
        prosperity_score: 18,
        earnings_score: 17,
        valuation_score: 12,
        catalyst_score: 14,
        evidence_score: 15,
        risk_score: 6,
        total_score: 73,
        rationale: "需求增长与份额提升。",
      }],
      analysis_metadata: {
        total_duration_ms: 12_500,
        research_duration_ms: 8_000,
        synthesis_duration_ms: 3_500,
        draft_duration_ms: 1_500,
        verification_duration_ms: 1_200,
        finalization_duration_ms: 800,
        archive_duration_ms: 1_000,
        cache_hits: ["technology"],
        cache_misses: ["market", "events"],
        failed_dimensions: ["events"],
        successful_dimensions: ["market", "technology"],
        agent_evidence_count: 7,
        public_item_count: 11,
        independent_source_count: 5,
      },
    };

    renderReport(
      <IndustryReport
        result={enhancedResult}
        activeName="AI 芯片"
        archiveId="archive-current"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    expect(screen.getByText("智能算力芯片 产业链")).toBeInTheDocument();
    expect(screen.getByText("研究主题存在多种口径")).toBeInTheDocument();
    expect(screen.getByText("当前主题可能对应多个板块口径，请确认研究边界。")).toBeInTheDocument();
    expect(screen.getByText("人工智能")).toBeInTheDocument();
    expect(screen.getByText("半导体")).toBeInTheDocument();

    expect(screen.getByRole("region", { name: "较上一版变化" })).toHaveTextContent(
      "新增 1 · 更新 0 · 移除 0",
    );
    fireEvent.click(screen.getByText("查看 1 项变化"));
    expect(await screen.findByText("新增公司")).toBeInTheDocument();

    expect(screen.getByRole("region", { name: "公司研究资料" })).toBeInTheDocument();
    expect(screen.getByText("按资料完整度排列，不代表投资价值或收益预期")).toBeInTheDocument();
    expect(screen.getByText("示例公司")).toBeInTheDocument();
    expect(screen.getByText("旧版评分已停用")).toBeInTheDocument();
    expect(screen.queryByText("73 分")).not.toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "运行信息" })).toBeInTheDocument();
    expect(screen.getByText("12.5 s")).toBeInTheDocument();
    expect(screen.getByText("1.50 s")).toBeInTheDocument();
    expect(screen.getByText("1.20 s")).toBeInTheDocument();
    expect(screen.getByText("800 ms")).toBeInTheDocument();
    expect(screen.getByText("5 个")).toBeInTheDocument();
    expect(screen.getByText("缓存命中：技术路线")).toBeInTheDocument();
    expect(screen.getByText("本次刷新：市场、事件")).toBeInTheDocument();
    expect(screen.getByText("失败维度：事件")).toBeInTheDocument();
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

  it("supports copying industry report and exporting markdown via dropdown", () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextSpy,
      },
    });
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderReport(
      <IndustryReport
        result={result}
        activeName="AI 芯片"
        archiveId="archive-1"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    // Test copy
    const copyBtn = screen.getByRole("button", { name: "复制研报" });
    fireEvent.click(copyBtn);
    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("AI 芯片 产业链投研报告"));

    // Test export markdown via dropdown
    const exportBtn = screen.getByRole("button", { name: "导出" });
    fireEvent.click(exportBtn);
    const exportMdItem = screen.getByText("导出为 Markdown (.md)");
    fireEvent.click(exportMdItem);
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("supports exporting key stocks list via dropdown as CSV", () => {
    window.URL.createObjectURL = vi.fn(() => "blob:mock-csv-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    const resultWithStocks: IndustryChainResult = {
      ...result,
      key_stocks: [
        { name: "中际旭创", code: "300308", role: "光模块龙头", total_market_cap: "1200亿", pe: "35.5x", pb: "8.2" },
      ],
    };

    renderReport(
      <IndustryReport
        result={resultWithStocks}
        activeName="CPO"
        archiveId="archive-cpo"
        isPushing={false}
        pushResult={null}
        onPush={vi.fn()}
      />,
    );

    const exportBtn = screen.getByRole("button", { name: "导出" });
    fireEvent.click(exportBtn);
    const exportCsvItem = screen.getByText("导出重点公司 (.csv)");
    fireEvent.click(exportCsvItem);
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});
