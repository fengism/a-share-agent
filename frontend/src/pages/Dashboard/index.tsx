import { Typography, Row, Col, Card } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, FundOutlined, MessageOutlined, RobotOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useMarketIndices } from "../../api/queries";
import { useColors, useStyles } from "../../styles/ui";
import { formatAmount } from "../../utils/format";

const { Text } = Typography;

const shortcuts = [
  { icon: <FundOutlined style={{ fontSize: 24 }} />, title: "市场行情", desc: "热点榜单与龙虎榜", link: "/market", gradientKey: "header" as const },
  { icon: <MessageOutlined style={{ fontSize: 24 }} />, title: "对话", desc: "AI 智能选股助手", link: "/chat", gradientKey: "elevated" as const },
  { icon: <RobotOutlined style={{ fontSize: 24 }} />, title: "AI 分析", desc: "输入代码获取深度分析", link: "/analysis", gradientKey: "accent" as const },
];

const INDEX_NAMES = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500"];

function formatIndexPrice(value: number | string | null | undefined) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue.toFixed(2) : "-";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: marketData } = useMarketIndices();
  const c = useColors();
  const { cardStyle, pageContainerStyle } = useStyles();

  const mainIndices = INDEX_NAMES.map(
    (name) => (marketData?.indices || []).find((item) => item.name === name)
  ).filter((item) => item != null);

  const today = new Date();
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`;

  const shortcutGradients = {
    header: c.headerGradient,
    elevated: `linear-gradient(135deg, ${c.elevatedBg}, ${c.cardBg})`,
    accent: `linear-gradient(135deg, ${c.accent}22, ${c.cardBg})`,
  };

  return (
    <div style={pageContainerStyle}>
      <div style={{ padding: "16px 0 20px" }}>
        <Text style={{ fontSize: 18, fontWeight: 600, color: c.textPrimary }}>{dateStr} · 市场概览</Text>
      </div>
      {mainIndices.length > 0 && (
        <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
          {mainIndices.map((idx) => {
            const isUp = idx.change_pct != null && idx.change_pct > 0;
            const isDown = idx.change_pct != null && idx.change_pct < 0;
            const color = isUp ? c.up : isDown ? c.down : c.textSecondary;
            return (
              <Col xs={24} sm={12} lg={8} key={idx.code}>
                <div style={{
                  display: "flex", flexDirection: "column", gap: 4, padding: "14px 18px",
                  background: isUp ? c.upCardGradient : isDown ? c.downCardGradient : c.elevatedBg,
                  border: `1px solid ${c.border}`, borderRadius: 10, height: "100%",
                }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <Text style={{ color: c.textSecondary, fontSize: 13, fontWeight: 500 }}>{idx.name}</Text>
                    <Text style={{ color: c.textMuted, fontSize: 11 }}>额 {formatAmount(idx.amount)}</Text>
                  </div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                    <Text style={{ color, fontSize: 24, fontWeight: 700, lineHeight: 1.2 }}>{formatIndexPrice(idx.price)}</Text>
                    {idx.change_pct != null && (
                      <Text style={{ color, fontSize: 14, fontWeight: 600 }}>
                        {isUp ? <ArrowUpOutlined /> : isDown ? <ArrowDownOutlined /> : null}
                        {" "}{isUp ? "+" : ""}{idx.change_pct.toFixed(2)}%
                      </Text>
                    )}
                  </div>
                </div>
              </Col>
            );
          })}
        </Row>
      )}
      <Row gutter={[16, 16]}>
        {shortcuts.map((s) => (
          <Col xs={24} md={8} key={s.title}>
            <Card
              hoverable
              style={{
                ...cardStyle, cursor: "pointer",
                transition: "transform 0.2s ease, box-shadow 0.2s ease",
                background: shortcutGradients[s.gradientKey],
              }}
              styles={{ body: { padding: "20px 24px" } }}
              onClick={() => navigate(s.link)}
              onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px)"; e.currentTarget.style.boxShadow = "0 8px 24px rgba(0,0,0,0.4)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0)"; e.currentTarget.style.boxShadow = cardStyle.boxShadow as string; }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 10, background: `${c.primary}20`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: c.primary, boxShadow: `0 0 12px ${c.primary}33`,
                }}>{s.icon}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15, color: c.textPrimary }}>{s.title}</div>
                  <div style={{ color: c.textSecondary, fontSize: 13, marginTop: 2 }}>{s.desc}</div>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
