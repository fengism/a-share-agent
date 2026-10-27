import React from "react";
import { Tag, Tooltip } from "antd";

interface CitationMeta {
  label: string;
  tooltip: string;
  color: string;
}

const CITATION_DICTIONARY: Record<string, CitationMeta> = {
  analyze_financials: {
    label: "官方财报",
    tooltip: "数据源认证：经官方披露三张表与杜邦分析穿透校验",
    color: "blue",
  },
  get_interactive_qa: {
    label: "董秘互动问答",
    tooltip: "数据源认证：深交所互动易 / 上交所 e 互动董秘法定公开答复",
    color: "purple",
  },
  get_restricted_shares_lift: {
    label: "限售解禁",
    tooltip: "数据源认证：中登公司与巨潮资讯法定解禁日历及规模测算",
    color: "orange",
  },
  get_stock_valuation_detail: {
    label: "估值分位",
    tooltip: "数据源认证：PE/PB/PS 历史分位中枢与本地 DCF 贴现模型",
    color: "cyan",
  },
  get_stock_technical_indicators: {
    label: "量化动量",
    tooltip: "数据源认证：本地量化均线簇与动量指标实时推算",
    color: "geekblue",
  },
  compare_stocks: {
    label: "同业对比",
    tooltip: "数据源认证：同行业头部龙头公司相对估值与财务横向比对",
    color: "green",
  },
  get_stock_documents: {
    label: "研报/公告",
    tooltip: "数据源认证：巨潮资讯定期公告与主流券商研究所深度研报原件",
    color: "magenta",
  },
  get_hk_stock_profile: {
    label: "港股快照",
    tooltip: "数据源认证：港交所官方行情与公司资料",
    color: "gold",
  },
  get_hk_stock_industry_comparison: {
    label: "港股同业对比",
    tooltip: "数据源认证：港股通同行业对手估值与财务对比",
    color: "lime",
  },
  web_fetch: {
    label: "深度正文",
    tooltip: "数据源认证：权威公开网页与官方通告原文精读查验",
    color: "default",
  },
  read_pdf: {
    label: "PDF精读",
    tooltip: "数据源认证：官方公告与深度券商研报 PDF 结构化精读",
    color: "volcano",
  },
};

const CITATION_REGEX = /\[\^([^\]]+)\]/g;

export function renderWithCitations(text: string): React.ReactNode {
  if (!text || !text.includes("[^")) {
    return text;
  }

  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const regex = new RegExp(CITATION_REGEX);

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.slice(lastIndex, match.index));
    }
    const rawKey = match[1].trim();
    const meta = CITATION_DICTIONARY[rawKey] || {
      label: rawKey.replace(/^get_/, "").replace(/_/g, " "),
      tooltip: `数据源出处：${rawKey}`,
      color: "default",
    };

    elements.push(
      <Tooltip key={`cite-${match.index}`} title={meta.tooltip} trigger={["hover", "click"]}>
        <Tag
          color={meta.color}
          style={{
            marginInline: "3px 2px",
            fontSize: "10.5px",
            lineHeight: "16px",
            padding: "0 5px",
            borderRadius: "4px",
            cursor: "pointer",
            verticalAlign: "baseline",
            userSelect: "none",
          }}
        >
          {meta.label}
        </Tag>
      </Tooltip>
    );

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex));
  }

  return elements;
}
