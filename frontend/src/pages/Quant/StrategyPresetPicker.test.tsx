import { useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { strategyOptions, type QuantFormValues } from "./quantForm";
import StrategyPresetPicker from "./StrategyPresetPicker";

function StrategyPickerHarness() {
  const [value, setValue] = useState<QuantFormValues["strategyType"]>("ma_cross");
  return <StrategyPresetPicker value={value} options={strategyOptions()} onChange={setValue} />;
}

describe("StrategyPresetPicker", () => {
  it("compares presets and exposes radio selection semantics", () => {
    render(<StrategyPickerHarness />);

    expect(screen.getByRole("radiogroup", { name: "预制策略" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("适用行情：趋势行情")).toBeInTheDocument();
    expect(screen.getByText("默认参数：MA 5 / 20")).toBeInTheDocument();

    const rsiPreset = screen.getByRole("radio", { name: /RSI 均值回归/ });
    fireEvent.click(rsiPreset);

    expect(rsiPreset).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("默认参数：RSI 14 · 30 / 70")).toBeInTheDocument();
  });
});
