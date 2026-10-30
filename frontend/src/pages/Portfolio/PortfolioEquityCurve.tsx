import { useMemo } from "react";
import { Alert, Button, Card, Empty, Skeleton, Space, Statistic, Tag, Typography } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import { ReloadOutlined } from "@ant-design/icons";
import { usePortfolioEquityCurve } from "../../api/queries";
import echarts from "../../charts/echarts-setup";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import { changeColor } from "../../utils/format";
import { buildPortfolioEquityOption } from "./portfolioEquityChartOptions";

const { Text } = Typography;

export default function PortfolioEquityCurve() {
  const query = usePortfolioEquityCurve();
  const colors = useColors();
  const { cardStyle } = useStyles();
  const narrow = useMediaQuery("(max-width: 768px)");
  const option = useMemo(
    () => query.data ? buildPortfolioEquityOption(query.data, colors, narrow) : {},
    [colors, narrow, query.data],
  );
  const points = query.data?.points ?? [];
  const warnings = query.data?.warnings ?? [];

  return (
    <Card
      size="small"
      title="总资产变化曲线"
      extra={(
        <Space size={8}>
          {query.data ? (
            <Tag>{query.data.mode === "total_assets" ? "总资产口径" : "仅证券市值"}</Tag>
          ) : null}
          <Button
            size="small"
            icon={<ReloadOutlined />}
            loading={query.isFetching}
            onClick={() => query.refetch()}
          >
            刷新
          </Button>
        </Space>
      )}
      style={{ ...cardStyle, marginBottom: 16 }}
    >
      {query.isLoading ? <Skeleton active paragraph={{ rows: 5 }} /> : null}
      {query.error ? (
        <Alert type="warning" showIcon title="资产曲线加载失败" description="当前持仓数据不受影响，可稍后刷新重试。" />
      ) : null}
      {query.data && !points.length ? <Empty description="暂无交易流水，无法生成资产曲线" /> : null}
      {query.data && points.length ? (
        <>
          <div
            style={{
              background: colors.nestedBg,
              borderRadius: 8,
              padding: "var(--c-pad-inset, 7px 12px)",
              marginBottom: 12,
              border: `1px solid ${colors.border ?? "rgba(128,128,128,0.15)"}`,
            }}
            className="portfolio-equity-quant-ribbon"
          >
            <Space wrap size={narrow ? [12, 8] : 24} style={{ marginBottom: 8 }}>
              {query.data.mode === "total_assets" ? (
                <>
                  <Statistic className="portfolio-equity-stat" title="期末总资产" value={query.data.current_total_assets ?? 0} precision={2} prefix="¥" />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="累计收益率"
                    value={query.data.total_return_pct ?? "-"}
                    precision={2}
                    suffix={query.data.total_return_pct == null ? undefined : "%"}
                    styles={{ content: { color: changeColor(query.data.total_return_pct, colors), fontWeight: 700 } }}
                  />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="最大回撤"
                    value={query.data.max_drawdown_pct ?? "-"}
                    precision={2}
                    suffix={query.data.max_drawdown_pct == null ? undefined : "%"}
                    styles={{ content: { color: colors.down ?? "#52c41a", fontWeight: 700 } }}
                  />
                </>
              ) : (
                <Statistic
                  className="portfolio-equity-stat"
                  title="期末证券市值"
                  value={query.data.current_securities_value ?? 0}
                  precision={2}
                  prefix="¥"
                />
              )}
              <Text type="secondary" style={{ fontSize: "var(--c-font-sm)", alignSelf: "center" }}>
                {query.data.start_date ?? "-"} 至 {query.data.end_date}
              </Text>
            </Space>
            {query.data.mode === "total_assets" ? (
              <>
                <Space wrap size={narrow ? [12, 8] : 24} style={{ marginBottom: 4 }}>
                  <Statistic
                    className="portfolio-equity-stat"
                    title="年化收益"
                    value={query.data.annualized_return_pct ?? "-"}
                    precision={2}
                    suffix={query.data.annualized_return_pct == null ? undefined : "%"}
                    styles={{ content: { color: changeColor(query.data.annualized_return_pct, colors), fontWeight: 700 } }}
                  />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="年化波动"
                    value={query.data.annualized_volatility_pct ?? "-"}
                    precision={2}
                    suffix={query.data.annualized_volatility_pct == null ? undefined : "%"}
                  />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="夏普比率"
                    value={query.data.sharpe_ratio ?? "-"}
                    precision={2}
                  />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="卡玛比率"
                    value={query.data.calmar_ratio ?? "-"}
                    precision={2}
                  />
                  <Statistic
                    className="portfolio-equity-stat"
                    title="胜率"
                    value={query.data.win_rate_pct ?? "-"}
                    precision={2}
                    suffix={query.data.win_rate_pct == null ? undefined : "%"}
                  />
                </Space>
                <Text type="secondary" style={{ fontSize: "var(--c-font-sm)", display: "block", marginTop: 4 }}>
                  最佳单日 {query.data.best_day_pct == null ? "-" : `${query.data.best_day_pct.toFixed(2)}%`}
                  {" · "}最差单日 {query.data.worst_day_pct == null ? "-" : `${query.data.worst_day_pct.toFixed(2)}%`}
                  {" · "}最长回撤 {query.data.longest_drawdown_days == null ? "-" : `${query.data.longest_drawdown_days} 天`}
                  {" · "}样本 {query.data.trading_days} 个交易日
                  {" · "}无风险利率 {query.data.risk_free_rate_pct.toFixed(2)}%
                </Text>
              </>
            ) : null}
          </div>
          <ReactECharts
            echarts={echarts}
            option={option}
            style={{ height: narrow ? 300 : 380 }}
            notMerge
            data-testid="portfolio-equity-chart"
          />
          {warnings.length ? (
            <Alert
              type="info"
              showIcon
              title="曲线口径说明"
              description={warnings.map((warning) => <div key={warning}>{warning}</div>)}
              style={{ marginTop: 12 }}
            />
          ) : null}
        </>
      ) : null}
    </Card>
  );
}
