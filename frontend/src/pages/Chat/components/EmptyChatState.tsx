import { useMemo, useState } from "react";
import {
  ApartmentOutlined,
  ClockCircleOutlined,
  CompassOutlined,
  FileSearchOutlined,
  FilterOutlined,
  FireOutlined,
  FundOutlined,
  LineChartOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Segmented, Tag, Typography } from "antd";
import { semanticTagStyle, useColors, useTokens } from "../../../styles/ui";
import { SAMPLE_PROMPTS } from "../constants";

const { Text, Title } = Typography;

interface EmptyChatStateProps {
  onSelectPrompt: (prompt: string) => void;
}

interface PromptCardItem {
  icon: React.ReactNode;
  category: "market" | "screener" | "analysis" | "macro";
  tag: string;
  tagColor?: "primary" | "warning" | "up" | "down";
  title: string;
  prompt: string;
  description: string;
}

function getTradingSessionInfo() {
  const now = new Date();
  // 转换或直接获取当前时间的小时/分钟
  const hours = now.getHours();
  const minutes = now.getMinutes();
  const totalMins = hours * 60 + minutes;

  if (totalMins >= 8 * 60 + 30 && totalMins < 9 * 60 + 25) {
    return {
      label: "盘前研判",
      color: "primary" as const,
      desc: "聚焦隔夜美股/大宗商品异动、早盘宏观资讯与竞价预期",
      defaultPrompt: "梳理今日早间核心财经资讯，并分析对A股开盘的主要影响板块",
    };
  }
  if (totalMins >= 9 * 60 + 25 && totalMins <= 15 * 60) {
    return {
      label: "盘中实时",
      color: "up" as const,
      desc: "捕捉盘中突发放量、主力资金动向、涨停梯队与炸板率",
      defaultPrompt: "分析当前盘面资金流向，涨停连板龙头有哪些？",
    };
  }
  if (totalMins > 15 * 60 && totalMins < 19 * 60) {
    return {
      label: "盘后全景复盘",
      color: "warning" as const,
      desc: "复盘今日板块涨跌逻辑、龙虎榜机构席位买入与明日推演",
      defaultPrompt: "总结今日A股收盘复盘，分析领涨题材持续性与龙虎榜机构动向",
    };
  }
  return {
    label: "深度策略与选股",
    color: "primary" as const,
    desc: "多因子量化选股、企业财务三张表排雷、产业链图谱穿透",
    defaultPrompt: "帮我找PE小于20且股息率大于3%的优质白马股",
  };
}

const PROMPT_ITEMS: PromptCardItem[] = [
  {
    icon: <FireOutlined />,
    category: "market",
    tag: "盘面风向",
    tagColor: "up",
    title: "主力资金与主线题材",
    prompt: "今日大盘主线题材与涨停连板龙头有哪些？分析主力资金净流入前三行业",
    description: "实时洞察题材轮动、量能配合与资金攻击方向",
  },
  {
    icon: <FilterOutlined />,
    category: "screener",
    tag: "量化选股",
    tagColor: "primary",
    title: "低估值高股息白马",
    prompt: "帮我找PE小于20、PB小于2且股息率大于3%的优质核心资产，列出前5只",
    description: "多维基本面与估值指标智能筛选，构建防御型组合",
  },
  {
    icon: <LineChartOutlined />,
    category: "analysis",
    tag: "深度个股",
    tagColor: "warning",
    title: "龙头基本面与估值诊断",
    prompt: "深度分析贵州茅台(600519)近期财务状况、机构一致预期与估值分位数",
    description: "三张表健康度、盈利质量与行业竞争格局全面拆解",
  },
  {
    icon: <ApartmentOutlined />,
    category: "macro",
    tag: "产业链穿透",
    title: "先进封装与芯片产业链",
    prompt: "帮我梳理半导体先进封装芯片产业链核心龙头标的及近期最新研报看点",
    description: "按上中下游梳理技术壁垒、核心受益标的与预期差",
  },
  {
    icon: <CompassOutlined />,
    category: "market",
    tag: "情绪周期",
    tagColor: "up",
    title: "连板天梯与短线情绪",
    prompt: "分析当前市场短线情绪周期（高标连板、炸板率、晋级率与连板梯队）",
    description: "短线游资打板策略与情绪冰点/高潮拐点识别",
  },
  {
    icon: <FileSearchOutlined />,
    category: "analysis",
    tag: "财务排雷",
    tagColor: "warning",
    title: "商誉与资产负债体检",
    prompt: "如何判断一家公司的应收账款和商誉是否存在大幅减值风险？举例分析",
    description: "穿透财务真实性，快速识别潜在暴雷与现金流隐患",
  },
];

