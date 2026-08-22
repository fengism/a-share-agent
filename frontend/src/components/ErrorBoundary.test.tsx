import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
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
});
