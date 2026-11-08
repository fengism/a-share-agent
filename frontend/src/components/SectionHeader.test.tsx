import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SectionHeader from "./SectionHeader";

describe("SectionHeader", () => {
  it("renders basic title and icon", () => {
    render(
      <SectionHeader
        title="今日主线题材"
        icon={<span data-testid="test-icon">⚡</span>}
      />,
    );

    expect(screen.getByRole("heading", { level: 3, name: "今日主线题材" })).toBeInTheDocument();
    expect(screen.getByTestId("test-icon")).toBeInTheDocument();
  });

  it("renders subtitle, badge and actions", () => {
    render(
      <SectionHeader
        title="市场风向标"
        subtitle="按申万一级行业统计资金与热度"
        badge={<span>实时</span>}
        actions={<button type="button">刷新</button>}
      />,
    );

    expect(screen.getByText("市场风向标")).toBeInTheDocument();
    expect(screen.getByText("按申万一级行业统计资金与热度")).toBeInTheDocument();
    expect(screen.getByText("实时")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新" })).toBeInTheDocument();
  });

  it("supports extra prop as an alias for actions", () => {
    render(
      <SectionHeader
        title="龙头股连板梯队"
        extra={<span>共 12 家</span>}
      />,
    );

    expect(screen.getByText("共 12 家")).toBeInTheDocument();
  });
});
