import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatStreamCallbacks } from "../../api/chat";
import { useChatStore } from "../../store/chatStore";
import { setActiveUserScope } from "../../store/userScope";
import { startChatRuntime, stopChatRuntime } from "./chatRuntime";

const { streamChat } = vi.hoisted(() => ({ streamChat: vi.fn() }));
vi.mock("../../api/chat", () => ({ streamChat }));

describe("chatRuntime", () => {
  beforeEach(() => {
    stopChatRuntime();
    setActiveUserScope(null);
    setActiveUserScope(1);
    streamChat.mockReset();
  });

  it("keeps the stream outside a page component and finalizes on global stop", () => {
    const controller = new AbortController();
    const abort = vi.spyOn(controller, "abort");
    streamChat.mockReturnValue(controller);
    expect(startChatRuntime({ input: "分析贵州茅台", history: [] })).toBe(true);
    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().activeRunLabel).toBe("分析贵州茅台");

    expect(stopChatRuntime()).toBe(true);
    expect(abort).toHaveBeenCalledOnce();
    expect(useChatStore.getState().isStreaming).toBe(false);
    const messages = useChatStore.getState().messages;
    expect(messages[messages.length - 1]?.isStreaming).toBe(false);
  });

  it("keeps receiving deltas after the caller that started it is gone", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });

    expect(startChatRuntime({ input: "第一次", history: [] })).toBe(true);
    callbacks?.onDelta({ type: "text", content: "后台完成" });
    callbacks?.onDone();

    const messages = useChatStore.getState().messages;
    expect(messages[messages.length - 1]?.content).toBe("后台完成");
    expect(messages[messages.length - 1]?.isStreaming).toBe(false);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("ignores a second start while another chat run is active", () => {
    streamChat.mockReturnValue(new AbortController());

    expect(startChatRuntime({ input: "第一次", history: [] })).toBe(true);
    expect(startChatRuntime({ input: "第二次", history: [] })).toBe(false);
    expect(streamChat).toHaveBeenCalledOnce();
  });
});