export function EmptyChatState({ onSelectPrompt }: EmptyChatStateProps) {
  const c = useColors();
  const t = useTokens();
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const sessionInfo = useMemo(() => getTradingSessionInfo(), []);

  const filteredItems = useMemo(() => {
    if (selectedCategory === "all") return PROMPT_ITEMS;
    return PROMPT_ITEMS.filter((item) => item.category === selectedCategory);
  }, [selectedCategory]);

  return (
    <div
      style={{
        textAlign: "center",
        color: c.textMuted,
        padding: `${t.space[5]} ${t.space[3]}`,
        maxWidth: 820,
        margin: "0 auto",
      }}
    >
      <div
        style={{
          width: 58,
          height: 58,
          borderRadius: t.radius.xl,
          background: `linear-gradient(135deg, ${c.primary}22, ${c.accent}33)`,
          border: `1px solid ${c.primary}44`,
          display: "grid",
          placeItems: "center",
          margin: "0 auto var(--c-space-3)",
          color: c.primary,
          fontSize: 28,
          boxShadow: `0 8px 24px ${c.primary}22`,
        }}
      >
        <RobotOutlined />
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 6 }}>
        <Title level={4} style={{ color: c.textPrimary, margin: 0 }}>
          AI 智能投研与选股工作台
        </Title>
        <Tag style={semanticTagStyle(sessionInfo.color)}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          {sessionInfo.label}
        </Tag>
      </div>

      <Text type="secondary" style={{ display: "block", marginBottom: t.space[4], fontSize: t.font.sm }}>
        {sessionInfo.desc}。支持自然语言选股、财务三张表体检、技术形态诊断与多标的对比。
      </Text>

      {/* 交易时段推荐发问 */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onSelectPrompt(sessionInfo.defaultPrompt)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectPrompt(sessionInfo.defaultPrompt);
          }
        }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 16px",
          background: `color-mix(in srgb, ${c.primary} 10%, transparent)`,
          border: `1px dashed ${c.primary}66`,
          borderRadius: t.radius.pill,
          cursor: "pointer",
          marginBottom: t.space[4],
          transition: "all 0.2s ease",
        }}
        className="u-card-interactive"
      >
        <ThunderboltOutlined style={{ color: c.primary }} />
        <span style={{ fontSize: t.font.xs, color: c.textPrimary }}>当前时段推荐：</span>
        <span style={{ fontSize: t.font.xs, color: c.primary, fontWeight: 500 }}>
          {sessionInfo.defaultPrompt}
        </span>
      </div>

      {/* 场景分类切换 */}
      <div style={{ display: "flex", justifyContent: "center", marginBottom: t.space[4] }}>
        <Segmented
          value={selectedCategory}
          onChange={(val) => setSelectedCategory(String(val))}
          options={[
            { label: "全部灵感", value: "all" },
            { label: "盘面主线", value: "market", icon: <FundOutlined /> },
            { label: "策略选股", value: "screener", icon: <FilterOutlined /> },
            { label: "个股体检", value: "analysis", icon: <LineChartOutlined /> },
            { label: "产业链", value: "macro", icon: <ApartmentOutlined /> },
          ]}
        />
      </div>

      {/* 灵感卡片网格 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: t.space[3],
          textAlign: "left",
          marginBottom: t.space[5],
        }}
      >
        {filteredItems.map((item) => (
          <div
            key={item.title}
            role="button"
            tabIndex={0}
            onClick={() => onSelectPrompt(item.prompt)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectPrompt(item.prompt);
              }
            }}
            className="u-card-interactive"
            style={{
              padding: `${t.space[3]} ${t.space[4]}`,
              borderRadius: t.radius.lg,
              border: `1px solid ${c.border}`,
              background: c.hoverBg,
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              gap: 8,
              transition: "border-color 0.2s ease, transform 0.2s ease",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ color: c.primary, fontSize: 16 }}>{item.icon}</span>
                  <strong style={{ color: c.textPrimary, fontSize: t.font.sm }}>{item.title}</strong>
                </div>
                <Tag style={{ ...semanticTagStyle(item.tagColor ?? "primary"), fontSize: 11, margin: 0 }}>
                  {item.tag}
                </Tag>
              </div>
              <div
                style={{
                  color: c.textSecondary,
                  fontSize: t.font.xs,
                  lineHeight: 1.5,
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {item.prompt}
              </div>
            </div>
            <div style={{ fontSize: 11, color: c.textMuted }}>
              {item.description}
            </div>
          </div>
        ))}
      </div>

      {/* 底部常用提示词 */}
      <div
        style={{
          display: "flex",
          gap: t.space[2],
          justifyContent: "center",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: t.font.xs, color: c.textMuted }}>快捷提示：</span>
        {SAMPLE_PROMPTS.map((prompt) => (
          <Button
            key={prompt}
            type="text"
            size="small"
            style={{
              background: c.hoverBg,
              border: `1px solid ${c.border}`,
              color: c.textSecondary,
              borderRadius: t.radius.pill,
              fontSize: t.font.xs,
            }}
            onClick={() => onSelectPrompt(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}
