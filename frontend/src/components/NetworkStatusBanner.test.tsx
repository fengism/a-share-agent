import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NetworkStatusBanner from "./NetworkStatusBanner";

describe("NetworkStatusBanner", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("renders nothing when online initially", () => {
    const { container } = render(<NetworkStatusBanner initialOnline={true} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders offline warning when initially offline", () => {
    render(<NetworkStatusBanner initialOnline={false} />);
    expect(
      screen.getByText("网络连接已断开，数据已暂停自动刷新，请检查网络连接"),
    ).toBeInTheDocument();
  });

  it("shows recovery alert and triggers reconnect callback when going online", () => {
    vi.useFakeTimers();
    const onReconnect = vi.fn();
    render(
      <NetworkStatusBanner
        initialOnline={false}
        recoveredDisplayMs={2000}
        onReconnect={onReconnect}
      />,
    );

    expect(screen.getByText(/网络连接已断开/)).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(onReconnect).toHaveBeenCalledOnce();
    expect(
      screen.getByText("网络已恢复连接，正在自动同步最新行情数据"),
    ).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.queryByText(/网络已恢复连接/)).toBeNull();
  });

  it("switches back to offline when connection is lost again", () => {
    render(<NetworkStatusBanner initialOnline={true} />);
    expect(screen.queryByRole("status")).toBeNull();

    act(() => {
      window.dispatchEvent(new Event("offline"));
    });

    expect(
      screen.getByText("网络连接已断开，数据已暂停自动刷新，请检查网络连接"),
    ).toBeInTheDocument();
  });
});
