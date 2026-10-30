import { useMemo } from "react";
import { Popover, Segmented, Tooltip } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import KlineChart from "../../charts/KlineChart";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import type { ConceptIndexPoint } from "../../api/queryHooks/concept";
import type { KlineItem } from "../../types/stock";
import BreadthBar from "./BreadthBar";
import { CONCEPT_INDEX_RANGES } from "./conceptSelection";

interface Props {
  concept: string;
  points: ConceptIndexPoint[] | undefined;
  days: number;
  onDaysChange: (days: number) => void;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  /** 成分股数量，用于说明指数的样本口径 */
  constituentTotal: number;
  constituentUsed: number;
  truncated: boolean;
  /** 工具栏右侧附加控件（如「走势/对比」视图切换） */
  toolbarExtra?: React.ReactNode;
}

/**
 * 把合成指数点转成 K 线图要的形状。
 *
 * 下方成交量窗格由 KlineChart 优先取``amount``，因此这里放成分股当日成交额合计
 * （概念指数本身没有"成交量"这个量）。涨跌家数放到顶部 KPI 条里更醒目。
 */
function toKlineItems(points: ConceptIndexPoint[]): KlineItem[] {
  return points.map((point) => ({
    date: point.date,
    open: point.open,
    high: point.high,
    low: point.low,
    close: point.close,
    volume: point.up_count,
    // KlineItem.amount 为必填 number，而后端 amount 可缺省；缺省时按 0 处理，
    // 成交量窗格会退化为无成交额柱，不影响价格主线渲染。
    amount: point.amount ?? 0,
    amplitude: null,
    turnover_pct: null,
    change_pct: point.change_pct,
  }));
}

function StatItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <span className="concept-kpi__stat">
      <span className="concept-kpi__stat-label">{label}</span>
      <span className="concept-kpi__stat-value financial-num">{value}</span>
    </span>
  );
}

export default function ConceptIndexPanel({
  concept,
  points,
  days,
  onDaysChange,
  isLoading,
  error,
  onRetry,
  constituentTotal,
  constituentUsed,
  truncated,
  toolbarExtra,
}: Props) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const items = useMemo(() => toKlineItems(points ?? []), [points]);

  const latest = points?.at(-1);
  const first = points?.[0];
  const periodChange = useMemo(() => {
    if (!latest || !first || first.close === 0) return null;
    return (latest.close / first.close - 1) * 100;
  }, [first, latest]);

  // 涨跌家数取自合成指数的最新一天（全样本口径），平家数 = 样本 - 涨 - 跌
  const flatCount = latest ? Math.max(latest.sample_count - latest.up_count - latest.down_count, 0) : 0;

  // 区间统计：当前档位内的最高/最低点，帮助判断板块位置
  const rangeHighLow = useMemo(() => {
    if (!points?.length) return null;
    let high = -Infinity;
    let low = Infinity;
    for (const point of points) {
      if (point.high > high) high = point.high;
      if (point.low < low) low = point.low;
    }
    return high === -Infinity ? null : { high, low };
  }, [points]);

  return (
    <div className="concept-index-panel" style={{ display: "flex", flexDirection: "column", gap: isNarrow ? 8 : 10, minWidth: 0 }}>
      {/* KPI 条：概念点位大数字 + 涨跌分布 + 涨停/成交额，一眼看清板块温度 */}
      <div className="concept-kpi">
        <div className="concept-kpi__main">
          <strong className="concept-kpi__name">{concept}</strong>
          {latest ? (
            <>
              <span
                aria-label="合成指数点位"
                className="concept-kpi__close financial-num"
                style={{ color: latest.change_pct > 0 ? c.up : latest.change_pct < 0 ? c.down : c.textPrimary }}
              >
                {latest.close.toFixed(2)}
              </span>
              <ChangeValue value={latest.change_pct} digits={2} showIcon />
              {periodChange != null ? (
                <span className="concept-kpi__period" style={{ color: c.textMuted }}>
                  区间
                  <ChangeValue value={periodChange} digits={2} />
                </span>
              ) : null}
            </>
          ) : (
            <span style={{ fontSize: 12, color: c.textMuted }}>指数合成中…</span>
          )}
        </div>
        {latest ? (
          <div className="concept-kpi__stats">
            <BreadthBar up={latest.up_count} flat={flatCount} down={latest.down_count} />
            <StatItem
              label="涨停/跌停"
              value={
                <>
                  <span style={{ color: latest.limit_up_count ? c.up : undefined }}>{latest.limit_up_count}</span>
                  <span style={{ color: c.textMuted }}> / </span>
                  <span style={{ color: latest.limit_down_count ? c.down : undefined }}>{latest.limit_down_count}</span>
                </>
              }
            />
            <StatItem label="成交额" value={latest.amount == null ? "—" : `${(latest.amount / 1e8).toFixed(0)}亿`} />
            {rangeHighLow ? (
              <StatItem
                label="区间高/低"
                value={`${rangeHighLow.high.toFixed(0)} / ${rangeHighLow.low.toFixed(0)}`}
              />
            ) : null}
            <StatItem label="样本" value={`${latest.sample_count}/${constituentUsed}`} />
          </div>
        ) : null}
      </div>

      <div className="concept-index-toolbar">
        <Tooltip title="概念指数由板块内成分股走势合成，仅反映该概念的整体强弱">
          <span className="concept-kpi__tag">
            <InfoCircleOutlined /> 成分股等权合成
          </span>
        </Tooltip>
        <div className="concept-index-toolbar__controls">
          {toolbarExtra}
          <Segmented
            size="small"
            value={days}
            options={CONCEPT_INDEX_RANGES.map((range) => ({ label: range.label, value: range.days }))}
            onChange={(value) => onDaysChange(Number(value))}
          />
        </div>
      </div>

      <SectionDataState
        isLoading={isLoading && !points?.length}
        error={points?.length ? undefined : error}
        onRetry={onRetry}
        isEmpty={!isLoading && !error && !points?.length}
        emptyText={`暂无「${concept}」的合成指数数据`}
        errorTitle="概念指数加载失败"
        minHeight={isNarrow ? 300 : 360}
      >
        <KlineChart
          data={items}
          height={isNarrow ? 320 : 380}
          viewKey={`${concept}-concept-index-${days}`}
          defaultSubIndicator="AMO"
        />
      </SectionDataState>

      {/* 口径说明收敛为一行 + Popover：默认界面不再出现复利/前复权等术语 */}
      <p className="concept-index-note" style={{ color: c.textMuted }}>
        指数由「{concept}」成分股走势等权合成，用来观察板块整体强弱与涨跌分布，不是交易所或行情软件发布的官方概念指数。
        <Popover
          placement="topLeft"
          title="数据口径"
          content={
            <div className="concept-caliper">
              <p>· 合成方式：成分股前复权日线等权平均、逐日链式复利，基期 1000。</p>
              <p>
                · 样本范围：
                {truncated
                  ? `概念共 ${constituentTotal} 只成分股，指数取流动性靠前的 ${constituentUsed} 只参与合成。`
                  : `全部 ${constituentTotal} 只成分股均参与合成。`}
                停牌与新股会使当日样本略有变化。
              </p>
              <p>· 图表下方窗格为成分股当日成交额合计。</p>
              <p>· 成分股盘中显示实时价；实时行情不可用时显示当日收盘价，并在价格颜色上以灰色区分。</p>
              <p>· 成分名单取自同花顺概念映射（本地维护）。</p>
            </div>
          }
        >
          <a role="button" onClick={(e) => e.preventDefault()}>查看详细口径</a>
        </Popover>
      </p>
    </div>
  );
}
