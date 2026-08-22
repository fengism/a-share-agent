import { MessageOutlined, RiseOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { AnalysisResult } from "../../types/stock";
import { getAnalysisFollowUps, getConditionalAction } from "./analysisDecision";

export default function AnalysisDecisionBoard({ result }: { result: AnalysisResult }) {
  const navigate = useNavigate();
  const action = getConditionalAction(result.signal);
  const prompts = getAnalysisFollowUps(result);
  const support = result.technical.support_level;
  const resistance = result.technical.resistance_level;
  const current = result.current_price;

  return (
    <section className="analysis-decision-board u-card" aria-label="决策重点与 AI 追问">
      <div className="analysis-decision-board__action">
        <span><RiseOutlined /> 操作建议</span>
        <strong className={`is-${action.tone}`}>{action.label}</strong>
        <p>{action.detail}</p>
      </div>
      <div className="analysis-levels" aria-label="关键交易点位">
        <div><span>关键支撑</span><strong>{support?.toFixed(2) ?? "-"}</strong><small>跌破后重新检查趋势</small></div>
        <div><span>当前价格</span><strong>{current?.toFixed(2) ?? "-"}</strong><small>以最新分析快照为准</small></div>
        <div><span>关键压力</span><strong>{resistance?.toFixed(2) ?? "-"}</strong><small>突破后观察量价确认</small></div>
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
