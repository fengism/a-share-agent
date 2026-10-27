import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionManagerCard from "./SessionManagerCard";
import { describeUserAgent } from "./sessionDevice";

const mocks = vi.hoisted(() => ({
  revoke: vi.fn(),
  refetch: vi.fn(),
  message: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../../api/queries", () => ({
  useSessions: () => ({
    data: {
      items: [
        {
          session_id: "abcdef123456",
          created_at: "2026-10-20 09:00:00",
          last_seen_at: "2026-10-22 21:15:00",
          expires_at: "2026-11-03 09:00:00",
          ip_address: "127.0.0.1",
          user_agent:
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
          is_current: true,
        },
        {
          session_id: "fedcba654321",
          created_at: "2026-10-19 21:30:00",
          last_seen_at: "2026-10-19 21:30:00",
          expires_at: "2026-11-02 21:30:00",
          ip_address: "203.0.113.9",
          user_agent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
          is_current: false,
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  }),
  useRevokeSession: () => ({ mutate: mocks.revoke, isPending: false }),
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: { ...mocks.message },
  };
});

describe("SessionManagerCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders devices with current marker and Beijing time", () => {
    render(<SessionManagerCard />);

    expect(screen.getByText("登录设备")).toBeInTheDocument();
    expect(screen.getByText("当前")).toBeInTheDocument();
    expect(screen.getByText("macOS · Chrome")).toBeInTheDocument();
    expect(screen.getByText("iOS · Safari")).toBeInTheDocument();
    expect(screen.getByText("203.0.113.9")).toBeInTheDocument();
    // naive 北京时间串按 +08:00 解析后仍显示同一墙上时钟
    expect(screen.getAllByText("2026/10/20 09:00:00").length).toBeGreaterThan(0);
    // 「最近活跃」按北京时间渲染
    expect(screen.getByText("2026/10/22 21:15:00")).toBeInTheDocument();
  });

  it("asks for confirmation before revoking another device", async () => {
    render(<SessionManagerCard />);

    const buttons = screen.getAllByRole("button", { name: /退\s*出/ });
    fireEvent.click(buttons[1]);
    await waitFor(() => expect(screen.getByText("让该设备下线？")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "确认退出" }));
    expect(mocks.revoke).toHaveBeenCalledWith("fedcba654321", expect.anything());
  });

  it("refreshes the list on demand", () => {
    render(<SessionManagerCard />);
    fireEvent.click(screen.getByRole("button", { name: /刷\s*新/ }));
    expect(mocks.refetch).toHaveBeenCalled();
  });
});

describe("describeUserAgent", () => {
  it("recognises common clients", () => {
    expect(describeUserAgent("")).toEqual({ icon: "desktop", label: "未知设备" });
    expect(describeUserAgent("Mozilla/5.0 (Windows NT 10.0) Chrome/121.0").label).toBe("Windows · Chrome");
    expect(describeUserAgent("Mozilla/5.0 (Linux; Android 14) Mobile").icon).toBe("mobile");
    expect(describeUserAgent("python-httpx/0.28").label).toBe("脚本客户端");
    expect(describeUserAgent("Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0").label).toBe("Linux · Firefox");
  });
});
