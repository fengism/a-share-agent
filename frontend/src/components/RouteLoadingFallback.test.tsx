import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import RouteLoadingFallback from "./RouteLoadingFallback";

describe("RouteLoadingFallback", () => {
  it("announces route loading accessibly", () => {
    render(<RouteLoadingFallback />);

    expect(screen.getByRole("status")).toHaveTextContent("正在加载页面");
    expect(screen.getByText("首次打开后，后续切换会更快")).toBeInTheDocument();
  });
});
