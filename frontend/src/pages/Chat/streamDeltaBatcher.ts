import type { ReasoningSource } from "../../types/chat";

export interface StreamDeltaBatch {
  text: string;
  reasoning: string;
  reasoningSource?: ReasoningSource;
}

type ScheduleFlush = (callback: () => void) => number;
type CancelFlush = (handle: number) => void;

export interface StreamDeltaBatcher {
  enqueueText: (text: string) => void;
  enqueueReasoning: (text: string, source?: ReasoningSource | null) => void;
  flush: () => void;
  clear: () => void;
}

export function createStreamDeltaBatcher(
  onFlush: (batch: StreamDeltaBatch) => void,
  scheduleFlush: ScheduleFlush = (callback) => window.requestAnimationFrame(callback),
  cancelFlush: CancelFlush = (handle) => window.cancelAnimationFrame(handle),
): StreamDeltaBatcher {
  let pendingText = "";
  let pendingReasoning = "";
  let pendingSource: ReasoningSource | undefined;
  let scheduledHandle: number | null = null;

  const emit = () => {
    if (!pendingText && !pendingReasoning) return;
    const batch = { text: pendingText, reasoning: pendingReasoning, ...(pendingSource ? { reasoningSource: pendingSource } : {}) };
    pendingText = "";
    pendingReasoning = "";
    pendingSource = undefined;
    onFlush(batch);
  };

  const schedule = () => {
    if (scheduledHandle !== null) return;
    scheduledHandle = scheduleFlush(() => {
      scheduledHandle = null;
      emit();
    });
  };

  const flush = () => {
    if (scheduledHandle !== null) {
      cancelFlush(scheduledHandle);
      scheduledHandle = null;
    }
    emit();
  };

  return {
    enqueueText: (text) => {
      if (!text) return;
      pendingText += text;
      schedule();
    },
    enqueueReasoning: (text, source) => {
      if (!text) return;
      if (pendingReasoning && pendingSource?.block_id !== source?.block_id) flush();
      pendingSource = source ?? undefined;
      pendingReasoning += text;
      schedule();
    },
    flush,
    clear: () => {
      if (scheduledHandle !== null) cancelFlush(scheduledHandle);
      scheduledHandle = null;
      pendingText = "";
      pendingReasoning = "";
      pendingSource = undefined;
    },
  };
}
