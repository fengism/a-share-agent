import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LazyChart from "./LazyChart";

describe("NationalTeam LazyChart", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("jsdom 没有 IntersectionObserver 时直接渲染子节点", () => {
    render(
      <LazyChart height={200}>
        <div data-testid="chart">chart</div>
      </LazyChart>,
    );

    expect(screen.getByTestId("chart")).toBeInTheDocument();
  });

  it("进入视口前只渲染占位，且支持用类名控制高度", () => {
    const observe = vi.fn();
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        observe = observe;
        unobserve = vi.fn();
        disconnect = vi.fn();
        takeRecords = () => [];
        root = null;
        rootMargin = "";
        thresholds = [];
      },
    );

    const { container } = render(
      <LazyChart height={340} placeholderClassName="placeholder">
        <div data-testid="chart">chart</div>
      </LazyChart>,
    );

    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
    expect(container.querySelector(".placeholder")).toBeInTheDocument();
    expect(observe).toHaveBeenCalled();
  });
});
