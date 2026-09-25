import { memo, useEffect, useRef } from "react";
import { CheckCircleOutlined, ClockCircleOutlined, LoadingOutlined, StopOutlined, CloseCircleOutlined, WarningOutlined } from "@ant-design/icons";
import type { ChatProcessUpdate } from "../../../types/chat";

function SummaryList({ label, values }: { label: string; values: string[] }) {
  if (!values.length) return null;
  return <div><strong>{label}</strong><ul>{values.map((value, index) => <li key={index}>{value}</li>)}</ul></div>;
}

export const ChatProcessTimeline = memo(function ChatProcessTimeline({
  updates,
  isStreaming,
}: {
  updates: ChatProcessUpdate[];
  isStreaming: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const followTailRef = useRef(true);
  useEffect(() => {
    if (followTailRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [updates]);

  if (!updates.length) return null;
  return (
    <div className="chat-process-timeline" aria-label="思考过程记录">
      <div className="chat-process-timeline-label">执行进度与调研摘要</div>
      <div
        ref={scrollRef}
        className="chat-process-timeline-scroll"
        tabIndex={0}
        aria-label="过程记录，可滚动查看"
        onScroll={(event) => {
          const { scrollTop, clientHeight, scrollHeight } = event.currentTarget;
          followTailRef.current = scrollHeight - scrollTop - clientHeight < 32;
        }}
      >
        {updates.map((update, index) => {
          if (update.type === "status") {
            const active = isStreaming && index === updates.length - 1;
            return (
              <div className="chat-process-step" key={index}>
                <span className={`chat-process-step-icon${active ? " is-running" : ""}`} aria-hidden="true">
                  {active ? <LoadingOutlined spin /> : <ClockCircleOutlined />}
                </span>
                <div className="chat-process-step-content chat-process-step-description">{update.content}</div>
              </div>
            );
          }
          const round = update.round;
          const running = round.status === "running";
          const degraded = round.status === "degraded";
          const cancelled = round.status === "cancelled" || (running && !isStreaming);
          const failed = round.status === "failed";
          const label = cancelled ? "已停止" : failed ? "执行失败" : running ? "调研中" : degraded ? "证据不足" : "已完成";
          return (
            <div className="chat-process-step" key={index}>
              <span className="chat-process-step-icon is-plan" aria-hidden="true">
                {running && isStreaming ? <LoadingOutlined spin /> : cancelled ? <StopOutlined /> : failed ? <CloseCircleOutlined /> : degraded ? <WarningOutlined /> : <CheckCircleOutlined />}
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title chat-plan-step-title">
                  <span>第 {round.round_index}/{round.round_total} 轮调研</span>
                  <span className={`chat-plan-step-status is-${running ? (isStreaming ? "running" : "cancelled") : round.status}`}>{label}</span>
                </div>
                <div className="chat-process-round-summary">
                  {round.objective && <div><strong>本轮目标</strong><p>{round.objective}</p></div>}
                  <SummaryList label="待补证据" values={round.evidence_gaps} />
                  {round.tool_selection_reason && <div><strong>工具选择依据</strong><p>{round.tool_selection_reason}</p></div>}
                  <SummaryList label="新增证据" values={round.evidence_added} />
                  <SummaryList label="判断依据" values={round.judgment_basis} />
                  {round.conclusion && <div><strong>阶段结论</strong><p>{round.conclusion}</p></div>}
                  {round.next_step && <div><strong>下一步</strong><p>{round.next_step}</p></div>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});
