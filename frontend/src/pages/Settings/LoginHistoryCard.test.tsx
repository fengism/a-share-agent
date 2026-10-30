import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginHistoryCard from "./LoginHistoryCard";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  useMyLoginAuditLogs: vi.fn(),
  isNarrow: false,
}));

vi.mock("../../api/queries", () => ({
  useMyLoginAuditLogs: mocks.useMyLoginAuditLogs,
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => mocks.isNarrow,
}));

function mockLogs(items: unknown[], total = items.length) {
  mocks.useMyLoginAuditLogs.mockReturnValue({
    data: { items, total, limit: 10, offset: 0 },
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  });
}

describe("LoginHistoryCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mocks.isNarrow = false;
  });

  it("renders own login attempts with Beijing time and device label", () => {
    mockLogs([
      {
        id: 1,
        username: "alice",
        user_id: 7,
        ip_address: "203.0.113.9",
        user_agent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0 Safari/537.36",
        status: "success",
        details: "",
        created_at: "2026-10-22 09:30:00",
      },
      {
        id: 2,
        username: "alice",
        user_id: 7,
        ip_address: "198.51.100.4",
        user_agent: "python-httpx/0.28",
        status: "failed_credentials",
        details: "wrong password",
        created_at: "2026-10-21 23:05:00",
      },
    ]);

    render(<LoginHistoryCard />);

    expect(screen.getByText("我的登录记录")).toBeInTheDocument();
    expect(screen.getByText("登录成功")).toBeInTheDocument();
    expect(screen.getByText("密码错误")).toBeInTheDocument();
    expect(screen.getByText("203.0.113.9")).toBeInTheDocument();
    expect(screen.getByText("macOS · Chrome")).toBeInTheDocument();
    expect(screen.getByText("脚本客户端")).toBeInTheDocument();
    // naive 北京时间串按 +08:00 解析后仍显示同一墙上时钟
    expect(screen.getByText("2026/10/22 09:30:00")).toBeInTheDocument();
  });

  it("shows an empty state when there is no history", () => {
    mockLogs([], 0);
    render(<LoginHistoryCard />);
    expect(screen.getByText("暂无登录记录")).toBeInTheDocument();
  });

  it("passes the status filter to the query", async () => {
    mockLogs([], 0);
    render(<LoginHistoryCard />);

    fireEvent.mouseDown(screen.getByRole("combobox"));
    const option = await screen.findByText("限流阻断", { selector: ".ant-select-item-option-content" });
    fireEvent.click(option);

    await waitFor(() =>
      expect(mocks.useMyLoginAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ status: "failed_rate_limited", offset: 0 }),
      ),
    );
  });

  it("refreshes on demand", () => {
    mockLogs([], 0);
    render(<LoginHistoryCard />);
    fireEvent.click(screen.getByRole("button", { name: /刷\s*新/ }));
    expect(mocks.refetch).toHaveBeenCalled();
  });

  it("renders a card list instead of a wide table on narrow screens", () => {
    mocks.isNarrow = true;
    mockLogs([
      {
        id: 3,
        username: "alice",
        user_id: 7,
        ip_address: "198.51.100.4",
        user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1",
        status: "success",
        details: "",
        created_at: "2026-10-22 10:00:00",
      },
    ]);

    render(<LoginHistoryCard />);

    const list = screen.getByRole("list", { name: "我的登录记录列表" });
    expect(within(list).getByText("198.51.100.4")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
