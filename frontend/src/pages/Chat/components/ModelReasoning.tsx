import { memo, useEffect, useMemo, useRef } from "react";

import type { ReasoningBlock } from "../../../types/chat";
import { sanitizeReasoningBlocks } from "../../../store/chatMessageGuards";

/** Render only provider-returned text, never HTML or reconstructed reasoning. */
export const ModelReasoning = memo(function ModelReasoning({
  content,
  blocks,
  isStreaming,
}: {
  content: string;
  blocks?: ReasoningBlock[];
  isStreaming: boolean;
}) {
  const sections = useMemo(() => {
    const valid = sanitizeReasoningBlocks(blocks, content) ?? [];
    const result: { key: string; label?: string; text: string }[] = [];
    let cursor = 0;
    for (const block of valid) {
      if (block.start > cursor) result.push({ key: `legacy-${cursor}`, text: content.slice(cursor, block.start) });
      result.push({ key: `${block.block_id}-${block.start}`,
        label: `${block.source} · 第 ${block.turn} 轮${block.attempt > 1 ? ` · 第 ${block.attempt} 次尝试` : ""}${block.task_id ? ` · ${block.task_id}` : ""}`,
        text: content.slice(block.start, block.end) });
      cursor = block.end;
    }
    if (cursor < content.length) result.push({ key: `legacy-${cursor}`, text: content.slice(cursor) });
    return result;
  }, [content, blocks]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const followTailRef = useRef(true);
  useEffect(() => {
    if (isStreaming && followTailRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [content, isStreaming]);

  return (
    <section className="chat-model-reasoning" aria-label="模型推理">
      <div className="chat-process-step-title">模型推理</div>
      <div
        ref={scrollRef}
        className="chat-model-reasoning-content"
        tabIndex={0}
        aria-label="模型返回的推理内容，可滚动查看"
        onScroll={(event) => {
          const { scrollHeight, scrollTop, clientHeight } = event.currentTarget;
          followTailRef.current = scrollHeight - scrollTop - clientHeight < 32;
        }}
      >{sections.map((section) => (
        <div key={section.key} className="chat-reasoning-block">
          {section.label && <div className="chat-process-step-title">{section.label}</div>}
          <div>{section.text}</div>
        </div>
      ))}</div>
    </section>
  );
});
