import { useMemo, useState } from "react";
import { Card, Col, Row, Segmented, Statistic, Typography } from "antd";
import { useMarketIndexKline, useMarketIndices } from "../../api/queries";
import KlineChart from "../../charts/KlineChart";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
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
  const {
    data: marketData,
    isLoading: indicesLoading,
    error: indicesError,
    refetch: refetchIndices,
  } = useMarketIndices();
  const {
    data: klineData,
    isLoading: klineLoading,
    error: klineError,
    refetch: refetchKline,
  } = useMarketIndexKline(activeSymbol, period);

  const mainIndices = useMemo(
    () => INDEX_CODES.map((code) => (marketData?.indices || []).find((item) => item.code === code)).filter((item) => item != null),
    [marketData],
  );
  const klineItems = klineData?.items ?? [];
  const hasKlineData = klineItems.length > 0;
  const activeIndex = mainIndices.find((item) => item.code === activeSymbol) || mainIndices[0];

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <SectionDataState
          isLoading={indicesLoading && mainIndices.length === 0}
          error={mainIndices.length > 0 ? undefined : indicesError}
          onRetry={() => refetchIndices()}
          isEmpty={mainIndices.length === 0}
          emptyText="暂无大盘指数数据"
          errorTitle="大盘指数加载失败"
          minHeight={180}
        >
          <Row gutter={[16, 16]}>
            {mainIndices.map((idx) => (
              <Col xs={24} sm={12} lg={4} key={idx.code}>
                <button
                  type="button"
                  onClick={() => setActiveSymbol(idx.code)}
                  aria-pressed={idx.code === activeSymbol}
                  style={{
                    cursor: "pointer",
                    border: 0,
                    padding: 0,
                    width: "100%",
                    background: "transparent",
                    textAlign: "left",
                  }}
                >
                  <Card
                    hoverable
                    style={{
                      borderRadius: 8,
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
                    />
                    <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <ChangeValue value={idx.change_pct} showIcon />
                      <Text type="secondary" style={{ fontSize: 12 }}>{idx.code}</Text>
                    </div>
                    <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>额 {formatAmount(idx.amount)}</Text>
                    </div>
                  </Card>
                </button>
              </Col>
            ))}
          </Row>
        </SectionDataState>
      </div>

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
        <SectionDataState
          isLoading={klineLoading && !hasKlineData}
          error={hasKlineData ? undefined : klineError}
          onRetry={() => refetchKline()}
          isEmpty={!hasKlineData}
          emptyText="暂无指数 K 线数据"
          errorTitle="指数 K 线加载失败"
          minHeight={420}
          skeletonRows={8}
        >
          <KlineChart
            data={klineItems}
            height={420}
            viewKey={`${activeSymbol}:${period}`}
          />
        </SectionDataState>
      </Card>
    </div>
  );
}
