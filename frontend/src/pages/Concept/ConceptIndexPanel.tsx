import { useMemo } from "react";
import { Segmented, Tag, Tooltip } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import KlineChart from "../../charts/KlineChart";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import type { ConceptIndexPoint } from "../../api/queryHooks/concept";
import type { KlineItem } from "../../types/stock";
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
}

/**
 * 把合成指数点转成 K 线图要的形状。
 *
 * 下方成交量窗格由 KlineChart 优先取``amount``，因此这里放成分股当日成交额合计
 * （概念指数本身没有"成交量"这个量）。涨跌家数放在上方统计行里更醒目。
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

  return (
    <div className="concept-index-panel" style={{ display: "flex", flexDirection: "column", gap: isNarrow ? 8 : 10, minWidth: 0 }}>
      <div className="concept-index-header">
        <div className="concept-index-price">
          <strong className="concept-index-price__name">{concept}</strong>
          {latest ? (
            <>
              <span
                aria-label="合成指数点位"
                className="concept-index-price__val financial-num"
                style={{
                  fontSize: isNarrow ? 16 : 18,
                  fontWeight: 600,
                  color: c.textPrimary,
                }}
              >
                {latest.close.toFixed(2)}
              </span>
              <ChangeValue value={latest.change_pct} digits={2} />
              {periodChange != null ? (
                <span style={{ fontSize: isNarrow ? 11.5 : 12, color: c.textMuted }}>
                  区间
                  <ChangeValue value={periodChange} digits={2} />
                </span>
              ) : null}
            </>
          ) : null}
        </div>
        <div className="concept-index-ranges">
          <Segmented
            size="small"
            value={days}
            options={CONCEPT_INDEX_RANGES.map((range) => ({ label: range.label, value: range.days }))}
            onChange={(value) => onDaysChange(Number(value))}
          />
        </div>
      </div>

      {latest ? (
        <div className="concept-index-stats">
          <span>
            上涨 <strong style={{ color: c.up }}>{latest.up_count}</strong>
          </span>
          <span>
            下跌 <strong style={{ color: c.down }}>{latest.down_count}</strong>
          </span>
          <span>
            涨停 <strong style={{ color: c.up }}>{latest.limit_up_count}</strong>
          </span>
          <span>
            跌停 <strong style={{ color: c.down }}>{latest.limit_down_count}</strong>
          </span>
          <span>
            成交额{" "}
            <strong className="financial-num" style={{ color: c.textPrimary }}>
              {latest.amount == null ? "—" : `${(latest.amount / 1e8).toFixed(0)}亿`}
            </strong>
          </span>
          <Tooltip
            title={
              truncated
                ? `概念共 ${constituentTotal} 只成分股，合成指数取前 ${constituentUsed} 只`
                : `样本 ${latest.sample_count} 只（停牌与新股会改变当日样本）`
            }
          >
            <span style={{ cursor: "help" }}>
              <InfoCircleOutlined /> 样本 {latest.sample_count}/{constituentUsed}
            </span>
          </Tooltip>
          <Tag className="concept-index-stats__tag" style={{ marginInlineEnd: 0, fontSize: isNarrow ? 11 : 12 }} color="default">
            本地合成等权指数
          </Tag>
        </div>
      ) : null}

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

      <p style={{ margin: 0, fontSize: 11, lineHeight: 1.6, color: c.textMuted }}>
        指数由本地成分股<b>前复权</b>日线等权平均、逐日链式复利合成（基期 1000），下方窗格显示当日成分股成交额合计。
        它不等同于交易所或同花顺发布的官方概念指数，仅用于观察板块内个股的整体强弱与涨跌分布。
      </p>
    </div>
  );
}