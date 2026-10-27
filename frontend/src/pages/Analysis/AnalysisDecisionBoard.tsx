import { useState } from "react";
import { AlertOutlined, CheckOutlined, CopyOutlined, MessageOutlined, RiseOutlined } from "@ant-design/icons";
import { Button, message } from "antd";
import { useNavigate } from "react-router-dom";
import { renderWithCitations } from "../../features/investment-research/citationRendering";
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
  const [copied, setCopied] = useState(false);
  const legacyAction = getConditionalAction(result.signal);
  const researchActions = result.research_framework?.actions;
  const structuredAction = researchActions ? NEW_INVESTOR_ACTIONS[researchActions.new_investor_action] : null;
  const action = structuredAction ?? legacyAction;
  const prompts = getAnalysisFollowUps(result);

  const handleCopySummary = async () => {
    const rawRationale = (researchActions?.rationale || legacyAction.detail || "").replace(/\[\^[^\]]+\]/g, "").trim();
    const breakers = researchActions?.thesis_breakers?.length
      ? `\n【风控证伪条件】\n${researchActions.thesis_breakers.map((b, i) => `${i + 1}. ${b.replace(/\[\^[^\]]+\]/g, "")}`).join("\n")}`
      : "";
    const memo = `【标的】${result.stock_name || ""} (${result.stock_code})
【建议】${action.label}
【研判逻辑】${rawRationale}${breakers}`;

    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(memo);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = memo;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      setCopied(true);
      message.success("已复制投资备忘至剪贴板");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      message.error("复制失败，请手动选取复制");
    }
  };

  return (
    <section
      className={`analysis-decision-board${embedded ? " analysis-decision-board--embedded" : " u-card"}`}
      data-pdf-capture
      aria-label="决策重点与 AI 追问"
    >
      <div className="analysis-decision-board__action">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gridColumn: "1 / -1" }}>
          <span><RiseOutlined /> {researchActions ? "新投资者建议" : "操作建议"}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong className={`is-${action.tone}`}>{action.label}</strong>
            <Button
              type="text"
              size="small"
              icon={copied ? <CheckOutlined style={{ color: "var(--c-success)" }} /> : <CopyOutlined />}
              className="pdf-hide"
              style={{ fontSize: 12, padding: "0 6px", height: 22, color: "var(--c-text-secondary)" }}
              onClick={handleCopySummary}
              title="复制决策备忘"
              aria-label="复制投资备忘"
            >
              {copied ? "已复制" : "复制备忘"}
            </Button>
          </div>
        </div>
        <p>{renderWithCitations(researchActions?.rationale || legacyAction.detail)}</p>
        {researchActions ? (
          <>
            <p className="analysis-decision-board__holder">
              已持有者：<strong>{HOLDER_ACTIONS[researchActions.holder_action]}</strong>
              {researchActions.thesis_breakers[0] ? `；首要失效条件：${researchActions.thesis_breakers[0]}` : ""}
            </p>
            {researchActions.thesis_breakers.length > 1 ? (
              <div className="analysis-decision-board__breaker-card">
                <div className="analysis-decision-board__breaker-title">
                  <AlertOutlined /> 风控警戒线（逻辑证伪条件）：
                </div>
                <ul className="analysis-decision-board__breaker-list">
                  {researchActions.thesis_breakers.map((breaker, idx) => (
                    <li key={`breaker-${idx}`}>{renderWithCitations(breaker)}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
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
