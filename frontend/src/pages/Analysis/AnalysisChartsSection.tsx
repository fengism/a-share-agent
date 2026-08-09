import { memo, useState } from "react";
import { Card, Segmented, Space } from "antd";
import { useKlineData } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import KlineChart from "../../charts/KlineChart";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisPageData } from "../../types/stock";

export default memo(function AnalysisChartsSection({ code, pageData }: { code?: string; pageData?: AnalysisPageData }) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [period, setPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const intradayData = pageData?.intraday;
  const isDefaultKline = period === "daily" && adjust === "qfq";
  const remoteKline = useKlineData(code || "", period, adjust, Boolean(code) && !isDefaultKline);
  const klineData = isDefaultKline ? pageData?.kline : remoteKline.data;
  const intradayItems = intradayData?.items ?? [];
  const latestIntraday = intradayItems.length > 0 ? intradayItems[intradayItems.length - 1] : undefined;

  return (
    <>
      {intradayData?.items.length ? (
        <Card
          size="small"
          className="pdf-avoid-break"
          title={<span style={{ fontWeight: 700, color: colors.textPrimary }}>最新分时图</span>}
          extra={<span style={{ fontSize: 12, color: colors.textSecondary }}>当日分时走势与成交量</span>}
          style={{ ...cardStyle, marginBottom: 14, borderTop: `3px solid ${colors.primary}`, boxShadow: "0 1px 2px rgba(0,0,0,0.18)" }}
          styles={{ body: { padding: "12px 16px" } }}
        >
          <div className="metric-grid cols-3" style={{ gap: 12, marginBottom: 12 }}>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>最新价</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: colors.textPrimary }}>{latestIntraday?.price?.toFixed(2) ?? "-"}</div>
            </div>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>分时涨跌幅</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: (latestIntraday?.change_pct ?? 0) >= 0 ? colors.up : colors.down }}>
                {latestIntraday?.change_pct != null
                  ? `${latestIntraday.change_pct > 0 ? "+" : ""}${latestIntraday.change_pct.toFixed(2)}%`
                  : "-"}
              </div>
            </div>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10 }}>
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
        className="pdf-avoid-break"
        title={<span style={{ fontWeight: 700, color: colors.textPrimary }}>K线图</span>}
        style={{ ...cardStyle, marginBottom: 14, borderTop: `3px solid ${colors.primary}`, boxShadow: "0 1px 2px rgba(0,0,0,0.18)" }}
        extra={
          <Space size={10} style={{ background: colors.nestedBg, border: `1px solid ${colors.border}`, borderRadius: 10, padding: "6px 8px" }}>
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
          </Space>
        }
      >
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
          <KlineChart
            data={klineData?.items || []}
            viewKey={`${code || "analysis"}:${period}:${adjust}`}
          />
        </SectionDataState>
      </Card>

      {code && (
        <Card size="small" style={{ ...cardStyle, marginTop: 16 }} styles={{ body: { padding: "12px 16px" } }}>
          <IndicatorSubCharts code={code} />
        </Card>
      )}
    </>
  );
});
