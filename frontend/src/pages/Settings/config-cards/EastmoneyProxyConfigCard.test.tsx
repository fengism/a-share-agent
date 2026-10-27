import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import OutboundProxyConfigCard from "./EastmoneyProxyConfigCard";
import { normalizeProxyUrl, validateProxyUrl } from "./EastmoneyProxyConfigCard.utils";

function renderCard(overrides: Partial<Parameters<typeof OutboundProxyConfigCard>[0]> = {}) {
  const onChange = vi.fn();
  const onSave = vi.fn();
  render(
    <OutboundProxyConfigCard
      form={{ outbound_proxy_type: "none", outbound_proxy_url: "" }}
      onChange={onChange}
      onSave={onSave}
      isSaving={false}
      {...overrides}
    />,
  );
  return { onChange, onSave };
}

describe("OutboundProxyConfigCard", () => {
  it("switches proxy type and reports the change", () => {
    const { onChange } = renderCard();

    fireEvent.click(screen.getByText("SOCKS5 代理"));
    expect(onChange).toHaveBeenCalledWith({ outbound_proxy_type: "socks5" });
  });

  it("edits the proxy address and delegates saving", () => {
    const { onChange, onSave } = renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://h:1" },
    });

    fireEvent.change(screen.getByLabelText("出站代理地址"), {
      target: { value: "socks5h://user:pw@proxy.local:2260" },
    });
    expect(onChange).toHaveBeenCalledWith({
      outbound_proxy_url: "socks5h://user:pw@proxy.local:2260",
    });

    fireEvent.click(screen.getByRole("button", { name: /保存出站代理配置/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });

  it("rejects an address whose scheme conflicts with the selected type", () => {
    renderCard({
      form: {
        outbound_proxy_type: "http",
        outbound_proxy_url: "socks5h://proxy.local:2260",
      },
    });

    expect(screen.getByText(/代理类型为 HTTP 时，地址协议必须是 http\/https/)).toBeInTheDocument();
  });

  it("requires a port for SOCKS5 proxies", () => {
    renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://proxy.local" },
    });

    expect(screen.getByText(/SOCKS5 代理必须指定端口/)).toBeInTheDocument();
  });

  it("accepts an address without a scheme and infers it from the proxy type", () => {
    renderCard({
      form: {
        outbound_proxy_type: "socks5",
        outbound_proxy_url: "user:pw@proxy.local:2260",
      },
    });

    expect(screen.queryByText(/必须是 socks5/)).not.toBeInTheDocument();
  });

  it("skips validation for a masked saved address", () => {
    renderCard({
      form: {
        outbound_proxy_type: "http",
        outbound_proxy_url: "http://***",
      },
    });

    expect(screen.getByText(/内容已脱敏/)).toBeInTheDocument();
  });

  it("disables the address input, scopes, and the test button when the proxy is off", () => {
    renderCard();

    expect(screen.getByLabelText("出站代理地址")).toBeDisabled();
    expect(screen.getByRole("button", { name: /测试连通性/ })).toBeDisabled();
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes.length).toBeGreaterThan(0);
    checkboxes.forEach((cb) => expect(cb).toBeDisabled());
  });

  it("changes selected proxy scopes", () => {
    const { onChange } = renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://h:2260", outbound_proxy_scopes: ["eastmoney"] },
    });

    fireEvent.click(screen.getByLabelText(/同花顺/));
    expect(onChange).toHaveBeenCalledWith({
      outbound_proxy_scopes: expect.arrayContaining(["eastmoney", "ths"]),
    });
  });

  it("renders the connectivity test result", () => {
    renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://h:2260" },
      testResult: {
        ok: true,
        target_url: "http://push2his.eastmoney.com/api/qt/stock/kline/get",
        proxy_enabled: true,
        proxy_type: "socks5",
        exit_ip: "203.0.113.7",
        latency_ms: 812,
        message: "HTTP 200，出口 IP 203.0.113.7",
      },
    });

    expect(screen.getByText(/代理可用 · 812ms · 出口 203.0.113.7/)).toBeInTheDocument();
    expect(screen.getByText(/HTTP 200，出口 IP 203.0.113.7/)).toBeInTheDocument();
  });

  it("highlights an unusable proxy", () => {
    renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://h:2260" },
      testResult: {
        ok: false,
        target_url: "http://push2his.eastmoney.com/api/qt/stock/kline/get",
        proxy_enabled: true,
        proxy_type: "socks5",
        exit_ip: null,
        latency_ms: 1200,
        message: "代理请求失败: ConnectionError",
      },
    });

    expect(screen.getByText(/代理不可用 · 1200ms/)).toBeInTheDocument();
  });

  it("triggers the connectivity test", () => {
    const onTest = vi.fn();
    renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://h:2260" },
      onTest,
    });

    fireEvent.click(screen.getByRole("button", { name: /测试连通性/ }));
    expect(onTest).toHaveBeenCalledTimes(1);
  });

  it("validates and normalizes SOCKS5 proxy URLs correctly", () => {
    expect(validateProxyUrl("socks5://user:pw@proxy.local:2260", "socks5")).toBeNull();
    expect(validateProxyUrl("socks5h://user:pw@proxy.local:2260", "socks5")).toBeNull();
    expect(validateProxyUrl("socks://user:pw@proxy.local:2260", "socks5")).toBeNull();
    expect(validateProxyUrl("127.0.0.1:1080", "socks5")).toBeNull();
    expect(validateProxyUrl("http://127.0.0.1:1080", "socks5")).toContain("必须是 socks5/socks5h");
    expect(validateProxyUrl("socks5://127.0.0.1", "socks5")).toContain("必须指定端口");

    expect(normalizeProxyUrl("127.0.0.1:1080", "socks5")).toBe("socks5h://127.0.0.1:1080");
    expect(normalizeProxyUrl("socks://127.0.0.1:1080", "socks5")).toBe("socks5h://127.0.0.1:1080");
    expect(normalizeProxyUrl("socks5://127.0.0.1:1080", "socks5")).toBe("socks5://127.0.0.1:1080");
  });

  it("clears masked proxy url when switching proxy type to avoid scheme mismatch", () => {
    const { onChange } = renderCard({
      form: { outbound_proxy_type: "http", outbound_proxy_url: "http***7890" },
    });

    fireEvent.click(screen.getByText("SOCKS5 代理"));
    expect(onChange).toHaveBeenCalledWith({
      outbound_proxy_type: "socks5",
      outbound_proxy_url: "",
    });
  });

  it("clears proxy url when switching to none", () => {
    const { onChange } = renderCard({
      form: { outbound_proxy_type: "socks5", outbound_proxy_url: "socks5h://127.0.0.1:1080" },
    });

    fireEvent.click(screen.getByText("直连（不使用代理）"));
    expect(onChange).toHaveBeenCalledWith({
      outbound_proxy_type: "none",
      outbound_proxy_url: "",
    });
  });
});