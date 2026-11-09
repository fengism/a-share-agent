import React, { useMemo } from "react";
import type { IndustryLeekItem } from "../../api/queryHooks/sentiment";
import { formatSignedAmount } from "./utils";
import "./leek-macro-cockpit.css";

interface Props {
  summary: {
    median_score: number;
    extreme_count: number;
    fever_count: number;
    safe_count: number;
    market_sentiment_label: string;
  };
  industries: IndustryLeekItem[];
  onSelectRiskTier?: (level: string) => void;
}

export const LeekMacroCockpit: React.FC<Props> = ({
  summary,
  industries,
  onSelectRiskTier,
}) => {
  const totalCount = industries.length > 0 ? industries.length : 31;
  const extremeCount = summary.extreme_count;
  const feverCount = summary.fever_count;
  const safeCount = summary.safe_count;
  const normalCount = Math.max(0, totalCount - extremeCount - feverCount - safeCount);

  // 百分比计算（用于 SVG 堆叠全景条）
  const extremePct = (extremeCount / totalCount) * 100;
  const feverPct = (feverCount / totalCount) * 100;
  const normalPct = (normalCount / totalCount) * 100;
  const safePct = (safeCount / totalCount) * 100;

  // 全市场主力与散户对冲总敞口
  const { totalMainNet, totalRetailNet, totalScissors } = useMemo(() => {
    let main = 0;
    let retail = 0;
    for (const ind of industries) {
      main += ind.main_net;
      retail += ind.retail_net;
    }
    return {
      totalMainNet: main,
      totalRetailNet: retail,
      totalScissors: retail - main,
    };
  }, [industries]);

  // 半环仪表弧长计算：半径 54，周长 169.65
  const medianScore = summary.median_score ?? 50.0;
  const gaugeCircumference = 169.65;
  const progressRatio = Math.max(0, Math.min(100, medianScore)) / 100;
  const strokeDashoffset = gaugeCircumference * (1 - progressRatio);

  const riskClass =
    medianScore >= 75
      ? "extreme"
      : medianScore >= 60
      ? "fever"
      : medianScore >= 35
      ? "normal"
      : "safe";

  const tierBadgeLabel =
    medianScore >= 75
      ? "极度接盘·高危"
      : medianScore >= 60
      ? "情绪过热·警戒"
      : medianScore >= 35
      ? "博弈均衡·可控"
      : "筹码出清·安全";

  // AI 量化操盘风向速评
  const commentary = useMemo(() => {
    if (!industries || industries.length === 0) {
      return {
        hasData: false,
        text: summary.market_sentiment_label || "正在计算全市场散户与主力博弈特征...",
        extremeNames: "",
        safeNames: "",
      };
    }
    const extremes = industries.filter((i) => i.leek_score >= 70);
    const safes = industries.filter((i) => i.leek_score <= 35);
    const extremeNames = extremes.slice(0, 3).map((i) => i.industry_name).join("、");
    const safeNames = safes.slice(0, 3).map((i) => i.industry_name).join("、");

    return {
      hasData: true,
      text: summary.market_sentiment_label,
      extremeNames,
      safeNames,
    };
  }, [industries, summary.market_sentiment_label]);

  return (
    <div className="leek-cockpit-panel">
      {/* 仪表中枢 */}
      <div className="leek-cockpit-col-gauge">
        <div className="leek-gauge-wrap">
          <svg className="leek-gauge-svg" viewBox="0 0 140 85">
            {/* 灰色底轨 */}
            <path
              d="M 16 70 A 54 54 0 0 1 124 70"
              className="leek-gauge-track"
            />
            {/* 动态彩色弧 */}
            <path
              d="M 16 70 A 54 54 0 0 1 124 70"
              className={`leek-gauge-progress leek-gauge-progress--${riskClass}`}
              strokeDasharray={gaugeCircumference}
              strokeDashoffset={strokeDashoffset}
            />
          </svg>
          <div className="leek-gauge-center">
            <div className="leek-gauge-score">{medianScore.toFixed(1)}</div>
            <div className="leek-gauge-unit">全市场中位分 / 100</div>
            <div className={`leek-gauge-badge leek-gauge-badge--${riskClass}`}>
              {tierBadgeLabel}
            </div>
          </div>
        </div>
        <div className="leek-gauge-ticks">
          <span>💎 35分 出清底</span>
          <span>🔥 75分 接盘顶</span>
        </div>
      </div>

      {/* 31 行业风险梯队全景与 AI 诊断 */}
      <div className="leek-cockpit-col-distribution">
        <div className="leek-cockpit-header-row">
          <div className="leek-cockpit-col-title">
            <span>31 行业风险梯队全景分布</span>
          </div>
          <span className="leek-cockpit-col-subtitle">
            申万一级行业博弈状态实时扫描
          </span>
        </div>

        {/* 梯队堆叠彩条 (SVG，0 内联样式) */}
        <div className="leek-tier-bar-wrap">
          <svg className="leek-tier-bar-svg" viewBox="0 0 100 12" preserveAspectRatio="none">
            <rect
              x={0}
              y={0}
              width={extremePct}
              height={12}
              className="tier-bar-rect--extreme"
            />
            <rect
              x={extremePct}
              y={0}
              width={feverPct}
              height={12}
              className="tier-bar-rect--fever"
            />
            <rect
              x={extremePct + feverPct}
              y={0}
              width={normalPct}
              height={12}
              className="tier-bar-rect--normal"
            />
            <rect
              x={extremePct + feverPct + normalPct}
              y={0}
              width={safePct}
              height={12}
              className="tier-bar-rect--safe"
            />
          </svg>
        </div>

        {/* 梯队图例与行业统计 */}
        <div className="leek-tier-legend">
          <div
            className="leek-tier-item"
            onClick={() => onSelectRiskTier && onSelectRiskTier("extreme")}
          >
            <span className="leek-tier-dot leek-tier-dot--extreme" />
            <span className="leek-tier-name">🔥 极度接盘</span>
            <span className="leek-tier-count">{extremeCount}</span>
            <span className="leek-tier-pct">({extremePct.toFixed(1)}%)</span>
          </div>

          <div
            className="leek-tier-item"
            onClick={() => onSelectRiskTier && onSelectRiskTier("fever")}
          >
            <span className="leek-tier-dot leek-tier-dot--fever" />
            <span className="leek-tier-name">⚠️ 散户过热</span>
            <span className="leek-tier-count">{feverCount}</span>
            <span className="leek-tier-pct">({feverPct.toFixed(1)}%)</span>
          </div>

          <div
            className="leek-tier-item"
            onClick={() => onSelectRiskTier && onSelectRiskTier("normal")}
          >
            <span className="leek-tier-dot leek-tier-dot--normal" />
            <span className="leek-tier-name">⚖️ 筹码均衡</span>
            <span className="leek-tier-count">{normalCount}</span>
            <span className="leek-tier-pct">({normalPct.toFixed(1)}%)</span>
          </div>

          <div
            className="leek-tier-item"
            onClick={() => onSelectRiskTier && onSelectRiskTier("safe")}
          >
            <span className="leek-tier-dot leek-tier-dot--safe" />
            <span className="leek-tier-name">💎 筹码出清</span>
            <span className="leek-tier-count">{safeCount}</span>
            <span className="leek-tier-pct">({safePct.toFixed(1)}%)</span>
          </div>
        </div>

        {/* AI 量化操盘风向诊断 */}
        <div className="leek-cockpit-commentary">
          <span className="leek-cockpit-commentary__title">💡 今日量化操盘风向：</span>
          <span>{commentary.text}。</span>
          {commentary.extremeNames && (
            <span>
              {" "}高危关注[
              <span className="leek-cockpit-commentary__highlight--risk">
                {`【${commentary.extremeNames}板块】`}
              </span>
              ] 主力大单坚决派发、散户小单追高，见顶诱多反杀风险高；
            </span>
          )}
          {commentary.safeNames && (
            <span>
              {" "}安全防御[
              <span className="leek-cockpit-commentary__highlight--safe">
                {`【${commentary.safeNames}板块】`}
              </span>
              ] 筹码出清充分，散户离场，左侧具备高防御性。
            </span>
          )}
        </div>
      </div>

      {/* 右侧多空对冲总敞口 */}
      <div className="leek-cockpit-col-hedging">
        <div className="leek-cockpit-col-title">
          <span>全市场博弈总敞口</span>
        </div>

        <div>
          <div className="leek-hedging-item">
            <span className="leek-hedging-label">主力大单净额</span>
            <span
              className={`leek-hedging-val ${
                totalMainNet >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"
              }`}
            >
              {formatSignedAmount(totalMainNet)}
            </span>
          </div>

          <div className="leek-hedging-item">
            <span className="leek-hedging-label">散户小单净额</span>
            <span
              className={`leek-hedging-val ${
                totalRetailNet >= 0 ? "leek-diff-val--inflow" : "leek-diff-val--outflow"
              }`}
            >
              {formatSignedAmount(totalRetailNet)}
            </span>
          </div>
        </div>

        <div className="leek-hedging-total-card">
          <div className="leek-hedging-total-header">
            <span>资金背离总剪刀差</span>
            <span
              className={`leek-hedging-tag ${
                totalScissors >= 0
                  ? "leek-hedging-tag--divergent"
                  : "leek-hedging-tag--convergent"
              }`}
            >
              {totalScissors >= 0 ? "主力派发·散户接盘" : "主力吸筹·散户离场"}
            </span>
          </div>
          <div className="leek-hedging-total-val">
            {formatSignedAmount(totalScissors)}
          </div>
        </div>
      </div>
    </div>
  );
};
