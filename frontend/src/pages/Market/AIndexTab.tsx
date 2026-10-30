import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Col, Modal, Row, Segmented, Statistic, Typography } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import { useMarketIndexKline, useMarketIndices } from "../../api/queries";
import LazyKlineChart from "../../charts/LazyKlineChart";
import ChangeValue from "../../components/ChangeValue";
import IndexIntradayCard from "../../components/IndexIntradayCard";
import SectionDataState from "../../components/SectionDataState";
import { useFullscreenChartHeight } from "../../hooks/useFullscreenChartHeight";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens } from "../../styles/ui";
import { MAX_KLINE_HISTORY_YEARS, yearsAgoDate } from "../../utils/date";
import { changeColor, formatAmount } from "../../utils/format";
import { KEY_MARKET_INDEX_CODES } from "../../utils/keyMarketIndices";
import MarketVolumeCard from "./MarketVolumeCard";

const { Text } = Typography;
const DEFAULT_INDEX_CODE = "000001";
const KLINE_PERIODS = ["daily", "weekly", "monthly", "annual"] as const;

export default function AIndexTab() {
  const c = useColors();
  const t = useTokens();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const chartHeight = isMobile ? 280 : 380;
  const [klineExpanded, setKlineExpanded] = useState(false);
  const fullscreenHeight = useFullscreenChartHeight();
  const [activeSymbol, setActiveSymbol] = useUrlSearchParam("index", DEFAULT_INDEX_CODE, {
    allowedValues: KEY_MARKET_INDEX_CODES,
  });
  const [period, setPeriod] = useUrlSearchParam("period", "daily", {
    allowedValues: KLINE_PERIODS,
  });
  const periodControl = (
    <Segmented
      size="small"
      aria-label="K线周期"
      options={[
        { label: "日K", value: "daily" },
        { label: "周K", value: "weekly" },
        { label: "月K", value: "monthly" },
        { label: "年K", value: "annual" },
      ]}
      value={period}
      onChange={(value) => setPeriod(String(value))}
    />
  );
  // 默认展示近 1 年，向左滑动触底时每次再向前扩充 1 年，最多到 10 年
  const [historyYears, setHistoryYears] = useState(1);
  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  const historyLimitReached = historyYears >= MAX_KLINE_HISTORY_YEARS;
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
  } = useMarketIndexKline(activeSymbol, period, { startDate, liveRefresh: period === "daily" });

  // 切换指数或周期时回到默认 1 年窗口
  useEffect(() => {
    setHistoryYears(1);
  }, [activeSymbol, period]);

  const handleReachLeftEdge = useCallback(() => {
    setHistoryYears((years) => Math.min(years + 1, MAX_KLINE_HISTORY_YEARS));
  }, []);

  const mainIndices = useMemo(
    () => KEY_MARKET_INDEX_CODES.map((code) => (marketData?.indices || []).find((item) => item.code === code)).filter((item) => item != null),
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
          {/* antd v6 的 Row gutter 不接受响应式对象（类型为 number | [number, number]），固定间距即可 */}
          <Row gutter={[16, 16]}>
            {mainIndices.map((idx) => {
              const isActive = idx.code === activeSymbol;
              return (
                <Col xs={12} sm={12} md={desktopSpan} lg={desktopSpan} key={idx.code}>
                  <button
                    type="button"
                    onClick={() => setActiveSymbol(idx.code)}
                    aria-pressed={isActive}
                    style={{
                      cursor: "pointer",
                      border: 0,
                      padding: 0,
                      width: "100%",
                      height: "100%",
                      background: "transparent",
                      textAlign: "left",
                      outline: "none",
                    }}
                  >
                    <Card
                      hoverable
                      className="market-index-card"
                      style={{
                        height: "100%",
                        borderRadius: t.radius.md,
                        border: `1px solid ${isActive ? c.primary : c.border}`,
                        borderTop: isActive ? `3px solid ${c.primary}` : `1px solid ${c.border}`,
                        background: isActive
                          ? "color-mix(in srgb, var(--c-primary) 5%, var(--c-card-bg))"
                          : "var(--c-card-bg)",
                        boxShadow: isActive ? "0 4px 14px rgba(22, 119, 255, 0.12)" : t.shadow.xs,
                        transition: "all 0.2s ease",
                        overflow: "hidden",
                      }}
                    >
                      <Statistic
                        title={
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", minWidth: 0, gap: 4 }}>
                            <span style={{
                              color: isActive ? c.primary : c.textSecondary,
                              fontSize: t.font.md,
                              fontWeight: isActive ? 600 : 500,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}>
                              {idx.name}
                            </span>
                            {isActive && (
                              <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: c.primary, flexShrink: 0 }} />
                            )}
                          </div>
                        }
                        value={idx.price ?? undefined}
                        precision={2}
                        styles={{
                          content: {
                            color: changeColor(idx.change_pct, c),
                            fontSize: "clamp(16px, 4.2vw, 26px)",
                            lineHeight: 1.2,
                            fontWeight: Number(t.weight.bold),
                            fontFamily: "var(--c-font-mono)",
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            maxWidth: "100%",
                            display: "block",
                          },
                        }}
                      />
                      <div style={{ marginTop: t.space[2], display: "flex", justifyContent: "space-between", alignItems: "center", minWidth: 0, gap: 4, flexWrap: "wrap" }}>
                        <ChangeValue value={idx.change_pct} showIcon />
                        <Text type="secondary" style={{ fontSize: t.font.xs, fontFamily: "var(--c-font-mono)", flexShrink: 0 }}>{idx.code}</Text>
                      </div>
                      <div style={{ marginTop: t.space[2], display: "flex", alignItems: "center", justifyContent: "space-between", minWidth: 0, overflow: "hidden" }}>
                        <Text type="secondary" ellipsis style={{ fontSize: t.font.xs, maxWidth: "100%" }}>成交额 {formatAmount(idx.amount)}</Text>
                      </div>
                    </Card>
                  </button>
                </Col>
              );
            })}
          </Row>
        </SectionDataState>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          {activeIndex && (
            <IndexIntradayCard
              symbol={activeIndex.code}
              name={activeIndex.name}
              price={activeIndex.price}
              changePct={activeIndex.change_pct}
              preClose={activeIndex.pre_close}
              height={chartHeight}
            />
          )}
        </Col>
        <Col xs={24} xl={12}>
          <Card
            size="small"
            className="market-kline-card"
            title={
              <span style={{ fontWeight: Number(t.weight.semibold) }}>
                {activeIndex?.name || "大盘指数"} · K线趋势
              </span>
            }
            extra={
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span
                  className="stock-chart-hint"
                  data-testid="index-kline-history-range"
                  style={{ fontSize: t.font.xs, color: c.textSecondary }}
                >
                  {historyLimitReached
                    ? `已加载近 ${MAX_KLINE_HISTORY_YEARS} 年（上限）`
                    : `近 ${historyYears} 年 · 向左滑动加载更早数据（最多 ${MAX_KLINE_HISTORY_YEARS} 年）`}
                </span>
                {periodControl}
                <Button
                  type="text"
                  size="small"
                  icon={<FullscreenOutlined />}
                  aria-label="放大K线图"
                  onClick={() => setKlineExpanded(true)}
                  style={{ color: c.textSecondary }}
                />
              </div>
            }
            style={{ borderRadius: t.radius.md, border: `1px solid ${c.border}`, boxShadow: t.shadow.xs, height: "100%" }}
            styles={{ body: { padding: "var(--c-pad-card, 16px 18px)" } }}
          >
            <SectionDataState
              isLoading={klineLoading && !hasKlineData}
              error={hasKlineData ? undefined : klineError}
              onRetry={() => refetchKline()}
              isEmpty={!hasKlineData}
              emptyText="暂无指数 K 线数据"
              errorTitle="指数 K 线加载失败"
              minHeight={chartHeight}
            >
              <LazyKlineChart
                data={klineItems}
                height={chartHeight}
                viewKey={`${activeSymbol}-${period}`}
                onReachLeftEdge={historyLimitReached ? undefined : handleReachLeftEdge}
                historyLimitReached={historyLimitReached}
                landscapeToolbar={periodControl}
              />
            </SectionDataState>
          </Card>
        </Col>
      </Row>

      <div style={{ marginTop: t.space[4] }}>
        <MarketVolumeCard />
      </div>

      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between", paddingRight: 32, flexWrap: "wrap", minWidth: 0 }}>
            <span>{`${activeIndex?.name || "大盘指数"} · ${period === "daily" ? "日K" : period === "weekly" ? "周K" : period === "monthly" ? "月K" : "年K"}线全屏`}</span>
            <span style={{ fontSize: t.font.xs, color: c.textSecondary, fontWeight: "normal" }}>
              {historyLimitReached
                ? `已加载近 ${MAX_KLINE_HISTORY_YEARS} 年（上限）`
                : `近 ${historyYears} 年 · 向左滑动加载更早数据（最多 ${MAX_KLINE_HISTORY_YEARS} 年）`}
            </span>
          </div>
        }
        open={klineExpanded}
        onCancel={() => setKlineExpanded(false)}
        footer={null}
        width="min(1200px, calc(100vw - 20px))"
        centered
        styles={{ body: { height: fullscreenHeight } }}
      >
        <LazyKlineChart
          data={klineItems}
          height={fullscreenHeight}
          viewKey={`${activeSymbol}-${period}-fullscreen`}
          onReachLeftEdge={historyLimitReached ? undefined : handleReachLeftEdge}
          historyLimitReached={historyLimitReached}
          landscapeToolbar={periodControl}
        />
      </Modal>
    </div>
  );
}
