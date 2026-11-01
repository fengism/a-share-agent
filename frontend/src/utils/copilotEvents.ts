export const COPILOT_OPEN_EVENT = "a-share:open-copilot";

export interface CopilotOpenDetail {
  prompt?: string;
  autoSend?: boolean;
}

export function openGlobalCopilot(prompt?: string, autoSend = false): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<CopilotOpenDetail>(COPILOT_OPEN_EVENT, {
        detail: { prompt, autoSend },
      }),
    );
  }
}

export function triggerStockAiDiagnosis(
  code: string,
  name?: string,
  navigate?: (url: string) => void,
): void {
  const stockLabel = name ? `${name} (${code})` : code;
  const prompt = `请对股票【${stockLabel}】进行深度投研诊断：
1. 技术形态诊断：当前均线结构、量价配合、顶底背离与筹码集中度；
2. 关键价位分析：短线核心支撑位与上方强压力位；
3. 资金动向与资金流特征；
4. 明确的操作策略建议（分短线博弈与波段策略）。`;

  if (typeof window !== "undefined" && window.location.pathname.startsWith("/chat")) {
    if (navigate) {
      navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
    } else {
      window.location.href = `/chat?prompt=${encodeURIComponent(prompt)}`;
    }
    return;
  }

  openGlobalCopilot(prompt);
}
