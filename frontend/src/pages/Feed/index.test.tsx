import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import Feed from ".";

vi.mock("./FeedTabs", () => ({
  default: ({ searchQuery }: { searchQuery: string }) => <div>市场资讯列表：{searchQuery || "全部"}</div>,
}));

vi.mock("./NewsAnalysisPanel", () => ({
  default: () => <div>市场资讯摘要</div>,
}));

vi.mock("../../features/feed/TwitterFeed", () => ({
  default: ({ searchQuery }: { searchQuery: string }) => <div>Twitter 资讯列表：{searchQuery || "全部"}</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>;
}

describe("Feed page", () => {
  it("provides Market and Twitter columns and keeps the selected column in the URL", () => {
    render(
      <MemoryRouter initialEntries={["/feed"]}>
        <Feed />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /市场资讯$/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Twitter 资讯$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "资讯中心" })).toBeInTheDocument();
    expect(screen.getByText("聚合市场快讯、财经媒体与社交信号")).toBeInTheDocument();
    expect(screen.getByLabelText("搜索市场资讯")).toBeInTheDocument();
    expect(screen.getByText("市场资讯列表：全部")).toBeInTheDocument();
    expect(screen.getByText("市场资讯摘要")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /Twitter 资讯$/ }));

    expect(screen.getByRole("heading", { name: "资讯中心" })).toBeInTheDocument();
    expect(screen.getByLabelText("搜索 Twitter 资讯")).toBeInTheDocument();
    expect(screen.getByText("Twitter 资讯列表：全部")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/feed?tab=twitter");
  });

  it("opens Twitter directly from a compatible feed URL", () => {
    render(
      <MemoryRouter initialEntries={["/feed?tab=twitter&q=科技"]}>
        <Feed />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /Twitter 资讯$/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByDisplayValue("科技")).toHaveAttribute("placeholder", "搜索推文标题或内容");
    expect(screen.getByText("Twitter 资讯列表：科技")).toBeInTheDocument();
  });
});
