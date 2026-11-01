import { describe, expect, it, vi } from "vitest";
import {
  COPILOT_OPEN_EVENT,
  openGlobalCopilot,
  triggerStockAiDiagnosis,
} from "./copilotEvents";

describe("copilotEvents", () => {
  it("dispatches custom event with prompt on openGlobalCopilot", () => {
    const handler = vi.fn();
    window.addEventListener(COPILOT_OPEN_EVENT, handler);

    openGlobalCopilot("测试分析 prompt");

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ prompt: "测试分析 prompt", autoSend: false });

    window.removeEventListener(COPILOT_OPEN_EVENT, handler);
  });

  it("triggers diagnosis event when not on /chat page", () => {
    const handler = vi.fn();
    window.addEventListener(COPILOT_OPEN_EVENT, handler);

    triggerStockAiDiagnosis("600519", "贵州茅台");

    expect(handler).toHaveBeenCalledTimes(1);
    const event = handler.mock.calls[0][0] as CustomEvent;
    expect(event.detail.prompt).toContain("贵州茅台");
    expect(event.detail.prompt).toContain("600519");

    window.removeEventListener(COPILOT_OPEN_EVENT, handler);
  });
});
