import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../api/queryHooks/market", () => ({
  useUsMacroData: () => ({
    data: {
      indicators: {},
      refreshing: true,
      failed_indicators: { cpi: "temporary" },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

import UsMacroTab from "./UsMacroTab";

describe("UsMacroTab", () => {
  it("shows background refresh and partial failure state", () => {
    render(<UsMacroTab />);

    expect(screen.getByText(/正在后台刷新美国宏观数据/)).toBeInTheDocument();
    expect(screen.getByText(/部分指标刷新失败：cpi/)).toBeInTheDocument();
    expect(screen.queryByText("美国核心 PCE")).not.toBeInTheDocument();
  });
});
