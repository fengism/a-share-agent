import { act, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useContainerWidth } from "./useContainerWidth";

/** 记录被 observe 的元素，便于手动触发 ResizeObserver 回调。 */
function installResizeObserver() {
  const observed: Element[] = [];
  const callbacks = new Map<Element, () => void>();
  class FakeResizeObserver {
    constructor(private cb: () => void) {}
    observe(target: Element) {
      observed.push(target);
      callbacks.set(target, this.cb);
    }
    unobserve(target: Element) {
      callbacks.delete(target);
    }
    disconnect() {
      observed.forEach((el) => callbacks.delete(el));
    }
  }
  vi.stubGlobal("ResizeObserver", FakeResizeObserver);
  return {
    observed,
    trigger: (target: Element) => act(() => callbacks.get(target)?.()),
  };
}

function setClientWidth(node: Element, width: number) {
  Object.defineProperty(node, "clientWidth", { value: width, configurable: true });
}

function Probe({ onWidth, attached = true }: { onWidth: (w: number) => void; attached?: boolean }) {
  const [ref, width] = useContainerWidth<HTMLDivElement>();
  onWidth(width);
  return attached ? <div ref={ref} data-testid="target" /> : <div data-testid="target" />;
}

describe("useContainerWidth", () => {
  it("reports the measured container width and updates on resize", () => {
    const ro = installResizeObserver();
    const seen: number[] = [];
    const { getByTestId } = render(<Probe onWidth={(w) => seen.push(w)} />);
    const target = getByTestId("target");

    // jsdom 的 clientWidth 默认为 0，首帧按 0 上报
    expect(seen.at(-1)).toBe(0);
    expect(ro.observed).toContain(target);

    // 容器拿到真实宽度后应立即上报（无需等下一帧）
    setClientWidth(target, 406);
    ro.trigger(target);
    expect(seen.at(-1)).toBe(406);

    setClientWidth(target, 900);
    ro.trigger(target);
    expect(seen.at(-1)).toBe(900);
    vi.unstubAllGlobals();
  });

  it("keeps the same state value when the width does not actually change", () => {
    const ro = installResizeObserver();
    const seen: number[] = [];
    const { getByTestId, rerender } = render(<Probe onWidth={(w) => seen.push(w)} />);
    const target = getByTestId("target");

    setClientWidth(target, 640);
    ro.trigger(target);
    const callsAfterFirst = seen.length;

    // 宽度没变时不应产生新的 state 更新（避免无意义重渲染）
    ro.trigger(target);
    expect(seen.length).toBe(callsAfterFirst);
    expect(seen.at(-1)).toBe(640);
    rerender(<Probe onWidth={(w) => seen.push(w)} />);
    vi.unstubAllGlobals();
  });

  it("resets to 0 when the node is detached", () => {
    const ro = installResizeObserver();
    const seen: number[] = [];
    const { getByTestId, rerender } = render(<Probe onWidth={(w) => seen.push(w)} />);
    setClientWidth(getByTestId("target"), 800);
    ro.trigger(getByTestId("target"));
    expect(seen.at(-1)).toBe(800);

    // 组件不再把 ref 挂到任何节点（ref 回调收到 null）时应回到 0
    rerender(<Probe onWidth={(w) => seen.push(w)} attached={false} />);
    expect(seen.at(-1)).toBe(0);
    vi.unstubAllGlobals();
  });
});