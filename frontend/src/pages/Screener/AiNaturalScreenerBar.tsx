import React, { useState } from "react";
import { Input, Button, Space, Tag, message, Tooltip } from "antd";
import { ThunderboltOutlined, RobotOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ScreenerFilter } from "../../types/stock";
import * as uiStyles from "../../styles/ui";
import { parseNaturalLanguageToFilters } from "./naturalScreenerParser";

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
