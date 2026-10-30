import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SecurityAuditCard from "./SecurityAuditCard";
import { summarizeDetails } from "./auditMeta";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
  isNarrow: false,
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => mocks.isNarrow,
}));

vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
    }),
  };
});

vi.mock("../../api/queries", () => ({
  useAdminAuditActions: () => ({
    data: {
      items: [
        {
          id: 11,
          actor_id: 1,
          actor_username: "admin",
          actor_ip: "203.0.113.7",
          actor_user_agent: "Mozilla/5.0",
          action: "user.role",
          target_type: "user",
          target_id: "7",
          target_label: "alice",
          details: '{"is_admin": true}',
          created_at: "2026-09-22 11:00:00",
        },
        {
          id: 12,
          actor_id: 1,
          actor_username: "admin",
          actor_ip: "203.0.113.7",
          actor_user_agent: "Mozilla/5.0",
          action: "config.update_global",
          target_type: "config",
          target_id: "global",
          target_label: "",
          details: '{"fields": ["llm_api_key", "llm_base_url"]}',
          created_at: "2026-09-22 11:05:00",
        },
      ],
      total: 2,
      limit: 20,
      offset: 0,
    },
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  }),
  useLoginAuditLogs: (params: { username?: string; status?: string } | undefined) => {
    const allItems = [
      {
        id: 1,
        username: "admin",
        user_id: 1,
        ip_address: "127.0.0.1",
        user_agent: "Mozilla/5.0 Chrome/120.0",
        status: "success",
        details: "",
        created_at: "2026-09-22 10:00:00",
      },
      {
        id: 2,
        username: "hacker_target",
        user_id: null,
        ip_address: "192.168.1.50",
        user_agent: "Python-urllib/3.10",
        status: "failed_credentials",
        details: "invalid username or password",
        created_at: "2026-09-22 10:05:00",
      },
      {
        id: 3,
        username: "disabled_user",
        user_id: 3,
        ip_address: "10.0.0.1",
        user_agent: "Safari/17.0",
        status: "failed_disabled",
        details: "account disabled",
        created_at: "2026-09-22 10:10:00",
      },
    ];

    const filtered = allItems.filter((i) => {
      if (params?.username && !i.username.includes(params.username)) return false;
      if (params?.status && i.status !== params.status) return false;
      return true;
    });

    return {
      data: {
        items: filtered,
        total: filtered.length,
        limit: 20,
        offset: 0,
      },
      isLoading: false,
      error: null,
      refetch: mocks.refetch,
    };
  },
}));

vi.mock("antd", async () => {
  const actual = await vi.importActual<typeof import("antd")>("antd");
  return {
    ...actual,
    message: {
      ...actual.message,
      error: vi.fn(),
      success: vi.fn(),
    },
  };
});

describe("SecurityAuditCard", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders audit log items and columns", () => {
    render(<SecurityAuditCard />);

    expect(screen.getByText("安全与登录审计日志")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("登录成功")).toBeInTheDocument();
    expect(screen.getByText("密码错误")).toBeInTheDocument();
    expect(screen.getByText("账号已停用")).toBeInTheDocument();
    expect(screen.getByText("127.0.0.1")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.50")).toBeInTheDocument();
  });

  it("triggers refetch when clicking refresh button", () => {
    render(<SecurityAuditCard />);
    const refreshBtn = screen.getByRole("button", { name: /刷\s*新/ });
    fireEvent.click(refreshBtn);
    expect(mocks.refetch).toHaveBeenCalled();
  });

  it("allows typing username to filter logs", () => {
    render(<SecurityAuditCard />);
    const input = screen.getByPlaceholderText("搜索用户名...");
    fireEvent.change(input, { target: { value: "hacker" } });
    expect(screen.getByText("hacker_target")).toBeInTheDocument();
    expect(screen.queryByText("admin")).not.toBeInTheDocument();
  });

  it("switches to admin action tab and shows change details", () => {
    render(<SecurityAuditCard />);

    fireEvent.click(screen.getByRole("tab", { name: "管理员操作" }));

    expect(screen.getByText("修改角色")).toBeInTheDocument();
    expect(screen.getByText("修改全局配置")).toBeInTheDocument();
    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText(/is_admin: 是/)).toBeInTheDocument();
    // 全局配置只显示字段名，绝不显示取值
    expect(screen.getByText(/llm_api_key, llm_base_url/)).toBeInTheDocument();
    expect(screen.queryByText(/sk-/)).not.toBeInTheDocument();
  });
});

describe("summarizeDetails", () => {
  it("flattens json details and tolerates broken payloads", () => {
    expect(summarizeDetails('{"is_active": false}')).toBe("is_active: 否");
    expect(summarizeDetails('{"fields": ["a", "b"]}')).toBe("fields: a, b");
    expect(summarizeDetails('{"fields": ["a","b","c","d","e","f","g"]}')).toContain("等 7 项");
    expect(summarizeDetails("")).toBe("—");
    expect(summarizeDetails("not-json")).toBe("not-json");
    expect(summarizeDetails("[1,2]")).toBe("[1,2]");
  });

  it("renders the audit records as cards on narrow screens", () => {
    mocks.isNarrow = true;
    render(<SecurityAuditCard />);

    expect(screen.getByRole("list", { name: "登录审计记录列表" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    mocks.isNarrow = false;
  });
});
