import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import FeedTabs from "./FeedTabs";

vi.mock("../../api/queries", () => ({
  useMarketKuaixun: () => ({
    data: [],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketOtherNews: () => ({
    data: [],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("FeedTabs", () => {
  it("keeps Twitter out of the general news tabs", () => {
    render(
      <MemoryRouter>
        <FeedTabs searchQuery="" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("tab", { name: /7×24 快讯/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /新闻资讯/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Twitter/ })).toBeNull();
  });
});
