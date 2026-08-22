import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LazyKlineChart from "./LazyKlineChart";

vi.mock("./KlineChart", () => ({
  default: () => <div>已加载K线图</div>,
}));

describe("LazyKlineChart", () => {
  const originalIntersectionObserver = globalThis.IntersectionObserver;

  afterEach(() => {
    globalThis.IntersectionObserver = originalIntersectionObserver;
  });

  it("loads the chart only when its container approaches the viewport", async () => {
    let notify: IntersectionObserverCallback | undefined;
    globalThis.IntersectionObserver = class {
      readonly root = null;
      readonly rootMargin = "240px 0px";
      readonly thresholds = [0];
      constructor(callback: IntersectionObserverCallback) {
        notify = callback;
      }
      disconnect() {}
      observe() {}
      takeRecords() { return []; }
      unobserve() {}
    };

    render(<LazyKlineChart data={[]} height={420} />);

    expect(screen.getByLabelText("K线图即将加载")).toBeInTheDocument();
    expect(screen.queryByText("已加载K线图")).not.toBeInTheDocument();

    await act(async () => {
      notify?.([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
      await Promise.resolve();
    });

    expect(await screen.findByText("已加载K线图")).toBeInTheDocument();
  });
});
