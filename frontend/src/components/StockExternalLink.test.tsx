import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StockExternalLink from "./StockExternalLink";

describe("StockExternalLink", () => {
  it("opens the corresponding Eastmoney stock page safely", () => {
    render(
      <StockExternalLink code="SH601991" name="大唐发电">
        大唐发电 601991
      </StockExternalLink>,
    );

    const link = screen.getByRole("link", { name: "大唐发电 601991" });
    expect(link).toHaveAttribute("href", "https://data.eastmoney.com/stockdata/601991.html");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(link).toHaveAttribute("title", "在东方财富查看大唐发电（601991）");
  });

  it("renders non-link content for an unsupported code", () => {
    render(<StockExternalLink code="invalid">未知股票</StockExternalLink>);

    expect(screen.queryByRole("link", { name: "未知股票" })).not.toBeInTheDocument();
    expect(screen.getByText("未知股票")).toBeInTheDocument();
  });
});
