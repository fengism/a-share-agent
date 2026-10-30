import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PageShell, { PageBody, PageHeader } from "./PageShell";

describe("PageShell", () => {
  it("renders a titled header with description and actions", () => {
    render(
      <PageShell>
        <PageHeader
          title="市场"
          icon={<span>icon</span>}
          badge={<span>非交易日</span>}
          description="查看大盘与资金动向"
          actions={<button type="button">刷新</button>}
        />
      </PageShell>,
    );

    expect(screen.getByRole("heading", { level: 1, name: /市场/ })).toBeInTheDocument();
    expect(screen.getByText("查看大盘与资金动向")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新" })).toBeInTheDocument();
    expect(screen.getByText("非交易日")).toBeInTheDocument();
  });

  it("supports a full-width dashboard shell", () => {
    const { container } = render(<PageShell width="full"><div>内容</div></PageShell>);
    expect(container.querySelector(".page-shell--full")).not.toBeNull();
  });

  it("renders the nav slot above the body content", () => {
    render(
      <PageShell>
        <PageBody nav={<nav>分区导航</nav>}>
          <div>主体</div>
        </PageBody>
      </PageShell>,
    );

    expect(screen.getByText("分区导航")).toBeInTheDocument();
    expect(screen.getByText("主体")).toBeInTheDocument();
  });

  it("omits description and actions when not provided", () => {
    const { container } = render(<PageShell><PageHeader title="极简" /></PageShell>);
    expect(container.querySelector(".page-shell__description")).toBeNull();
    expect(container.querySelector(".page-shell__actions")).toBeNull();
  });
});
