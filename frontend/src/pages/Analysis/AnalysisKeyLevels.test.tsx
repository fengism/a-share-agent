import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AnalysisKeyLevels from "./AnalysisKeyLevels";

describe("AnalysisKeyLevels", () => {
  it("renders deterministic levels without an AI analysis result", () => {
    render(<AnalysisKeyLevels current={1520} support={1450} resistance={1650} />);

    expect(screen.getByLabelText("关键点位")).toBeInTheDocument();
    expect(screen.queryByText(/无需 AI 研究/)).not.toBeInTheDocument();
    expect(screen.getByText("1450.00")).toBeInTheDocument();
    expect(screen.getByText("1520.00")).toBeInTheDocument();
    expect(screen.getByText("1650.00")).toBeInTheDocument();
    expect(screen.getByText("距支撑 +4.8%")).toBeInTheDocument();
    expect(screen.getByText("距压力 -7.9%")).toBeInTheDocument();
    expect(screen.getByText("区间运行")).toBeInTheDocument();
  });

  it("labels snapshot prices separately from live quotes", () => {
    render(<AnalysisKeyLevels current={1520} support={1450} resistance={1650} currentLabel="分析时价格" />);

    expect(screen.getByText("分析时价格")).toBeInTheDocument();
    expect(screen.queryByText("当前价")).not.toBeInTheDocument();
  });

  it("keeps the section visible while market data is unavailable", () => {
    render(<AnalysisKeyLevels current={null} support={null} resistance={null} />);

    expect(screen.getByLabelText("关键点位")).toBeInTheDocument();
    expect(screen.getByText("数据待补充")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("关键点位数据不足");
  });
});
