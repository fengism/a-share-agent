import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import StockExternalLink from "./StockExternalLink";

describe("StockExternalLink", () => {
  it("links to the in-app stock profile page", () => {
    render(
      <MemoryRouter>
        <StockExternalLink code="SH601991" name="大唐发电">
          大唐发电 601991
        </StockExternalLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "大唐发电 601991" });
    expect(link).toHaveAttribute("href", "/stock/601991");
    expect(link).toHaveAttribute("title", "查看大唐发电（601991）个股详情");
  });

  it("links to HK stock profile page", () => {
    render(
      <MemoryRouter>
        <StockExternalLink code="00700" name="腾讯控股">
          腾讯控股 00700
        </StockExternalLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "腾讯控股 00700" });
    expect(link).toHaveAttribute("href", "/stock/00700");
    expect(link).toHaveAttribute("title", "查看腾讯控股（00700）个股详情");
  });

  it("renders non-link content for an unsupported code", () => {
    render(
      <MemoryRouter>
        <StockExternalLink code="invalid">未知股票</StockExternalLink>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link", { name: "未知股票" })).not.toBeInTheDocument();
    expect(screen.getByText("未知股票")).toBeInTheDocument();
  });
});
