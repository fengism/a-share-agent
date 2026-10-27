import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import BacktestParameterSensitivity from "./BacktestParameterSensitivity";
import * as quantHooks from "../../../api/queryHooks/quant";

vi.mock("../../../hooks/useMediaQuery", () => ({ useMediaQuery: () => true }));

function renderComponent(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("BacktestParameterSensitivity", () => {
  it("renders strategy parameters and triggers grid scan mutation", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({
      param1_name: "fast_period",
      param1_values: [5, 10],
      param2_name: "slow_period",
      param2_values: [20, 30],
      points: [
        {
          param1_value: 5,
          param2_value: 20,
          sharpe_ratio: 1.45,
          total_return: 28.5,
          annualized_return: 18.2,
          max_drawdown: -8.5,
          win_rate: 65,
        },
        {
          param1_value: 10,
          param2_value: 30,
          sharpe_ratio: 0.95,
          total_return: 14.2,
          annualized_return: 10.1,
          max_drawdown: -12.3,
          win_rate: 55,
        },
      ],
      optimal_point: {
        param1_value: 5,
        param2_value: 20,
        sharpe_ratio: 1.45,
        total_return: 28.5,
        annualized_return: 18.2,
        max_drawdown: -8.5,
        win_rate: 65,
      },
      robustness_score: 82.5,
      profitable_ratio: 100,
    });

    vi.spyOn(quantHooks, "useScanQuantParameterSensitivity").mockReturnValue({
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof quantHooks.useScanQuantParameterSensitivity>);

    const onApplyOptimal = vi.fn();

    renderComponent(
      <BacktestParameterSensitivity
        runId="test-run-123"
        strategy={{
          type: "ma_cross",
          version: "1.0.0",
          parameters: { fast_period: 5, slow_period: 20 },
        }}
        onApplyOptimal={onApplyOptimal}
      />,
    );

    expect(screen.getByText(/策略参数敏感性与稳健度分析/)).toBeInTheDocument();
    const scanBtn = screen.getByRole("button", { name: /开始网格扫描/ });
    expect(scanBtn).toBeEnabled();

    fireEvent.click(scanBtn);

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        runId: "test-run-123",
        request: expect.objectContaining({
          param1_name: "fast_period",
        }),
      });
    });

    // 检查扫描结果展示
    expect(await screen.findByText(/参数稳健度评分：/)).toBeInTheDocument();
    expect(screen.getByText(/82.5 分/)).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText(/fast_period=5, slow_period=20/)).toBeInTheDocument();

    // 点击一键应用
    const applyBtn = screen.getByRole("button", { name: /一键应用/ });
    fireEvent.click(applyBtn);
    expect(onApplyOptimal).toHaveBeenCalledWith("fast_period", 5, "slow_period", 20);
  });
});
