import { memo, useMemo, useState } from "react";
import { Button, Card, Modal, Segmented, Switch, Tooltip } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import { useKlineData, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../theme/hooks";
import { analyzeChanlun, MMD_LABELS } from "../../utils/chanlun";
import type { AnalysisPageData } from "../../types/stock";

export default memo(function AnalysisChartsSection({
  code,
  pageData,
  isExportingPdf = false,
}: {
  code?: string;
  pageData?: AnalysisPageData;
  isExportingPdf?: boolean;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [activeTab, setActiveTab] = useState<"kline" | "intraday">("kline");
  const [period, setPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const [chanlunEnabled, setChanlunEnabled] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);
  const intradayQuery = useStockIntraday(code || "", pageData?.intraday);
  const intradayData = Array.isArray(intradayQuery.data?.items)
    ? intradayQuery.data
    : pageData?.intraday;
  const isDefaultKline = period === "daily" && adjust === "qfq";
  const remoteKline = useKlineData(code || "", period, adjust, Boolean(code) && !isDefaultKline);
  const klineData = isDefaultKline ? pageData?.kline : remoteKline.data;
  const klineItems = useMemo(() => klineData?.items ?? [], [klineData]);
  const chanlunResult = useMemo(
    () => (chanlunEnabled && klineItems.length >= 10 ? analyzeChanlun(klineItems) : null),
    [chanlunEnabled, klineItems],
  );
  const lastBi = chanlunResult?.bis[chanlunResult.bis.length - 1];
  const lastZs = chanlunResult?.zss[chanlunResult.zss.length - 1];
  const lastMmds = useMemo(
    () => (chanlunResult ? chanlunResult.mmds.slice(-3).reverse() : []),
    [chanlunResult],
  );

  return (
    <section className="analysis-charts-section" aria-label="个股行情图表">
      <Card
        data-pdf-capture
        data-pdf-group
        size="small"
        className="analysis-chart-card analysis-terminal-card pdf-avoid-break"
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ fontWeight: "var(--c-weight-bold)", color: colors.textPrimary }}>行情分析</span>
            <Segmented
              options={[
                { label: "K线走势", value: "kline" },
                ...(intradayData?.items.length ? [{ label: "当日分时", value: "intraday" }] : []),
              ]}
              value={activeTab}
              onChange={(value) => setActiveTab(value as "kline" | "intraday")}
              size="small"
            />
          </div>
        }
        extra={
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {activeTab === "kline" ? (
              <span className="analysis-chart-caption">
                {period === "daily" ? "日K" : period === "weekly" ? "周K" : "月K"} · {adjust === "qfq" ? "前复权" : adjust === "hfq" ? "后复权" : "不复权"}
              </span>
            ) : (
              <span className="analysis-chart-caption">当日分时走势与成交量</span>
            )}
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              aria-label="放大查看行情图表"
              onClick={() => setIsExpanded(true)}
              style={{ color: colors.textSecondary }}
            />
          </div>
        }
        style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
        styles={{ body: { padding: "12px 14px" } }}
      >
        {/* K-line view */}
        <div style={{ display: isExportingPdf || activeTab === "kline" ? "block" : "none" }}>
          <div className="analysis-chart-toolbar" aria-label="K 线图显示设置">
            <DataRefreshIndicator active={!isDefaultKline && remoteKline.isFetching} />
            <Segmented
              options={[
                { label: "日K", value: "daily" },
                { label: "周K", value: "weekly" },
                { label: "月K", value: "monthly" },
              ]}
              value={period}
              onChange={(value) => setPeriod(String(value))}
              size="small"
            />
            <Segmented
              options={[
                { label: "前复权", value: "qfq" },
                { label: "后复权", value: "hfq" },
                { label: "不复权", value: "" },
              ]}
              value={adjust}
              onChange={(value) => setAdjust(String(value))}
              size="small"
            />
            <Tooltip title="缠论：笔（青色折线）、中枢上下沿（蓝色虚线）、三类买卖点（①②③箭头）">
              <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--c-font-sm)", color: colors.textSecondary, cursor: "pointer" }}>
                缠论
                <Switch size="small" checked={chanlunEnabled} onChange={setChanlunEnabled} />
              </label>
            </Tooltip>
          </div>
          {chanlunResult && (
            <div
              aria-label="缠论摘要"
              style={{
                display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center",
                padding: "6px 10px", marginBottom: 8, fontSize: "var(--c-font-xs)",
                background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 8,
              }}
            >
              <span style={{ color: colors.textSecondary }}>
                笔：
                <strong style={{ color: lastBi?.direction === "up" ? colors.up : colors.down }}>
                  {lastBi ? `${lastBi.direction === "up" ? "向上" : "向下"} ${lastBi.low.toFixed(2)}–${lastBi.high.toFixed(2)}` : "-"}
                </strong>
              </span>
              <span style={{ color: colors.textSecondary }}>
                最近中枢：
                <strong style={{ color: colors.info }}>
                  {lastZs ? `${lastZs.zd.toFixed(2)}–${lastZs.zg.toFixed(2)}（${lastZs.lineCount} 笔${lastZs.done ? "" : "，未完成"}）` : "暂无"}
                </strong>
              </span>
              <span style={{ color: colors.textSecondary }}>
                最近信号：
                {lastMmds.length > 0 ? lastMmds.map((mmd) => (
                  <Tooltip key={`${mmd.date}-${mmd.mmdType}`} title={`${mmd.date} ${mmd.msg}`}>
                    <span
                      style={{
                        marginLeft: 6, fontWeight: "var(--c-weight-semibold)",
                        color: mmd.mmdType.endsWith("buy") ? colors.up : colors.down,
                      }}
                    >
                      {MMD_LABELS[mmd.mmdType]}·{mmd.date.slice(5)}
                    </span>
                  </Tooltip>
                )) : <strong style={{ color: colors.textMuted }}>暂无</strong>}
              </span>
            </div>
          )}
          <SectionDataState
            isLoading={!isDefaultKline && remoteKline.isLoading}
            error={!isDefaultKline ? remoteKline.error : undefined}
            onRetry={() => remoteKline.refetch()}
            isEmpty={!klineData?.items.length}
            emptyText="暂无 K 线数据"
            errorTitle="K 线加载失败"
            skeletonRows={8}
            minHeight={380}
          >
            <div data-pdf-chart="kline">
              <LazyKlineChart
                data={klineData?.items || []}
                height={380}
                viewKey={`${code || "analysis"}:${period}:${adjust}`}
                chanlun={chanlunResult}
                forceRender={isExportingPdf}
              />
            </div>
          </SectionDataState>
        </div>

        {/* Intraday view */}
        {intradayData?.items.length ? (
          <div style={{ display: isExportingPdf || activeTab === "intraday" ? "block" : "none" }}>
            <div data-pdf-chart="intraday">
              <IntradayChart
                data={intradayData.items}
                prevClose={intradayData.prev_close}
                height={380}
                viewKey={code || "analysis"}
              />
            </div>
          </div>
        ) : null}

        {/* MACD belongs to the stock profile; research keeps the complementary oscillators. */}
        {code && (
          <div style={{ marginTop: 12, borderTop: `1px solid ${colors.border}`, paddingTop: 10 }}>
            <IndicatorSubCharts code={code} types={["rsi", "kdj"]} />
          </div>
        )}
      </Card>

      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap", paddingRight: 32 }}>
            <span style={{ fontWeight: "var(--c-weight-bold)", color: colors.textPrimary, fontSize: "16px" }}>
              {pageData?.stock_info?.name || code || "个股"} 行情全屏研判
            </span>
            <Segmented
              options={[
                { label: "K线走势", value: "kline" },
                ...(intradayData?.items.length ? [{ label: "当日分时", value: "intraday" }] : []),
              ]}
              value={activeTab}
              onChange={(value) => setActiveTab(value as "kline" | "intraday")}
            />
          </div>
        }
        open={isExpanded}
        onCancel={() => setIsExpanded(false)}
        footer={null}
        width="min(1380px, 95vw)"
        style={{ top: 20 }}
        destroyOnHidden
      >
        <div style={{ padding: "8px 0" }}>
          {activeTab === "kline" && (
            <div>
              <div className="analysis-chart-toolbar" aria-label="K 线图显示设置" style={{ marginBottom: 12 }}>
                <DataRefreshIndicator active={!isDefaultKline && remoteKline.isFetching} />
                <Segmented
                  options={[
                    { label: "日K", value: "daily" },
                    { label: "周K", value: "weekly" },
                    { label: "月K", value: "monthly" },
                  ]}
                  value={period}
                  onChange={(value) => setPeriod(String(value))}
                />
                <Segmented
                  options={[
                    { label: "前复权", value: "qfq" },
                    { label: "后复权", value: "hfq" },
                    { label: "不复权", value: "" },
                  ]}
                  value={adjust}
                  onChange={(value) => setAdjust(String(value))}
                />
                <Tooltip title="缠论：笔（青色折线）、中枢上下沿（蓝色虚线）、三类买卖点（①②③箭头）">
                  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--c-font-sm)", color: colors.textSecondary, cursor: "pointer" }}>
                    缠论
                    <Switch size="small" checked={chanlunEnabled} onChange={setChanlunEnabled} />
                  </label>
                </Tooltip>
              </div>
              {chanlunResult && (
                <div
                  aria-label="缠论摘要"
                  style={{
                    display: "flex", flexWrap: "wrap", gap: "6px 16px", alignItems: "center",
                    padding: "8px 12px", marginBottom: 10, fontSize: "var(--c-font-xs)",
                    background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 8,
                  }}
                >
                  <span style={{ color: colors.textSecondary }}>
                    笔：
                    <strong style={{ color: lastBi?.direction === "up" ? colors.up : colors.down }}>
                      {lastBi ? `${lastBi.direction === "up" ? "向上" : "向下"} ${lastBi.low.toFixed(2)}–${lastBi.high.toFixed(2)}` : "-"}
                    </strong>
                  </span>
                  <span style={{ color: colors.textSecondary }}>
                    最近中枢：
                    <strong style={{ color: colors.info }}>
                      {lastZs ? `${lastZs.zd.toFixed(2)}–${lastZs.zg.toFixed(2)}（${lastZs.lineCount} 笔${lastZs.done ? "" : "，未完成"}）` : "暂无"}
                    </strong>
                  </span>
                  <span style={{ color: colors.textSecondary }}>
                    最近信号：
                    {lastMmds.length > 0 ? lastMmds.map((mmd) => (
                      <Tooltip key={`${mmd.date}-${mmd.mmdType}`} title={`${mmd.date} ${mmd.msg}`}>
                        <span
                          style={{
                            marginLeft: 6, fontWeight: "var(--c-weight-semibold)",
                            color: mmd.mmdType.endsWith("buy") ? colors.up : colors.down,
                          }}
                        >
                          {MMD_LABELS[mmd.mmdType]}·{mmd.date.slice(5)}
                        </span>
                      </Tooltip>
                    )) : <strong style={{ color: colors.textMuted }}>暂无</strong>}
                  </span>
                </div>
              )}
              <LazyKlineChart
                data={klineData?.items || []}
                height={500}
                viewKey={`modal:${code || "analysis"}:${period}:${adjust}`}
                chanlun={chanlunResult}
                forceRender
              />
              {code && (
                <div style={{ marginTop: 12, borderTop: `1px solid ${colors.border}`, paddingTop: 10 }}>
                  <IndicatorSubCharts code={code} types={["rsi", "kdj"]} />
                </div>
              )}
            </div>
          )}

          {activeTab === "intraday" && intradayData?.items.length && (
            <IntradayChart
              data={intradayData.items}
              prevClose={intradayData.prev_close}
              height={560}
              viewKey={`modal-intraday:${code || "analysis"}`}
            />
          )}

        </div>
      </Modal>
    </section>
  );
});
