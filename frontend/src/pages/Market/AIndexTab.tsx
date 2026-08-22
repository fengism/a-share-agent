import { useEffect, useMemo } from "react";
import { Card, Col, Row, Segmented, Statistic, Typography } from "antd";
import { useMarketIndexKline, useMarketIndices } from "../../api/queries";
import LazyKlineChart from "../../charts/LazyKlineChart";
import ChangeValue from "../../components/ChangeValue";
import IndexIntradayCard from "../../components/IndexIntradayCard";
import SectionDataState from "../../components/SectionDataState";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens } from "../../styles/ui";
import type { ThemeColors } from "../../styles/ui";

const { Text } = Typography;
const INDEX_CODES = ["000001", "399001", "399006", "000688", "000300", "000905"] as const;
const KLINE_PERIODS = ["daily", "weekly", "monthly"] as const;

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
  const t = useTokens();
  const [activeSymbol, setActiveSymbol] = useUrlSearchParam("index", "000001", {
    allowedValues: INDEX_CODES,
  });
  const [period, setPeriod] = useUrlSearchParam("period", "daily", {
    allowedValues: KLINE_PERIODS,
  });
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
  const desktopSpan = mainIndices.length > 0 ? Math.max(4, Math.floor(24 / mainIndices.length)) : 4;
  const klineItems = klineData?.items ?? [];
  const hasKlineData = klineItems.length > 0;
  const activeIndex = mainIndices.find((item) => item.code === activeSymbol) || mainIndices[0];

  useEffect(() => {
    if (indicesLoading || mainIndices.length === 0) return;
    if (!mainIndices.some((item) => item.code === activeSymbol)) {
      setActiveSymbol(mainIndices[0].code);
    }
  }, [activeSymbol, indicesLoading, mainIndices, setActiveSymbol]);

  return (
    <div>
      <div style={{ marginBottom: t.space[4] }}>
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
              <Col xs={12} sm={8} lg={desktopSpan} key={idx.code}>
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
                      borderRadius: t.radius.md,
                      border: `1px solid ${idx.code === activeSymbol ? c.primary : c.border}`,
                      boxShadow: t.shadow.xs,
                    }}
                    styles={{ body: { padding: t.space[4] } }}
                  >
                    <Statistic
                      title={<span style={{ color: c.textSecondary, fontSize: t.font.md }}>{idx.name}</span>}
                      value={idx.price ?? undefined}
                      precision={2}
                      styles={{
                        content: {
                          color: getChangeColor(idx.change_pct, c),
                          fontSize: t.font["3xl"],
                          fontWeight: Number(t.weight.bold),
                        },
                      }}
                    />
                    <div style={{ marginTop: t.space[2], display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <ChangeValue value={idx.change_pct} showIcon />
                      <Text type="secondary" style={{ fontSize: t.font.sm }}>{idx.code}</Text>
                    </div>
                    <div style={{ marginTop: t.space[2], display: "flex", alignItems: "center" }}>
                      <Text type="secondary" style={{ fontSize: t.font.sm }}>成交额 {formatAmount(idx.amount)}</Text>
                    </div>
                  </Card>
                </button>
              </Col>
            ))}
          </Row>
        </SectionDataState>
      </div>

      {activeIndex && (
        <div style={{ marginBottom: t.space[4] }}>
          <IndexIntradayCard
            symbol={activeIndex.code}
            name={activeIndex.name}
            price={activeIndex.price}
            changePct={activeIndex.change_pct}
            preClose={activeIndex.pre_close}
            height={360}
          />
        </div>
      )}

      <Card
        size="small"
        title={<span style={{ fontWeight: Number(t.weight.semibold) }}>{activeIndex?.name || "大盘指数"} K线</span>}
        extra={
          <Segmented
            aria-label="K线周期"
            options={[
              { label: "日K", value: "daily" },
              { label: "周K", value: "weekly" },
              { label: "月K", value: "monthly" },
            ]}
            value={period}
            onChange={(value) => setPeriod(String(value))}
          />
        }
        style={{ borderRadius: t.radius.md, border: `1px solid ${c.border}`, boxShadow: t.shadow.xs }}
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
          <LazyKlineChart
            data={klineItems}
            height={420}
            viewKey={`${activeSymbol}:${period}`}
          />
        </SectionDataState>
      </Card>
    </div>
  );
}
