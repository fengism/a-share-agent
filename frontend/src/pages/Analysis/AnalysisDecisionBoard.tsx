import { MessageOutlined, RiseOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { AnalysisResult } from "../../types/stock";
import { getAnalysisFollowUps, getConditionalAction } from "./analysisDecision";

const NEW_INVESTOR_ACTIONS = {
  buy: { label: "考虑买入", tone: "positive" },
  watch: { label: "继续观察", tone: "neutral" },
  avoid: { label: "暂时回避", tone: "negative" },
  insufficient_evidence: { label: "证据不足", tone: "neutral" },
} as const;

const HOLDER_ACTIONS = {
  hold: "继续持有",
  add: "考虑增持",
  reduce: "考虑减持",
  exit: "考虑退出",
  insufficient_evidence: "证据不足",
} as const;

export default function AnalysisDecisionBoard({
  result,
  embedded = false,
}: {
  result: AnalysisResult;
  embedded?: boolean;
}) {
  const navigate = useNavigate();
  const legacyAction = getConditionalAction(result.signal);
  const researchActions = result.research_framework?.actions;
  const structuredAction = researchActions ? NEW_INVESTOR_ACTIONS[researchActions.new_investor_action] : null;
  const action = structuredAction ?? legacyAction;
  const prompts = getAnalysisFollowUps(result);
  const support = result.technical.support_level;
  const resistance = result.technical.resistance_level;
  const current = result.current_price;

  return (
    <section
      className={`analysis-decision-board${embedded ? " analysis-decision-board--embedded" : " u-card"}`}
      data-pdf-capture
      aria-label="决策重点与 AI 追问"
    >
      <div className="analysis-decision-board__action">
        <span><RiseOutlined /> {researchActions ? "新投资者建议" : "操作建议"}</span>
        <strong className={`is-${action.tone}`}>{action.label}</strong>
        <p>{researchActions?.rationale || legacyAction.detail}</p>
        {researchActions ? (
          <p className="analysis-decision-board__holder">
            已持有者：<strong>{HOLDER_ACTIONS[researchActions.holder_action]}</strong>
            {researchActions.thesis_breakers[0] ? `；首要失效条件：${researchActions.thesis_breakers[0]}` : ""}
          </p>
        ) : null}
      </div>
      <div className="analysis-levels" aria-label="短期择时参考">
        <div><span>短期支撑</span><strong>{support?.toFixed(2) ?? "-"}</strong><small>跌破后重新检查趋势</small></div>
        <div><span>当前价格</span><strong>{current?.toFixed(2) ?? "-"}</strong><small>以最新分析快照为准</small></div>
        <div><span>短期压力</span><strong>{resistance?.toFixed(2) ?? "-"}</strong><small>突破后观察量价确认</small></div>
      </div>
      <div className="analysis-follow-ups">
        <span className="analysis-follow-ups__label"><MessageOutlined /> 追问 AI</span>
        <div>
          {prompts.map((prompt) => (
            <button
              type="button"
              key={prompt}
              onClick={() => navigate(`/chat?prompt=${encodeURIComponent(prompt)}`)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
