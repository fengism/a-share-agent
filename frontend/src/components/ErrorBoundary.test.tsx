import { fireEvent, render, screen } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

let shouldThrow = true;

function ThrowOnce({ children }: { children: ReactNode }) {
  if (shouldThrow) {
    throw new Error("测试错误");
  }
  return children;
}

describe("ErrorBoundary", () => {
  const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);

  beforeEach(() => {
    shouldThrow = true;
  });

  afterEach(() => consoleError.mockClear());

  it("shows a lightweight alert and retries the failed subtree", () => {
    render(
      <ErrorBoundary>
        <ThrowOnce><div>恢复成功</div></ThrowOnce>
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("测试错误");
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(screen.getByText("恢复成功")).toBeInTheDocument();
  });

  it("remounts the subtree on retry so broken child state cannot survive", () => {
    // 只清 hasError 而不换 key 时，React 会复用同一个子组件实例，它的
    // state 仍停在崩溃现场（这里 broken=true），点重试会立刻再崩。
    // 换 key 强制重新挂载后，子组件从初始 state 重建，不再崩溃。
    function Fragile() {
      const [broken, setBroken] = useState(false);
      if (broken) {
        throw new Error("子组件状态已损坏");
      }
      return (
        <button type="button" onClick={() => setBroken(true)}>
          触发崩溃
        </button>
      );
    }

    render(
      <ErrorBoundary>
        <Fragile />
      </ErrorBoundary>,
    );

    fireEvent.click(screen.getByRole("button", { name: "触发崩溃" }));
    expect(screen.getByRole("alert")).toHaveTextContent("子组件状态已损坏");

    fireEvent.click(screen.getByRole("button", { name: "重试" }));

    // 重新挂载：broken 回到 false，页面恢复可用。
    expect(screen.getByRole("button", { name: "触发崩溃" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

