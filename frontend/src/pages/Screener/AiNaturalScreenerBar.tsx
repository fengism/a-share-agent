import React, { useState } from "react";
import { Input, Button, Space, Tag, message, Tooltip } from "antd";
import { ThunderboltOutlined, RobotOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ScreenerFilter } from "../../types/stock";
import * as uiStyles from "../../styles/ui";

const DEFAULT_COLORS = {
  primary: "#1677ff",
  textPrimary: "rgba(0, 0, 0, 0.88)",
  textMuted: "rgba(0, 0, 0, 0.45)",
  up: "#f5222d",
  down: "#52c41a",
};

interface AiNaturalScreenerBarProps {
  currentFilters: ScreenerFilter;
  onApplyFilters: (patch: Partial<ScreenerFilter>) => void;
  onSearch: () => void;
  industries?: string[];
  concepts?: string[];
}

export interface ParsedFilterResult {
  patch: Partial<ScreenerFilter>;
  matchedExplanations: string[];
}

export function parseNaturalLanguageToFilters(
  text: string,
  availableIndustries: string[] = [],
  availableConcepts: string[] = [],
): ParsedFilterResult {
  const patch: Partial<ScreenerFilter> = {};
  const matchedExplanations: string[] = [];
  const lower = text.toLowerCase();

  // 1. 市值
  const capMinMatch = text.match(/(?:市值|流通市值)(?:大于|超过|>|高于)(\d+)(?:亿)?/);
  if (capMinMatch) {
    patch.market_cap_min = Number(capMinMatch[1]);
    matchedExplanations.push(`市值 ≥ ${capMinMatch[1]}亿`);
  }
  const capMaxMatch = text.match(/(?:市值|流通市值)(?:小于|低于|<)(\d+)(?:亿)?/);
  if (capMaxMatch) {
    patch.market_cap_max = Number(capMaxMatch[1]);
    matchedExplanations.push(`市值 ≤ ${capMaxMatch[1]}亿`);
  }

  // 2. PE
  const peMaxMatch = text.match(/(?:pe|市盈率|pe_ttm)(?:低于|小于|<|不超过)(\d+)/i);
  if (peMaxMatch) {
    patch.pe_max = Number(peMaxMatch[1]);
    matchedExplanations.push(`PE(TTM) ≤ ${peMaxMatch[1]}`);
  }
  const peMinMatch = text.match(/(?:pe|市盈率|pe_ttm)(?:高于|大于|>|超过)(\d+)/i);
  if (peMinMatch) {
    patch.pe_min = Number(peMinMatch[1]);
    matchedExplanations.push(`PE(TTM) ≥ ${peMinMatch[1]}`);
  }

  // 3. PB / 破净
  if (lower.includes("破净")) {
    patch.is_broken_net = true;
    patch.pb_max = 1.0;
    matchedExplanations.push("破净股 (PB ≤ 1.0)");
  } else {
    const pbMaxMatch = text.match(/(?:pb|市净率)(?:低于|小于|<|不超过)(\d+(?:\.\d+)?)/i);
    if (pbMaxMatch) {
      patch.pb_max = Number(pbMaxMatch[1]);
      matchedExplanations.push(`PB ≤ ${pbMaxMatch[1]}`);
    }
  }

  // 4. 换手率
  const turnoverMatch = text.match(/(?:换手率|换手)(?:大于|高于|>|超过)(\d+(?:\.\d+)?)(?:%)?/);
  if (turnoverMatch) {
    patch.turnover_pct_min = Number(turnoverMatch[1]);
    matchedExplanations.push(`换手率 ≥ ${turnoverMatch[1]}%`);
  }

  // 5. 涨跌幅
  const changeMatch = text.match(/(?:涨跌幅|涨幅)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)(?:%)?/);
  if (changeMatch) {
    patch.change_pct_min = Number(changeMatch[1]);
    matchedExplanations.push(`涨幅 ≥ ${changeMatch[1]}%`);
  }

  // 6. 60日涨幅
  const change60Match = text.match(/(?:60日涨幅|两月涨幅|中期涨幅)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)(?:%)?/);
  if (change60Match) {
    patch.change_pct_60d_min = Number(change60Match[1]);
    matchedExplanations.push(`60日涨幅 ≥ ${change60Match[1]}%`);
  }

  // 7. 量比
  const volumeRatioMatch = text.match(/(?:量比)(?:大于|超过|>|高于)(\d+(?:\.\d+)?)/);
  if (volumeRatioMatch) {
    patch.volume_ratio_min = Number(volumeRatioMatch[1]);
    matchedExplanations.push(`量比 ≥ ${volumeRatioMatch[1]}`);
  }

  // 8. 剔除ST
  if (/(?:剔除st|不含st|非st|无st)/i.test(text)) {
    patch.exclude_st = true;
    matchedExplanations.push("剔除ST风险股");
  }

  // 9. 匹配行业
  const matchedIndustries: string[] = [];
  availableIndustries.forEach((ind) => {
    if (ind && ind.length >= 2 && text.includes(ind)) {
      matchedIndustries.push(ind);
    }
  });
  if (matchedIndustries.length > 0) {
    patch.industries = matchedIndustries;
    matchedExplanations.push(`行业: ${matchedIndustries.join("、")}`);
  }

  // 10. 匹配概念
  const matchedConcepts: string[] = [];
  availableConcepts.forEach((c) => {
    if (c && c.length >= 2 && text.includes(c)) {
      matchedConcepts.push(c);
    }
  });
  if (matchedConcepts.length > 0) {
    patch.concepts = matchedConcepts;
    matchedExplanations.push(`概念: ${matchedConcepts.join("、")}`);
  }

  return { patch, matchedExplanations };
}

