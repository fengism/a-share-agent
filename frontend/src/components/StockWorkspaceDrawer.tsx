import { useMemo, useState } from "react";
import { Button, DatePicker, Drawer, Empty, Segmented, Skeleton, Space, Tabs, Tag, Typography } from "antd";
import {
  ArrowRightOutlined,
  LineChartOutlined,
  RobotOutlined,
  StarOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import {
  useDragonTigerDetail,
  useKlineData,
  useStockChipDistribution,
  useStockInfo,
  useStockIntraday,
} from "../api/queries";
import { useAddWatchlistItem, useWatchlist } from "../api/queryHooks/watchlist";
import LazyKlineChart from "../charts/LazyKlineChart";
import IntradayChart from "../charts/IntradayChart";
import ChangeValue from "./ChangeValue";
import ResponsiveMetricGrid from "./ResponsiveMetricGrid";
import SectionDataState from "./SectionDataState";
import ChipDistributionPanel from "../features/stock-insights/ChipDistributionPanel";
import FundFlowPanel from "../features/stock-insights/FundFlowPanel";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { formatNumberWithSeparators } from "../utils/format";
import "./stock-workspace-drawer.css";

const { Text } = Typography;

type ChartView = "kline" | "intraday" | "chip";
type WorkspaceTab = "chart" | "metrics" | "flow" | "ai";

export interface StockWorkspaceDrawerProps {
  open: boolean;
  code: string | null;
  name?: string;
  onClose: () => void;
}

function formatLarge(value: number | null | undefined, unit: "currency" | "shares") {
  if (value == null || !Number.isFinite(value)) return "-";
  const abs = Math.abs(value);
  if (unit === "currency") {
    if (abs >= 1e12) return `${(value / 1e12).toFixed(2)} 万亿`;
    if (abs >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
    if (abs >= 1e4) return `${(value / 1e4).toFixed(2)} 万`;
    return formatNumberWithSeparators(value, 0);
  }
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)} 亿股`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)} 万股`;
  return formatNumberWithSeparators(value, 0);
}

