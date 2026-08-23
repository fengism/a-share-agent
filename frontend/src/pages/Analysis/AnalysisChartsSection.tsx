import { memo, useState } from "react";
import { Card, Segmented } from "antd";
import { useKlineData, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisPageData } from "../../types/stock";

export default memo(function AnalysisChartsSection({ code, pageData }: { code?: string; pageData?: AnalysisPageData }) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [period, setPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const intradayQuery = useStockIntraday(code || "", pageData?.intraday);
  const intradayData = Array.isArray(intradayQuery.data?.items)
    ? intradayQuery.data
    : pageData?.intraday;
  const isDefaultKline = period === "daily" && adjust === "qfq";
  const remoteKline = useKlineData(code || "", period, adjust, Boolean(code) && !isDefaultKline);
  const klineData = isDefaultKline ? pageData?.kline : remoteKline.data;
  const intradayItems = intradayData?.items ?? [];
  const latestIntraday = intradayItems.length > 0 ? intradayItems[intradayItems.length - 1] : undefined;

  return (
    <section className="analysis-charts-section" aria-label="个股行情图表">
      {intradayData?.items.length ? (
        <Card
          size="small"
          className="analysis-chart-card pdf-avoid-break"
          title={<span style={{ fontWeight: 700, color: colors.textPrimary }}>最新分时图</span>}
          extra={<span className="analysis-chart-caption">当日分时走势与成交量</span>}
          style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
          styles={{ body: { padding: "12px 16px" } }}
        >
          <div className="metric-grid cols-3 analysis-intraday-metrics">
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>最新价</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: colors.textPrimary }}>{latestIntraday?.price?.toFixed(2) ?? "-"}</div>
            </div>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>分时涨跌幅</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: (latestIntraday?.change_pct ?? 0) >= 0 ? colors.up : colors.down }}>
                {latestIntraday?.change_pct != null
                  ? `${latestIntraday.change_pct > 0 ? "+" : ""}${latestIntraday.change_pct.toFixed(2)}%`
                  : "-"}
              </div>
            </div>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>昨收价</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: colors.textPrimary }}>
                {intradayData.prev_close != null ? intradayData.prev_close.toFixed(2) : "-"}
              </div>
            </div>
          </div>
          <IntradayChart
            data={intradayData.items}
            prevClose={intradayData.prev_close}
            viewKey={code || "analysis"}
          />
        </Card>
      ) : null}

      <Card
        size="small"
        className="analysis-chart-card analysis-kline-card pdf-avoid-break"
        title={<span style={{ fontWeight: 700, color: colors.textPrimary }}>K线图</span>}
        style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
      >
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
        </div>
        <SectionDataState
          isLoading={!isDefaultKline && remoteKline.isLoading}
          error={!isDefaultKline ? remoteKline.error : undefined}
          onRetry={() => remoteKline.refetch()}
          isEmpty={!klineData?.items.length}
          emptyText="暂无 K 线数据"
          errorTitle="K 线加载失败"
          skeletonRows={8}
          minHeight={500}
        >
          <LazyKlineChart
            data={klineData?.items || []}
            viewKey={`${code || "analysis"}:${period}:${adjust}`}
          />
        </SectionDataState>
      </Card>

      {code && (
        <Card
          size="small"
          className="analysis-chart-card analysis-indicator-card"
          style={cardStyle}
          styles={{ body: { padding: "12px 16px" } }}
        >
          <IndicatorSubCharts code={code} />
        </Card>
      )}
    </section>
  );
});
