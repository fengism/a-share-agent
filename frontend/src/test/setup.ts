import "@testing-library/jest-dom";

const getComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = ((element: Element) => getComputedStyle(element)) as typeof window.getComputedStyle;

// jsdom lacks a few browser APIs that Ant Design components probe for.
// Provide inert polyfills so component tests can render.
if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

if (!("ResizeObserver" in globalThis)) {
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// react-router 的 data router 在每次导航时都会构造 Request（即使没有 loader），
// 而 Node 的 undici Request 不接受 jsdom 的 AbortSignal 实例，导致导航直接失败。
// 这里在测试环境中丢弃 signal（测试不使用 loader）以保持导航可执行。
{
  const OriginalRequest = globalThis.Request;
  if (typeof OriginalRequest === "function") {
    class TestRequest extends OriginalRequest {
      constructor(input: RequestInfo | URL, init?: RequestInit) {
        super(input, init ? { ...init, signal: undefined } : init);
      }
    }
    globalThis.Request = TestRequest as typeof globalThis.Request;
  }
}

// jsdom 的 window.scrollTo 只会在虚拟控制台报 "Not implemented"，
// 这里提供惰性实现，避免每个涉及滚动定位的用例都单独 stub。
// 需要断言滚动的用例可用 vi.stubGlobal("scrollTo", vi.fn()) 覆盖。
if (typeof window.scrollTo === "function" && !("__scrollToPatched" in window)) {
  Object.defineProperty(window, "__scrollToPatched", { value: true });
  window.scrollTo = () => {};
}

// Ant Design 的静态 message / notification 会脱离当前测试的 React 根节点并在 document.body 创建独立 DOM/root，
// 其异步动画和定时器在测试结束后会触发 React "not wrapped in act(...)" 警告。
// 在测试环境中提供安全的空实现，避免污染 stderr 或引起测试间状态泄露。
import { message, notification } from "antd";
import { vi } from "vitest";

const createNoticeStub = () => {
  const fn = () => {};
  fn.then = (resolve?: (val: boolean) => unknown) => Promise.resolve(true).then(resolve);
  return fn;
};

const messageTarget = message as unknown as Record<string, unknown>;
for (const method of ["open", "success", "info", "warning", "error", "loading"] as const) {
  messageTarget[method] = vi.fn(createNoticeStub);
}
messageTarget.destroy = vi.fn();

const notificationTarget = notification as unknown as Record<string, unknown>;
for (const method of ["open", "success", "info", "warning", "error"] as const) {
  notificationTarget[method] = vi.fn(createNoticeStub);
}
notificationTarget.destroy = vi.fn();
