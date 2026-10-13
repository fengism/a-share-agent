import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EastmoneyRateLimitConfigCard, {
  EASTMONEY_RATE_LIMIT_KEYS,
} from "./EastmoneyRateLimitConfigCard";

function renderCard(overrides: Partial<Parameters<typeof EastmoneyRateLimitConfigCard>[0]> = {}) {
  const onChange = vi.fn();
  const onSave = vi.fn();
  render(
    <EastmoneyRateLimitConfigCard
      form={{
        eastmoney_min_interval_seconds: 1,
        eastmoney_datacenter_min_interval_seconds: 1,
        eastmoney_cooldown_seconds: 120,
        eastmoney_datacenter_cooldown_seconds: 10,
        eastmoney_jitter_min_seconds: 0.1,
        eastmoney_jitter_max_seconds: 0.5,
        eastmoney_transient_failure_threshold: 3,
      }}
      onChange={onChange}
      onSave={onSave}
      isSaving={false}
      {...overrides}
    />,
  );
  return { onChange, onSave };
}

describe("EastmoneyRateLimitConfigCard", () => {
  it("exposes every rate-limit key used by the page for save and revert", () => {
    expect(EASTMONEY_RATE_LIMIT_KEYS).toEqual([
      "eastmoney_min_interval_seconds",
      "eastmoney_datacenter_min_interval_seconds",
      "eastmoney_cooldown_seconds",
      "eastmoney_datacenter_cooldown_seconds",
      "eastmoney_jitter_min_seconds",
      "eastmoney_jitter_max_seconds",
      "eastmoney_transient_failure_threshold",
    ]);
  });

  it("edits the quote request interval", () => {
    const { onChange } = renderCard();

    fireEvent.change(screen.getByLabelText("行情接口请求间隔（秒）"), { target: { value: "2.5" } });
    expect(onChange).toHaveBeenCalledWith({ eastmoney_min_interval_seconds: 2.5 });
  });

  it("edits the quote cooldown duration", () => {
    const { onChange } = renderCard();

    fireEvent.change(screen.getByLabelText("行情接口冷却时长（秒）"), { target: { value: "300" } });
    expect(onChange).toHaveBeenCalledWith({ eastmoney_cooldown_seconds: 300 });
  });

  it("edits the transient failure threshold", () => {
    const { onChange } = renderCard();

    fireEvent.change(screen.getByLabelText("连续失败阈值"), { target: { value: "5" } });
    expect(onChange).toHaveBeenCalledWith({ eastmoney_transient_failure_threshold: 5 });
  });

  it("warns when the jitter upper bound is below the lower bound", () => {
    renderCard({
      form: { eastmoney_jitter_min_seconds: 1.2, eastmoney_jitter_max_seconds: 0.4 },
    });

    expect(
      screen.getByText(/抖动上限（0.4）小于下限（1.2），实际会按下限执行/),
    ).toBeInTheDocument();
  });

  it("has no warning when the jitter range is valid", () => {
    renderCard({
      form: { eastmoney_jitter_min_seconds: 0.1, eastmoney_jitter_max_seconds: 0.5 },
    });

    expect(screen.queryByText(/小于下限/)).not.toBeInTheDocument();
  });

  it("delegates saving", () => {
    const { onSave } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: /保存东财限流配置/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("falls back to backend defaults when the form has no value yet", () => {
    renderCard({ form: {} });

    expect(screen.getByLabelText("行情接口请求间隔（秒）")).toHaveValue("1.0");
    expect(screen.getByLabelText("行情接口冷却时长（秒）")).toHaveValue("120");
    expect(screen.getByLabelText("连续失败阈值")).toHaveValue("3");
  });
});