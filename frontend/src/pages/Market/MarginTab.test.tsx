import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MarginTab from "./MarginTab";

vi.mock("../../api/queries", () => ({
  useMarketMargin: () => ({
    data: {
      source: "东方财富",
      fetched_at: "2026-08-20T16:00:00+08:00",
      items: [
        { date: "2026-08-18", rzye: 26000.11, rqye: 265.12, rzrqye: 26265.23, rzmre: 1900.5, rzche: 1850.2, rzjme: 50.3 },
        { date: "2026-08-19", rzye: 26411.51, rqye: 264.53, rzrqye: 26676.05, rzmre: 2155.12, rzche: 2452.29, rzjme: -297.17 },
        { date: "2026-08-20", rzye: 26395.22, rqye: 268.35, rzrqye: 26663.56, rzmre: 1888.29, rzche: 1904.59, rzjme: -16.3 },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="margin-chart" />,
}));

describe("MarginTab", () => {
  it("renders the latest margin balances and the history chart", () => {
    render(<MarginTab />);

    expect(screen.getByText("沪深两市融资融券历史走势")).toBeInTheDocument();
    expect(screen.getByTestId("margin-chart")).toBeInTheDocument();
    expect(screen.getByTestId("margin-total-balance")).toHaveTextContent("26,663.56");
    expect(screen.getByTestId("margin-fin-balance")).toHaveTextContent("26,395.22");
    expect(screen.getByTestId("margin-sec-balance")).toHaveTextContent("268.35");
    expect(screen.getByTestId("margin-balance-change")).toHaveTextContent("-12.49");
    expect(screen.getByText(/数据截至：2026-08-20/)).toBeInTheDocument();
  });
});
