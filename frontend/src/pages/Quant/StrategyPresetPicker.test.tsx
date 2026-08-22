import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { strategyOptions, type QuantFormValues } from "./quantForm";
import StrategyPresetPicker from "./StrategyPresetPicker";

function StrategyPickerHarness() {
  const [value, setValue] = useState<QuantFormValues["strategyType"]>("ma_cross");
  return (
    <StrategyPresetPicker
      value={value}
      options={strategyOptions()}
      parameterValues={value === "ma_cross" ? { fast_period: 5, slow_period: 30 } : undefined}
      onChange={setValue}
    />
  );
}

describe("StrategyPresetPicker", () => {
  it("compares presets and exposes radio selection semantics", () => {
    render(<StrategyPickerHarness />);

    expect(screen.getByText("当前策略：双均线趋势")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup", { name: "预制策略" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "更换策略" }));
    expect(screen.getByRole("radiogroup", { name: "预制策略" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("适用行情：趋势行情")).toBeInTheDocument();
    expect(screen.getByText("实际参数：短均线 5 · 长均线 30")).toBeInTheDocument();
    expect(screen.getByText("已修改")).toBeInTheDocument();
    expect(screen.getByText("默认参数：短均线 5 · 长均线 20")).toBeInTheDocument();
    expect(screen.getAllByText("版本：1.0.0")).toHaveLength(3);

    const rsiPreset = screen.getByRole("radio", { name: /RSI 均值回归/ });
    fireEvent.click(rsiPreset);

    expect(screen.queryByRole("radiogroup", { name: "预制策略" })).not.toBeInTheDocument();
    expect(screen.getByText("当前策略：RSI 均值回归")).toBeInTheDocument();
    expect(screen.getByText("实际参数：RSI 周期 14 · 买入阈值 30 · 卖出阈值 70")).toBeInTheDocument();
  });

  it("filters presets while keeping the selected strategy visible", async () => {
    render(<StrategyPickerHarness />);

    fireEvent.click(screen.getByRole("button", { name: "更换策略" }));
    fireEvent.change(screen.getByRole("textbox", { name: "搜索预制策略" }), { target: { value: "RSI" } });

    expect(screen.getByText("匹配 1/3")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /双均线趋势/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /RSI 均值回归/ })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /动量突破/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: /RSI 均值回归/ }));
    fireEvent.click(screen.getByRole("button", { name: "更换策略" }));
    fireEvent.change(screen.getByRole("textbox", { name: "搜索预制策略" }), { target: { value: "" } });
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "策略风险" }));
    fireEvent.click(await screen.findByText("较高风险"));

    expect(screen.getByRole("radio", { name: /RSI 均值回归/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /动量突破/ })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: /双均线趋势/ })).not.toBeInTheDocument();
  });

});
