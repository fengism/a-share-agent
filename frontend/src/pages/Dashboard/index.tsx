import { Typography, Row, Col, Card, Input } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, FundOutlined, FilterOutlined, RobotOutlined, SearchOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useMarketIndices, useStockSearch } from "../../api/queries";
import { cardStyle, darkColors, pageContainerStyle } from "../../styles/ui";
import { useState, useRef } from "react";
import type { InputRef } from "antd";

const { Text } = Typography;

const shortcuts = [
  { icon: <FundOutlined style={{ fontSize: 24 }} />, title: "市场行情", desc: "热点榜单与龙虎榜", link: "/market", gradient: darkColors.headerGradient },
  { icon: <FilterOutlined style={{ fontSize: 24 }} />, title: "智能选股", desc: "PE/PB/市值多维筛选", link: "/screener", gradient: "linear-gradient(135deg, #1a2332, #111827)" },
  { icon: <RobotOutlined style={{ fontSize: 24 }} />, title: "AI 分析", desc: "输入代码获取深度分析", link: "/analysis", gradient: "linear-gradient(135deg, #1e1040, #111827)" },
];

const INDEX_NAMES = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500"];

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(1)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toFixed(0);
}

function formatIndexPrice(value: number | string | null | undefined) {
  const numericValue = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numericValue) ? numericValue.toFixed(2) : "-";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: marketData } = useMarketIndices();
  const [searchQuery, setSearchQuery] = useState("");
  const { data: searchResults = [] } = useStockSearch(searchQuery);
  const searchRef = useRef<InputRef>(null);

  const mainIndices = INDEX_NAMES.map(
    (name) => (marketData?.indices || []).find((item) => item.name === name)
  ).filter((item) => item != null);

  const today = new Date();
  const dateStr = `${today.getFullYear()}年${today.getMonth() + 1}月${today.getDate()}日`;

  return (
    <div style={pageContainerStyle}>
      {/* Header row: greeting + search */}
      <Row justify="space-between" align="middle" style={{ padding: "24px 0 20px" }}>
        <Col>
          <Text style={{ fontSize: 18, fontWeight: 600, color: darkColors.textPrimary }}>{dateStr} · 市场概览</Text>
        </Col>
        <Col>
          <Input.Search
            ref={searchRef}
            placeholder="输入股票代码或名称"
            prefix={<SearchOutlined style={{ color: darkColors.textMuted }} />}
            allowClear
            enterButton
            style={{ width: 280 }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value.trim())}
            onSearch={(val) => {
              const trimmed = val.trim();
              if (trimmed.length === 6 && /^\d{6}$/.test(trimmed)) {
                navigate(`/analysis/${trimmed}`);
                setSearchQuery("");
              } else if (searchResults.length > 0) {
                navigate(`/analysis/${searchResults[0].code}`);
                setSearchQuery("");
              }
            }}
          />
        </Col>
      </Row>

      {/* Index bars */}
      {mainIndices.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
          {mainIndices.map((idx) => {
            const isUp = idx.change_pct != null && idx.change_pct > 0;
            const isDown = idx.change_pct != null && idx.change_pct < 0;
            const color = isUp ? darkColors.up : isDown ? darkColors.down : darkColors.textSecondary;
            return (
              <div
                key={idx.code}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "12px 18px",
                  background: isUp ? darkColors.upCardGradient : isDown ? darkColors.downCardGradient : darkColors.elevatedBg,
                  border: `1px solid ${darkColors.border}`,
                  borderRadius: 10,
                }}
              >
                <Text style={{ color: darkColors.textSecondary, fontSize: 14, width: 80 }}>{idx.name}</Text>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, flex: 1 }}>
                  <Text style={{ color, fontSize: 24, fontWeight: 700 }}>{formatIndexPrice(idx.price)}</Text>
                  {idx.change_pct != null && (
                    <Text style={{ color, fontSize: 14, fontWeight: 600 }}>
                      {isUp ? <ArrowUpOutlined /> : isDown ? <ArrowDownOutlined /> : null}
                      {" "}{isUp ? "+" : ""}{idx.change_pct.toFixed(2)}%
                    </Text>
                  )}
                </div>
                <Text style={{ color: darkColors.textMuted, fontSize: 12 }}>额 {formatAmount(idx.amount)}</Text>
              </div>
            );
          })}
        </div>
      )}

      {/* Shortcuts */}
      <Row gutter={[16, 16]}>
        {shortcuts.map((s) => (
          <Col xs={24} md={8} key={s.title}>
            <Card
              hoverable
              style={{
                ...cardStyle,
                cursor: "pointer",
                transition: "transform 0.2s ease, box-shadow 0.2s ease",
                background: s.gradient,
              }}
              styles={{ body: { padding: "20px 24px" } }}
              onClick={() => navigate(s.link)}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 24px rgba(0,0,0,0.4)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = cardStyle.boxShadow as string;
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: 10,
                  background: "rgba(59,130,246,0.15)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: darkColors.primary,
                  boxShadow: "0 0 12px rgba(59,130,246,0.2)",
                }}>{s.icon}</div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 15, color: darkColors.textPrimary }}>{s.title}</div>
                  <div style={{ color: darkColors.textSecondary, fontSize: 13, marginTop: 2 }}>{s.desc}</div>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
