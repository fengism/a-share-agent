import { CompassOutlined } from "@ant-design/icons";
import { Card } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

export default function HKTradingRulesCard() {
  const colors = useColors();
  const { cardStyle } = useStyles();

  return (
    <Card
      className="stock-section-card stock-business-intro-card"
      title={<StockSectionTitle icon={<CompassOutlined />} title="港股交易规则" description="香港证券市场交易机制速览" />}
      style={cardStyle}
    >
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.primary}` }}>
          <div style={{ fontSize: 12, color: colors.textSecondary }}>交易机制</div>
          <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>T+0 回转交易 · 无单日涨跌幅限制</div>
        </div>
        <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.accent}` }}>
          <div style={{ fontSize: 12, color: colors.textSecondary }}>交易时间段</div>
          <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>早盘 09:30-12:00 · 午盘 13:00-16:00</div>
        </div>
        <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.info}` }}>
          <div style={{ fontSize: 12, color: colors.textSecondary }}>结算与交收</div>
          <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>T+2 证券及资金结算 · 港币 (HKD) 报价</div>
        </div>
      </div>
    </Card>
  );
}
