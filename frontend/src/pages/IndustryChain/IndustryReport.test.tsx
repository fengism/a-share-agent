import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { IndustryChainResult } from "../../types/stock";
import IndustryReport from "./IndustryReport";

vi.mock("@ant-design/icons", () => ({
  ApartmentOutlined: () => <span />,
  CloudUploadOutlined: () => <span />,
  FullscreenOutlined: () => <span />,
  SendOutlined: () => <span />,
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
    render(
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
      trends: [{ title: "机架级交付", detail: "整机向系统交付升级" }],
      capital_moves: [{ title: "扩产", detail: "头部厂商扩建产线" }],
      key_events: [{ date: "2026-01", title: "运营商集采", impact: "拉动国产服务器需求" }],
      key_stocks: [{ name: "浪潮信息", code: "000977", description: "整机龙头" }],
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

    render(
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
    expect(screen.getByText("运营商集采")).toBeInTheDocument();
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
  });

  it("shows degraded quality and archive warnings", () => {
    render(
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