const PRESET_PROMPTS = [
  "市值大于500亿、PE小于20的高股息蓝筹",
  "破净股、市值大于100亿且剔除ST",
  "换手率大于5%、涨幅大于3%的放量突破",
  "PE小于35、60日涨幅大于20%的成长股",
];

export const AiNaturalScreenerBar: React.FC<AiNaturalScreenerBarProps> = ({
  onApplyFilters,
  onSearch,
  industries = [],
  concepts = [],
}) => {
  const [promptText, setPromptText] = useState("");
  const navigate = useNavigate();
  const c = typeof uiStyles.useColors === "function" ? uiStyles.useColors() : DEFAULT_COLORS;

  const handleApplyParse = (query: string = promptText) => {
    if (!query.trim()) {
      message.info("请输入选股诉求或点击推荐词");
      return;
    }
    const { patch, matchedExplanations } = parseNaturalLanguageToFilters(query, industries, concepts);

    if (matchedExplanations.length === 0) {
      message.warning("未能识别到具体量化指标条件，您可以尝试「问 AI 选股」获得综合投研解答");
      return;
    }

    onApplyFilters({ ...patch, page: 1 });
    onSearch();
    message.success(`已应用 ${matchedExplanations.length} 项量化条件：${matchedExplanations.join(" · ")}`);
  };

  const handleAskAi = () => {
    const text = promptText.trim() || "请推荐当前 A 股市场估值具备安全边际且资金活跃度上升的优质标的";
    const prompt = `请根据我的选股需求进行全方位智能研选：\n「${text}」\n请给出符合逻辑的筛选标准、选股理由、风险防范与首选个股标的推荐。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  return (
    <div
      style={{
        marginBottom: 12,
        padding: "var(--c-pad-inset, 7px 12px)",
        background: "var(--c-fill-quaternary, rgba(22, 119, 255, 0.03))",
        border: "1px dashed var(--c-primary, #1677ff)",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
        <span
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: c.primary,
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          <ThunderboltOutlined />
          AI 语义选股助手
        </span>
        <span style={{ fontSize: 12, color: c.textMuted }}>
          支持自然语言自动提取指标或直达大模型投研
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Input
          value={promptText}
          onChange={(e) => setPromptText(e.target.value)}
          onPressEnter={() => handleApplyParse()}
          placeholder="例如：寻找市值大于500亿、PE小于20、剔除ST的高股息蓝筹"
          style={{ flex: 1, minWidth: 260 }}
          allowClear
          prefix={<ThunderboltOutlined style={{ color: c.primary }} />}
        />
        <Space size={6}>
          <Button
            type="primary"
            icon={<ArrowRightOutlined />}
            onClick={() => handleApplyParse()}
          >
            解析并筛选
          </Button>
          <Tooltip title="将选股需求带入 Chat 助手进行深度逻辑研判与行业分析">
            <Button
              icon={<RobotOutlined />}
              onClick={handleAskAi}
            >
              问 AI 选股
            </Button>
          </Tooltip>
        </Space>
      </div>

      {/* 推荐快捷短语 */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", fontSize: 12 }}>
        <span style={{ color: c.textMuted }}>灵感示例:</span>
        {PRESET_PROMPTS.map((p) => (
          <Tag
            key={p}
            style={{
              cursor: "pointer",
              borderRadius: 4,
              fontSize: 11,
              padding: "0 6px",
              lineHeight: "20px",
            }}
            onClick={() => {
              setPromptText(p);
              handleApplyParse(p);
            }}
          >
            {p}
          </Tag>
        ))}
      </div>
    </div>
  );
};

export default AiNaturalScreenerBar;
