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
