import { useMemo, type ReactNode } from "react";
import { Button, Skeleton, Tooltip } from "antd";
import {
  AppstoreOutlined,
  DashboardOutlined,
  FireOutlined,
  ReloadOutlined,
  RightOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  useIndustryRankings,
  useMarketEmotion,
  useMarketIndices,
  useMarketLimitUpLadder,
  useThsHotConcept,
} from "../api/queries";
import ChangeValue from "./ChangeValue";
import { formatAmount, formatHotValue } from "../utils/format";
import type { MarketEmotionDistribution } from "../types/stock";
import "./market-overview.css";

interface MarketOverviewBoardProps {
  onNavigate: (tab: string) => void;
  showRankings?: boolean;
}

function heatLabel(degree: number | null | undefined) {
  if (degree == null) return "等待更新";
  if (degree <= 20) return "冰点";
  if (degree <= 40) return "偏冷";
  if (degree <= 60) return "中性";
  if (degree <= 80) return "活跃";
  return "亢奋";
}

function formatPrice(value: number | null) {
  return value == null ? "-" : value.toFixed(2);
}

function marketSessionLabel() {
  const now = dayjs();
  if (now.day() === 0 || now.day() === 6) return "今日休市";
  const minutes = now.hour() * 60 + now.minute();
  if (minutes < 9 * 60 + 15) return "盘前准备";
  if (minutes < 11 * 60 + 30) return "交易中";
  if (minutes < 13 * 60) return "午间休市";
  if (minutes < 15 * 60) return "交易中";
  return "已收盘";
}

function formatChineseDate(value: dayjs.Dayjs) {
  const weekdays = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];
  return `${value.format("YYYY年M月D日")} ${weekdays[value.day()]}`;
}

function PanelHeader({
  icon,
  title,
  meta,
  onMore,
}: {
  icon: ReactNode;
  title: string;
  meta?: string;
  onMore?: () => void;
}) {
  return (
    <header className="market-board-panel__header">
      <div className="market-board-panel__title">
        <span className="market-board-panel__icon">{icon}</span>
        <strong>{title}</strong>
        {meta ? <span>{meta}</span> : null}
      </div>
      {onMore ? (
        <Button
          type="text"
          size="small"
          aria-label={`查看${title}详情`}
          onClick={onMore}
          className="market-board-panel__more"
        >
          查看详情 <RightOutlined />
        </Button>
      ) : null}
    </header>
  );
}

function PanelPlaceholder({ loading, error, emptyText }: { loading: boolean; error: unknown; emptyText: string }) {
  if (loading) {
    return <Skeleton active title={false} paragraph={{ rows: 3, width: ["100%", "88%", "72%"] }} />;
  }
  return <div className="market-board-panel__placeholder">{error ? "数据暂时不可用，可尝试刷新" : emptyText}</div>;
}

function MarketDistribution({ distribution }: { distribution: MarketEmotionDistribution }) {
  const rows = [
    { label: "8%以上", down: distribution.down_10, up: distribution.up_10 },
    { label: "6%～8%", down: distribution.down_8, up: distribution.up_8 },
    { label: "4%～6%", down: distribution.down_6, up: distribution.up_6 },
    { label: "2%～4%", down: distribution.down_4, up: distribution.up_4 },
    { label: "0%～2%", down: distribution.down_2, up: distribution.up_2 },
  ];
  const maxValue = Math.max(1, ...rows.flatMap((row) => [row.down, row.up]));
  const barWidth = (value: number) => value === 0 ? 0 : Math.max(3, (value / maxValue) * 100);

  return (
    <section className="market-board-distribution" aria-label="全市场涨跌结构">
      <div className="market-board-distribution__heading">
        <strong>全市场涨跌结构</strong>
        <span>
          上涨 <b className="is-up">{distribution.rise_num}</b>
          <i aria-hidden="true">·</i>
          平盘 <b>{distribution.flat_num}</b>
          <i aria-hidden="true">·</i>
          下跌 <b className="is-down">{distribution.fall_num}</b>
        </span>
      </div>
      <div className="market-board-distribution__header" aria-hidden="true">
        <span>下跌家数</span>
        <span>涨跌幅</span>
        <span>上涨家数</span>
      </div>
      {rows.map((row) => (
        <div className="market-board-distribution__row" key={row.label}>
          <div className="market-board-distribution__side market-board-distribution__side--down">
            <strong>{row.down}</strong>
            <div className="market-board-distribution__track">
              <span style={{ width: `${barWidth(row.down)}%` }} />
            </div>
          </div>
          <span className="market-board-distribution__label">{row.label}</span>
          <div className="market-board-distribution__side market-board-distribution__side--up">
            <div className="market-board-distribution__track">
              <span style={{ width: `${barWidth(row.up)}%` }} />
            </div>
            <strong>{row.up}</strong>
          </div>
        </div>
      ))}
    </section>
  );
}