function formatRatio(value: number | null | undefined, suffix = "") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}${suffix}`;
}

export default function StockWorkspaceDrawer({
  open,
  code,
  name,
  onClose,
}: StockWorkspaceDrawerProps) {
  const navigate = useNavigate();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const validCode = code ? code.trim() : "";
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("chart");
  const [chartView, setChartView] = useState<ChartView>("kline");
  const [lhbDate, setLhbDate] = useState<string | null>(null);

  const { data: stockInfo } = useStockInfo(validCode, {
    enabled: open && Boolean(validCode),
  });

  const { data: klineData, isLoading: isKlineLoading } = useKlineData(
    validCode,
    "daily",
    "qfq",
    open && Boolean(validCode) && chartView === "kline",
  );

  const { data: intradayData, isLoading: isIntradayLoading } = useStockIntraday(
    validCode,
    undefined,
    { enabled: open && Boolean(validCode) && chartView === "intraday" },
  );

  const { data: chipData, isLoading: isChipLoading } = useStockChipDistribution(validCode, {
    enabled: open && Boolean(validCode) && chartView === "chip",
  });

  const { data: watchlist } = useWatchlist();
  const addToWatchlistMutation = useAddWatchlistItem();

  const isFavorited = useMemo(() => {
    return Boolean(watchlist?.items?.some((item) => item.stock_code === validCode));
  }, [watchlist, validCode]);

  const candleItems = useMemo(() => klineData?.items ?? [], [klineData]);
  const intradayItems = useMemo(() => intradayData?.items ?? [], [intradayData]);
  const latestCandle = candleItems.length > 0 ? candleItems[candleItems.length - 1] : null;

  // 龙虎榜按交易日查，默认落在已知的最近交易日（K 线末根），避免默认日期无数据。
  const defaultLhbDate = latestCandle?.date ?? dayjs().subtract(1, "day").format("YYYY-MM-DD");
  const reportDate = lhbDate ?? defaultLhbDate;
  const lhbQuery = useDragonTigerDetail(validCode, open && activeTab === "flow" ? reportDate : "");
  const lhbRows = lhbQuery.data ?? [];

  const displayName = name || stockInfo?.name || validCode;
  const price = stockInfo?.current_price ?? latestCandle?.close ?? null;
  const changePct = latestCandle?.change_pct ?? null;
  const high = latestCandle?.high ?? null;
  const low = latestCandle?.low ?? null;
  const turnover = stockInfo?.turnover_pct ?? latestCandle?.turnover_pct ?? null;
  const industry = stockInfo?.first_industry?.name || stockInfo?.exchange_industry || null;

  const handleGoToAnalysis = () => {
    if (!validCode) return;
    onClose();
    navigate(`/analysis/${validCode}`);
  };

  const handleToggleWatchlist = () => {
    if (!validCode || isFavorited) return;
    addToWatchlistMutation.mutate({ stock_code: validCode, note: displayName });
  };

  const handleAskAi = (prompt: string) => {
    if (!validCode) return;
    onClose();
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  const metricItems = [
    { key: "marketCap", label: "总市值", value: formatLarge(stockInfo?.market_cap, "currency") },
    { key: "floatCap", label: "流通市值", value: formatLarge(stockInfo?.float_market_cap, "currency") },
    { key: "peTtm", label: "市盈率 TTM", value: formatRatio(stockInfo?.pe_ttm) },
    { key: "peStatic", label: "静态市盈率", value: formatRatio(stockInfo?.pe_static) },
    { key: "pb", label: "市净率", value: formatRatio(stockInfo?.pb) },
    { key: "turnover", label: "换手率", value: formatRatio(stockInfo?.turnover_pct, "%") },
    { key: "totalShares", label: "总股本", value: formatLarge(stockInfo?.total_shares, "shares") },
    { key: "floatShares", label: "流通股本", value: formatLarge(stockInfo?.circulating_shares, "shares") },
    { key: "listing", label: "上市日期", value: stockInfo?.listing_date || "-" },
  ];

  const metricGrid = <ResponsiveMetricGrid items={metricItems} />;

  const chartPane = (
    <div className="stock-workspace__chart-container">
      {chartView === "kline" ? (
        isKlineLoading ? (
          <div className="stock-workspace__skeleton">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        ) : candleItems.length > 0 ? (
          <LazyKlineChart data={candleItems} height={380} forceRender />
        ) : (
          <div className="stock-workspace__empty">
            <LineChartOutlined className="stock-workspace__empty-icon" />
            <Text type="secondary">暂无 K 线历史数据</Text>
          </div>
        )
      ) : chartView === "intraday" ? (
        isIntradayLoading ? (
          <div className="stock-workspace__skeleton">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        ) : intradayItems.length > 0 ? (
          <IntradayChart
            data={intradayItems}
            prevClose={intradayData?.prev_close ?? null}
            height={380}
          />
        ) : (
          <div className="stock-workspace__empty">
            <LineChartOutlined className="stock-workspace__empty-icon" />
            <Text type="secondary">暂无当日分时数据</Text>
          </div>
        )
      ) : (
        <SectionDataState
          isLoading={isChipLoading}
          error={null}
          onRetry={() => undefined}
          isEmpty={!isChipLoading && !chipData}
          emptyText="暂无筹码分布数据"
          skeletonRows={4}
          minHeight={280}
        >
          {chipData ? <ChipDistributionPanel data={chipData} embedded /> : null}
        </SectionDataState>
      )}
    </div>
  );

  const flowPane = (
    <div className="stock-workspace__pane">
      <FundFlowPanel code={validCode} />

      <section className="stock-workspace__lhb" aria-label="龙虎榜席位">
        <div className="stock-workspace__lhb-head">
          <span className="stock-workspace__lhb-title">龙虎榜机构席位</span>
          <DatePicker
            size="small"
            allowClear={false}
            value={dayjs(reportDate)}
            onChange={(value) => setLhbDate(value ? value.format("YYYY-MM-DD") : null)}
            className="stock-workspace__lhb-date"
          />
        </div>
        {lhbQuery.isLoading ? (
          <Skeleton active paragraph={{ rows: 3 }} />
        ) : lhbRows.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={`${reportDate} 无龙虎榜记录`}
            className="stock-workspace__lhb-empty"
          />
        ) : (
          <ul className="stock-workspace__lhb-list">
            {lhbRows.map((row) => (
              <li key={`${row.operate_name}-${row.side}`} className="stock-workspace__lhb-row">
                <span className="stock-workspace__lhb-seat">{row.operate_name}</span>
                <Tag
                  color={row.side === "buy" ? "volcano" : "cyan"}
                  className="stock-workspace__lhb-side"
                >
                  {row.side === "buy" ? "买入" : "卖出"}
                </Tag>
                <span className="stock-workspace__lhb-amount financial-num">
                  {formatLarge(row.net_amount, "currency")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );

  const aiPane = (
    <div className="stock-workspace__pane">
      <section className="stock-workspace__ai" aria-label="AI 智能诊断">
        <p className="stock-workspace__ai-desc">
          调用投研 Agent 基于当前标的的行情、资金与财报，生成风险点与研报看点摘要。
        </p>
        <Space orientation="vertical" size={8} className="stock-workspace__ai-actions">
          <Button
            block
            icon={<RobotOutlined />}
            onClick={() =>
              handleAskAi(`诊断 ${displayName}(${validCode}) 的主要风险点、资金动向与研报关注要点`)
            }
          >
            AI 风险与看点诊断
          </Button>
          <Button
            block
            icon={<ThunderboltOutlined />}
            onClick={() => handleAskAi(`对比 ${displayName}(${validCode}) 与同业的关键财务与估值差异`)}
          >
            AI 同业对比
          </Button>
          <Button block type="primary" icon={<ArrowRightOutlined />} onClick={handleGoToAnalysis}>
            打开深度研报
          </Button>
        </Space>
      </section>
    </div>
  );

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      size={isMobile ? "100%" : 640}
      destroyOnHidden
      rootClassName="stock-workspace-drawer"
      title={(
        <div className="stock-workspace__title-row">
          <div className="stock-workspace__title-left">
            <span className="stock-workspace__name">{displayName}</span>
            <Tag className="financial-num stock-workspace__code-tag">{validCode}</Tag>
            {industry ? <Tag color="cyan">{industry}</Tag> : null}
          </div>
        </div>
      )}
      extra={(
        <Space size={8}>
          <Button
            size="small"
            icon={<StarOutlined />}
            disabled={isFavorited || addToWatchlistMutation.isPending}
            onClick={handleToggleWatchlist}
          >
            {isFavorited ? "已在自选" : "加自选"}
          </Button>
          <Button size="small" type="primary" icon={<ArrowRightOutlined />} onClick={handleGoToAnalysis}>
            深度研报
          </Button>
        </Space>
      )}
    >
      <div className="stock-workspace__body">
        {/* 顶部行情数据横条 */}
        <div className="stock-workspace__stats-strip">
          <div className="stock-workspace__price-box">
            <span className="stock-workspace__price financial-num">
              {price !== null ? price.toFixed(2) : "--"}
            </span>
            <ChangeValue value={changePct} showIcon />
          </div>

          <div className="stock-workspace__metrics">
            <div className="stock-workspace__metric-cell">
              <span className="stock-workspace__metric-label">最高</span>
              <span className="stock-workspace__metric-val financial-num">{high !== null ? high.toFixed(2) : "--"}</span>
            </div>
            <div className="stock-workspace__metric-cell">
              <span className="stock-workspace__metric-label">最低</span>
              <span className="stock-workspace__metric-val financial-num">{low !== null ? low.toFixed(2) : "--"}</span>
            </div>
            <div className="stock-workspace__metric-cell">
              <span className="stock-workspace__metric-label">换手率</span>
              <span className="stock-workspace__metric-val financial-num">
                {turnover !== null ? `${turnover.toFixed(2)}%` : "--"}
              </span>
            </div>
          </div>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as WorkspaceTab)}
          size="small"
          items={[
            {
              key: "chart",
              label: "K线走势",
              children: (
                <div className="stock-workspace__pane">
                  <div className="stock-workspace__chart-switch">
                    <Segmented
                      size="small"
                      value={chartView}
                      onChange={(val) => setChartView(val as ChartView)}
                      options={[
                        { label: "日K", value: "kline" },
                        { label: "当日分时", value: "intraday" },
                        { label: "筹码分布", value: "chip" },
                      ]}
                    />
                  </div>
                  {chartPane}
                </div>
              ),
            },
            {
              key: "metrics",
              label: "核心指标",
              children: (
                <div className="stock-workspace__pane">
                  {stockInfo ? metricGrid : <Skeleton active paragraph={{ rows: 5 }} />}
                  <Text type="secondary" className="stock-workspace__pane-note">
                    估值分位、业绩预测与同业对比请打开「深度研报」，此处只做速览，避免与研报页重复取数。
                  </Text>
                </div>
              ),
            },
            { key: "flow", label: "主力与龙虎榜", children: flowPane },
            { key: "ai", label: "AI 诊断", children: aiPane },
          ]}
        />
      </div>
    </Drawer>
  );
}
