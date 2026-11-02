import "@testing-library/jest-dom";

const originalGetComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = ((element: Element, pseudoElt?: string | null) => {
  const style = originalGetComputedStyle(element, pseudoElt);
  return new Proxy(style, {
    get(target, prop, receiver) {
      if (prop === "getPropertyValue") {
        return (propertyName: string) => {
          const val = target.getPropertyValue(propertyName);
          if (
            val === "" &&
            (propertyName.startsWith("padding-") ||
              propertyName.startsWith("border-") ||
              propertyName === "border-width" ||
              propertyName === "line-height")
          ) {
            return "0px";
          }
          return val;
        };
      }
      return Reflect.get(target, prop, receiver);
    },
  });
}) as typeof window.getComputedStyle;

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

// Ant Design 5/6 的静态 message / notification 使用 rc-notification 独立根节点与 CSS 动画，
// 其异步通知生命周期在单元测试脱离当前 act 上下文时会向控制台输出无害的 ForwardRef / Notifications 调度告警。
// 这里安全过滤该特定内部告警，保留所有真实业务报错。
const originalConsoleError = console.error.bind(console);
console.error = (...args: unknown[]) => {
  const fullText = args.map((arg) => String(arg ?? "")).join(" ");
  if (
    fullText.includes("not wrapped in act(...)") &&
    (fullText.includes("ForwardRef") || fullText.includes("Notifications"))
  ) {
    return;
  }
  originalConsoleError(...args);
};

// jsdom 未实现 HTMLCanvasElement.prototype.getContext，
// ECharts / zrender 文字测量（measureText）需要使用 2D 上下文。
// 这里提供标准 2D 上下文 polyfill，避免虚拟控制台输出 "Not implemented" 报错。
if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = function (contextId: string) {
    if (contextId === "2d") {
      return {
        fillRect: () => {},
        clearRect: () => {},
        getImageData: (_x: number, _y: number, w: number, h: number) => ({
          data: new Array(w * h * 4),
        }),
        putImageData: () => {},
        createImageData: () => [],
        setTransform: () => {},
        drawImage: () => {},
        save: () => {},
        fillText: () => {},
        restore: () => {},
        beginPath: () => {},
        moveTo: () => {},
        lineTo: () => {},
        closePath: () => {},
        stroke: () => {},
        translate: () => {},
        scale: () => {},
        rotate: () => {},
        arc: () => {},
        fill: () => {},
        measureText: (text: string) => ({
          width: text.length * 10,
          actualBoundingBoxAscent: 10,
          actualBoundingBoxDescent: 2,
        }),
        transform: () => {},
        rect: () => {},
        clip: () => {},
      } as unknown as RenderingContext;
    }
    return null;
  } as typeof HTMLCanvasElement.prototype.getContext;
}
