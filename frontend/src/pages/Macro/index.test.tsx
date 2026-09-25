import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { message } from "antd";
import Macro from ".";

const mocks = vi.hoisted(() => ({
  refresh: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useForceRefreshMacroAllData: () => ({
    mutate: mocks.refresh,
    isPending: false,
  }),
}));

vi.mock("../../components/ResponsiveSectionNav", () => ({
  default: () => <div>宏观指标导航</div>,
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

describe("Macro page", () => {
  afterEach(() => vi.clearAllMocks());

  it("forces a macro data refresh and reports success", () => {
    mocks.refresh.mockImplementation((_variables, options) => options.onSuccess());
    render(
      <MemoryRouter>
        <Macro />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "宏观经济" })).toBeInTheDocument();
    expect(screen.getByLabelText("数据覆盖范围")).toHaveTextContent("10 大主题");
    expect(screen.getByLabelText("数据覆盖范围")).toHaveTextContent("商品期货 & 全国进出口");

    fireEvent.click(screen.getByRole("button", { name: /强制刷新/ }));

    expect(mocks.refresh).toHaveBeenCalledWith(undefined, expect.objectContaining({
      onSuccess: expect.any(Function),
      onError: expect.any(Function),
    }));
    expect(message.success).toHaveBeenCalledWith("宏观数据已刷新");
  });
});