export default function MarketOverviewBoard({ onNavigate, showRankings = true }: MarketOverviewBoardProps) {
  const today = dayjs().format("YYYY-MM-DD");
  const indicesQuery = useMarketIndices();
  const emotionQuery = useMarketEmotion();
  const ladderQuery = useMarketLimitUpLadder(today);
  const industryQuery = useIndustryRankings(today);
  const conceptQuery = useThsHotConcept();

  const indices = useMemo(() => indicesQuery.data?.indices.slice(0, 6) ?? [], [indicesQuery.data?.indices]);
  const distribution = emotionQuery.data?.up_down_dis;
  const riseCount = distribution?.rise_num ?? 0;
  const fallCount = distribution?.fall_num ?? 0;
  const breadthTotal = riseCount + fallCount;
  const risePercent = breadthTotal > 0 ? (riseCount / breadthTotal) * 100 : 50;
  const degree = emotionQuery.data?.market_degree;
  const degreePercent = degree == null ? 0 : Math.max(0, Math.min(100, degree));
  const maxBoardCount = Math.max(0, ...(ladderQuery.data?.stocks ?? []).map((stock) => stock.board_count));
  const ladderStocks = useMemo(
    () => [...(ladderQuery.data?.stocks ?? [])]
      .sort((left, right) => right.board_count - left.board_count || left.limit_up_time.localeCompare(right.limit_up_time))
      .slice(0, 6),
    [ladderQuery.data?.stocks],
  );
  const industries = useMemo(
    () => [...(industryQuery.data?.sectors ?? [])]
      .sort((left, right) => (right.change_pct ?? Number.NEGATIVE_INFINITY) - (left.change_pct ?? Number.NEGATIVE_INFINITY))
      .slice(0, 6),
    [industryQuery.data?.sectors],
  );
  const concepts = useMemo(
    () => [...(conceptQuery.data ?? [])]
      .sort((left, right) => (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER))
      .slice(0, 6),
    [conceptQuery.data],
  );
  const sessionLabel = marketSessionLabel();
  const isRefreshing = [
    indicesQuery,
    emotionQuery,
    ladderQuery,
    industryQuery,
    conceptQuery,
  ].some((query) => query.isFetching);

  const refreshAll = () => {
    void Promise.all([
      indicesQuery.refetch(),
      emotionQuery.refetch(),
      ladderQuery.refetch(),
      industryQuery.refetch(),
      conceptQuery.refetch(),
    ]);
  };

  const overviewMetrics = [
    { label: "两市成交额", value: emotionQuery.data?.shsz_balance || "-", note: emotionQuery.data?.shsz_balance_change_px || "较前日 -", tone: "neutral" },
    { label: "上涨家数", value: String(riseCount), note: breadthTotal > 0 ? `占比 ${risePercent.toFixed(1)}%` : "等待更新", tone: "up" },
    { label: "下跌家数", value: String(fallCount), note: breadthTotal > 0 ? `占比 ${(100 - risePercent).toFixed(1)}%` : "等待更新", tone: "down" },
    { label: "涨停", value: String(distribution?.up_num ?? 0), note: `封板率 ${emotionQuery.data?.up_ratio || "-"}`, tone: "up" },
    { label: "跌停", value: String(distribution?.down_num ?? 0), note: "全市场", tone: "down" },
    { label: "炸板", value: String(emotionQuery.data?.up_open_num ?? 0), note: `炸板率 ${emotionQuery.data?.up_open_ratio || "-"}`, tone: "warning" },
  ];

  return (
    <section className="market-board" aria-label="市场看板">
      <div className="market-board__toolbar">
        <div className="market-board__status">
          <span className={`market-board__status-dot${sessionLabel === "交易中" ? " is-open" : ""}`} />
          <strong>{sessionLabel}</strong>
          <span>{formatChineseDate(dayjs())}</span>
        </div>
        <Button icon={<ReloadOutlined />} loading={isRefreshing} onClick={refreshAll}>刷新看板</Button>
      </div>

      <section className="market-board__indices" aria-label="核心指数">
        {indices.length > 0 ? indices.map((index) => {
          const tone = index.change_pct == null || index.change_pct === 0 ? "flat" : index.change_pct > 0 ? "up" : "down";
          return (
            <button key={index.code} type="button" className={`market-board-index market-board-index--${tone}`} onClick={() => onNavigate("a-index")}>
              <span className="market-board-index__identity"><strong>{index.name}</strong><small>{index.code}</small></span>
              <span className="market-board-index__quote"><strong>{formatPrice(index.price)}</strong><ChangeValue value={index.change_pct} showIcon /></span>
              <span className="market-board-index__amount">成交额 {formatAmount(index.amount)}</span>
            </button>
          );
        }) : (
          <div className="market-board__wide-placeholder">
            <PanelPlaceholder loading={indicesQuery.isLoading} error={indicesQuery.error} emptyText="暂无指数行情" />
          </div>
        )}
      </section>

      <section className="market-board__metrics" aria-label="市场核心指标">
        {overviewMetrics.map((metric) => (
          <div key={metric.label} className={`market-board-metric market-board-metric--${metric.tone}`}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.note}</small>
          </div>
        ))}
      </section>

      <div className="market-board__grid">
        <section className="market-board-panel market-board-panel--emotion">
          <PanelHeader icon={<DashboardOutlined />} title="市场情绪" meta={emotionQuery.data?.source} onMore={() => onNavigate("emotion")} />
          {emotionQuery.data ? (
            <div className="market-board-emotion">
              <div className="market-board-emotion__score">
                <span>市场热度</span>
                <strong>{degree ?? "-"}</strong>
                <small>{heatLabel(degree)}</small>
                <div className="market-board-emotion__meter" aria-label={`市场热度 ${degree ?? "暂无"}`}>
                  <span style={{ width: `${degreePercent}%` }} />
                </div>
              </div>
              <div className="market-board-emotion__breadth">
                <div><span>上涨</span><strong className="is-up">{riseCount}</strong></div>
                <div><span>下跌</span><strong className="is-down">{fallCount}</strong></div>
                <div className="market-board-emotion__breadth-bar" aria-label={`上涨占比 ${risePercent.toFixed(1)}%`}>
                  <span className="is-up" style={{ width: `${risePercent}%` }} />
                  <span className="is-down" style={{ width: `${100 - risePercent}%` }} />
                </div>
                <p>{riseCount >= fallCount ? "上涨力量占优，关注强势方向持续性" : "下跌家数占优，注意控制市场风险敞口"}</p>
              </div>
              {distribution ? <MarketDistribution distribution={distribution} /> : null}
            </div>
          ) : <PanelPlaceholder loading={emotionQuery.isLoading} error={emotionQuery.error} emptyText="暂无市场情绪数据" />}
        </section>

        <section className="market-board-panel market-board-panel--ladder">
          <PanelHeader icon={<FireOutlined />} title="涨停梯队" meta={maxBoardCount > 0 ? `高度 ${maxBoardCount} 板` : undefined} onMore={() => onNavigate("limit-up")} />
          {ladderStocks.length > 0 ? (
            <div className="market-board-ladder">
              {ladderStocks.map((stock, index) => (
                <div className="market-board-ladder__row" key={stock.code}>
                  <span className={`market-board-rank${index < 3 ? " is-top" : ""}`}>{index + 1}</span>
                  <span className="market-board-ladder__stock"><strong>{stock.name}</strong><small>{stock.sector_name || "其他"}</small></span>
                  <Tooltip title={`涨停时间 ${stock.limit_up_time || "-"}`}><span className="market-board-ladder__board">{stock.board_count}板</span></Tooltip>
                </div>
              ))}
            </div>
          ) : <PanelPlaceholder loading={ladderQuery.isLoading} error={ladderQuery.error} emptyText="暂无涨停梯队数据" />}
        </section>

        {showRankings ? (
          <>
            <section className="market-board-panel">
              <PanelHeader icon={<RiseOutlined />} title="行业强弱" meta={industryQuery.data?.date?.slice(5)} onMore={() => onNavigate("industry-rank")} />
              {industries.length > 0 ? (
                <div className="market-board-ranking">
                  {industries.map((industry, index) => (
                    <div className="market-board-ranking__row" key={industry.code || industry.name}>
                      <span className={`market-board-rank${index < 3 ? " is-top" : ""}`}>{industry.rank ?? index + 1}</span>
                      <span className="market-board-ranking__name"><strong>{industry.name}</strong><small>{industry.leader ? `领涨 ${industry.leader}` : `${industry.up_count ?? 0} 涨 / ${industry.down_count ?? 0} 跌`}</small></span>
                      <ChangeValue value={industry.change_pct} />
                    </div>
                  ))}
                </div>
              ) : <PanelPlaceholder loading={industryQuery.isLoading} error={industryQuery.error} emptyText="暂无行业排行" />}
            </section>

            <section className="market-board-panel">
              <PanelHeader icon={<AppstoreOutlined />} title="热门概念" meta="同花顺热榜" />
              {concepts.length > 0 ? (
                <div className="market-board-ranking">
                  {concepts.map((concept, index) => (
                    <div className="market-board-ranking__row" key={concept.code || concept.name}>
                      <span className={`market-board-rank${index < 3 ? " is-top" : ""}`}>{concept.rank ?? index + 1}</span>
                      <span className="market-board-ranking__name"><strong>{concept.name}</strong><small>{concept.hot_tag || concept.tag || `热度 ${formatHotValue(concept.hot_value)}`}</small></span>
                      <ChangeValue value={concept.change_pct} />
                    </div>
                  ))}
                </div>
              ) : <PanelPlaceholder loading={conceptQuery.isLoading} error={conceptQuery.error} emptyText="暂无概念热榜" />}
            </section>
          </>
        ) : null}

      </div>
    </section>
  );
}
