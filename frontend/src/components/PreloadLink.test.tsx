import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PreloadLink from "./PreloadLink";

const { preloadAppRoute } = vi.hoisted(() => ({
  preloadAppRoute: vi.fn(),
}));

vi.mock("../routes/RoutePreloadContext", () => ({ useRoutePreload: () => preloadAppRoute }));

describe("PreloadLink", () => {
  beforeEach(() => preloadAppRoute.mockReset());

  it("preloads the route on pointer intent and keyboard focus", () => {
    render(
      <MemoryRouter>
        <PreloadLink to="/analysis/600519?date=20260813">查看分析</PreloadLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "查看分析" });
    fireEvent.pointerEnter(link);
    fireEvent.focus(link);

    expect(preloadAppRoute).toHaveBeenNthCalledWith(1, "/analysis/600519");
    expect(preloadAppRoute).toHaveBeenNthCalledWith(2, "/analysis/600519");
  });
});
