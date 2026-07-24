import { useMemo, useState } from "react";
import { Card, Col, Empty, Row, Segmented, Spin, Statistic, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { useMarketIndexKline, useMarketIndices } from "../../api/queries";
import KlineChart from "../../charts/KlineChart";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../styles/ui";

const { Text } = Typography;
const INDEX_CODES = ["000001", "399001", "399006", "000688", "000300", "000905"];

function getChangeColor(changePct: number | null, c: ThemeColors) {
  if (changePct == null) return c.textSecondary;
  if (changePct > 0) return c.up;
  if (changePct < 0) return c.down;
  return c.textSecondary;
}

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(1)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toFixed(0);
}

export default function AIndexTab() {
  const c = useColors();
  const [activeSymbol, setActiveSymbol] = useState("000001");
  const [period, setPeriod] = useState("daily");
  const { data: marketData, isLoading: indicesLoading } = useMarketIndices();
  const { data: klineData, isLoading: klineLoading } = useMarketIndexKline(activeSymbol, period);

  const mainIndices = useMemo(
    () => INDEX_CODES.map((code) => (marketData?.indices || []).find((item) => item.code === code)).filter((item) => item != null),
    [marketData],
  );
  const activeIndex = mainIndices.find((item) => item.code === activeSymbol) || mainIndices[0];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {indicesLoading ? (
          <Col span={24}><Card><Spin /></Card></Col>
        ) : mainIndices.length > 0 ? (
          mainIndices.map((idx) => (
            <Col xs={24} sm={12} lg={4} key={idx.code}>
              <Card
                hoverable
                onClick={() => setActiveSymbol(idx.code)}
                style={{
                  borderRadius: 8,
                  cursor: "pointer",
                  border: `1px solid ${idx.code === activeSymbol ? c.primary : c.border}`,
                  boxShadow: "none",
                }}
                styles={{ body: { padding: 16 } }}
              >
                <Statistic
                  title={<span style={{ color: c.textSecondary, fontSize: 13 }}>{idx.name}</span>}
                  value={idx.price ?? undefined}
                  precision={2}
                  valueStyle={{ color: getChangeColor(idx.change_pct, c), fontSize: 24, fontWeight: 700 }}
                  prefix={idx.change_pct != null ? (idx.change_pct > 0 ? <ArrowUpOutlined /> : idx.change_pct < 0 ? <ArrowDownOutlined /> : null) : null}
                />
                <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <Text style={{ color: getChangeColor(idx.change_pct, c), fontWeight: 600 }}>
                    {idx.change_pct != null ? `${idx.change_pct > 0 ? "+" : ""}${idx.change_pct.toFixed(2)}%` : "-"}
                  </Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{idx.code}</Text>
                </div>
                <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>额 {formatAmount(idx.amount)}</Text>
                </div>
              </Card>
            </Col>
          ))
        ) : (
          <Col span={24}><Empty description="暂无大盘指数数据" /></Col>
        )}
      </Row>

      <Card
        size="small"
        title={<span style={{ fontWeight: 600 }}>{activeIndex?.name || "大盘指数"} K线</span>}
        extra={
          <Segmented
            options={[
              { label: "日K", value: "daily" },
              { label: "周K", value: "weekly" },
              { label: "月K", value: "monthly" },
            ]}
            value={period}
            onChange={(value) => setPeriod(String(value))}
          />
        }
        style={{ borderRadius: 8, border: `1px solid ${c.border}`, boxShadow: "none" }}
      >
        {klineLoading ? (
          <Spin />
        ) : klineData?.items?.length ? (
          <KlineChart data={klineData.items} height={420} />
        ) : (
          <Empty description="暂无指数K线数据" />
        )}
      </Card>
    </div>
  );
}
