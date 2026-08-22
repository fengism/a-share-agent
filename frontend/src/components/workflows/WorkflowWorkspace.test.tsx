import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import WorkflowPageHeader from "./WorkflowPageHeader";
import WorkflowProgressPanel from "./WorkflowProgressPanel";
import WorkflowWorkspace from "./WorkflowWorkspace";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("workflow page primitives", () => {
  it("renders a consistent header, main content and history", () => {
    render(
      <>
        <WorkflowPageHeader title="产业链分析" description="统一工作流页面" />
        <WorkflowWorkspace historyTitle="历史记录" history={<div>历史内容</div>}>
          <div>工作流主体</div>
        </WorkflowWorkspace>
      </>,
    );

    expect(screen.getByText("产业链分析")).toBeInTheDocument();
    expect(screen.getByText("统一工作流页面")).toBeInTheDocument();
    expect(screen.getByText("工作流主体")).toBeInTheDocument();
    expect(screen.getByText("历史记录")).toBeInTheDocument();
    expect(screen.getByText("历史内容")).toBeInTheDocument();
    expect(screen.getByText("历史内容").closest(".ant-card-body")).toHaveStyle({
      maxHeight: "calc(100vh - 180px)",
      overflowY: "auto",
    });
  });

  it("closes mobile history when the selected history version changes", async () => {
    vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
      matches: query === "(max-width: 991px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    const { rerender } = render(
      <WorkflowWorkspace historyTitle="分析历史" historyVersion="first" history={<div>历史内容</div>}>
        <div>工作流主体</div>
      </WorkflowWorkspace>,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看历史" }));
    await waitFor(() => expect(document.querySelector(".ant-drawer-open")).toBeInTheDocument());

    rerender(
      <WorkflowWorkspace historyTitle="分析历史" historyVersion="second" history={<div>历史内容</div>}>
        <div>工作流主体</div>
      </WorkflowWorkspace>,
    );

    await waitFor(() => expect(document.querySelector(".ant-drawer-open")).not.toBeInTheDocument());
  });

  it("does not reopen mobile history after switching through desktop layout", async () => {
    let isCompact = true;
    let mediaListener: ((event: MediaQueryListEvent) => void) | undefined;
    vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
      matches: isCompact && query === "(max-width: 991px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_event, listener) => {
        mediaListener = listener as (event: MediaQueryListEvent) => void;
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <WorkflowWorkspace historyTitle="分析历史" history={<div>历史内容</div>}>
        <div>工作流主体</div>
      </WorkflowWorkspace>,
    );

    fireEvent.click(screen.getByRole("button", { name: "查看历史" }));
    await waitFor(() => expect(document.querySelector(".ant-drawer-open")).toBeInTheDocument());

    isCompact = false;
    act(() => mediaListener?.({ matches: false } as MediaQueryListEvent));
    await waitFor(() => expect(screen.queryByRole("button", { name: "查看历史" })).not.toBeInTheDocument());

    isCompact = true;
    act(() => mediaListener?.({ matches: true } as MediaQueryListEvent));
    await waitFor(() => expect(screen.getByRole("button", { name: "查看历史" })).toBeInTheDocument());
    expect(document.querySelector(".ant-drawer-open")).not.toBeInTheDocument();
  });

  it("renders workflow failures without a success indicator", () => {
    render(
      <WorkflowProgressPanel
        current={1}
        status="error"
        message="数据采集失败"
        items={[{ title: "数据采集" }, { title: "生成报告" }]}
      />,
    );

    expect(screen.getByText("数据采集失败")).toBeInTheDocument();
    expect(screen.getAllByLabelText("close-circle").length).toBeGreaterThan(0);
    expect(screen.getByRole("alert")).toHaveAttribute("aria-live", "assertive");
  });

  it("announces running workflow progress politely", () => {
    render(
      <WorkflowProgressPanel
        current={0}
        status="running"
        message="正在采集数据"
        items={[{ title: "数据采集" }, { title: "生成报告" }]}
      />,
    );

    expect(screen.getByRole("status")).toHaveAttribute("aria-live", "polite");
  });
});
