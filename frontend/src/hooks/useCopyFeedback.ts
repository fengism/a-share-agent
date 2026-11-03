import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 复制反馈状态：`copied` 置真后延迟自动复位，并保证计时器随组件卸载清理。
 *
 * 直接写 `setTimeout(() => setCopied(false), 2000)` 的问题：
 * - 组件在计时器到点前卸载，回调仍会执行并 setState（React 18 起不再告警，
 *   但属于在已卸载组件上做无意义工作，且重复点击会堆叠多个未取消的计时器）；
 * - 先前的计时器不会被新的一次点击取代，导致反馈时长不稳定。
 */
export function useCopyFeedback(durationMs = 2000) {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<number | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const markCopied = useCallback(() => {
    setCopied(true);
    clearTimer();
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      setCopied(false);
    }, durationMs);
  }, [clearTimer, durationMs]);

  const resetCopied = useCallback(() => {
    clearTimer();
    setCopied(false);
  }, [clearTimer]);

  useEffect(() => clearTimer, [clearTimer]);

  return { copied, markCopied, resetCopied };
}
