import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import StockInformationTabs from "./StockInformationTabs";

const mounts = vi.hoisted(() => ({ bulletins: vi.fn(), reports: vi.fn(), fundFlow: vi.fn() }));

vi.mock("../../features/stock-insights/AnnouncementsPanel", () => ({
  default: () => { mounts.bulletins(); return <div>公告内容</div>; },
}));
vi.mock("../../features/stock-insights/ResearchReportsPanel", () => ({
  default: () => { mounts.reports(); return <div>研报内容</div>; },
}));
vi.mock("../../features/stock-insights/FundFlowPanel", () => ({
  default: () => { mounts.fundFlow(); return <div>资金内容</div>; },
}));
vi.mock("./StockNewsPanel", () => ({ default: () => <div>新闻内容</div> }));

describe("StockInformationTabs", () => {
  it("only mounts the active information panel", () => {
    render(<StockInformationTabs code="600519" />);

    expect(screen.getByText("公告内容")).toBeInTheDocument();
    expect(mounts.bulletins).toHaveBeenCalled();
    expect(mounts.reports).not.toHaveBeenCalled();
    expect(mounts.fundFlow).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: "券商研报" }));
    expect(screen.getByText("研报内容")).toBeInTheDocument();
    expect(mounts.reports).toHaveBeenCalled();
    expect(mounts.fundFlow).not.toHaveBeenCalled();
  });

  it("activates the tab designated by url query infoTab", () => {
    render(
      <MemoryRouter initialEntries={["/stock/600519?infoTab=reports"]}>
        <StockInformationTabs code="600519" />
      </MemoryRouter>,
    );

    expect(screen.getByText("研报内容")).toBeInTheDocument();
    expect(mounts.reports).toHaveBeenCalled();
  });
});
