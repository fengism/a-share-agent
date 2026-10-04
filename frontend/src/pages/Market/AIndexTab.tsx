import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, Col, Modal, Row, Segmented, Statistic, Typography } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import { useMarketIndexKline, useMarketIndices } from "../../api/queries";
import LazyKlineChart from "../../charts/LazyKlineChart";
import ChangeValue from "../../components/ChangeValue";
import IndexIntradayCard from "../../components/IndexIntradayCard";
import SectionDataState from "../../components/SectionDataState";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens } from "../../styles/ui";
import type { ThemeColors } from "../../styles/ui";
import { MAX_KLINE_HISTORY_YEARS, yearsAgoDate } from "../../utils/date";

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
  const [klineExpanded, setKlineExpanded] = useState(false);
  const [activeSymbol, setActiveSymbol] = useUrlSearchParam("index", "000001", {
    allowedValues: INDEX_CODES,
  });
  const [period, setPeriod] = useUrlSearchParam("period", "daily", {
    allowedValues: KLINE_PERIODS,
  });
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
  } = useMarketIndexKline(activeSymbol, period, { startDate });

  // 切换指数或周期时回到默认 1 年窗口
  useEffect(() => {
    setHistoryYears(1);
  }, [activeSymbol, period]);

  const handleReachLeftEdge = useCallback(() => {
    setHistoryYears((years) => Math.min(years + 1, MAX_KLINE_HISTORY_YEARS));
  }, []);

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
          {/* antd v6 的 Row gutter 不接受响应式对象（类型为 number | [number, number]），固定间距即可 */}
          <Row gutter={[16, 16]}>
            {mainIndices.map((idx) => {
              const isActive = idx.code === activeSymbol;
              return (
                <Col xs={12} sm={8} lg={desktopSpan} key={idx.code}>
                  <button
                    type="button"
                    onClick={() => setActiveSymbol(idx.code)}
                    aria-pressed={isActive}
                    style={{
                      cursor: "pointer",
                      border: 0,
                      padding: 0,
                      width: "100%",
                      background: "transparent",
                      textAlign: "left",
                      outline: "none",
                    }}
                  >
                    <Card
                      hoverable
                      className="market-index-card"
                      style={{
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
                            color: getChangeColor(idx.change_pct, c),
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
              height={380}
            />
          )}
        </Col>
        <Col xs={24} xl={12}>
          <Card
            size="small"
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
                <Segmented
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
            styles={{ body: { padding: "12px 14px" } }}
          >
            <SectionDataState
              isLoading={klineLoading && !hasKlineData}
              error={hasKlineData ? undefined : klineError}
              onRetry={() => refetchKline()}
              isEmpty={!hasKlineData}
              emptyText="暂无指数 K 线数据"
              errorTitle="指数 K 线加载失败"
              minHeight={380}
            >
              <LazyKlineChart
                data={klineItems}
                height={380}
                viewKey={`${activeSymbol}-${period}`}
                onReachLeftEdge={historyLimitReached ? undefined : handleReachLeftEdge}
                historyLimitReached={historyLimitReached}
              />
            </SectionDataState>
          </Card>
        </Col>
      </Row>

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
        width="90vw"
        styles={{ body: { height: "75vh" } }}
      >
        <LazyKlineChart
          data={klineItems}
          height={580}
          viewKey={`${activeSymbol}-${period}-fullscreen`}
          onReachLeftEdge={historyLimitReached ? undefined : handleReachLeftEdge}
          historyLimitReached={historyLimitReached}
        />
      </Modal>
    </div>
  );
}
