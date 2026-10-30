import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SectionBlock from "./SectionBlock";

describe("SectionBlock", () => {
  it("renders title, extra and content", () => {
    render(
      <SectionBlock title="市场图谱" extra="3 条">
        <div>图表内容</div>
      </SectionBlock>,
    );

    expect(screen.getByRole("heading", { level: 4, name: "市场图谱" })).toBeInTheDocument();
    expect(screen.getByText("3 条")).toBeInTheDocument();
    expect(screen.getByText("图表内容")).toBeInTheDocument();
  });

  it("marks the first block so it has no divider", () => {
    const { container } = render(
      <SectionBlock title="首个" first>
        <div>x</div>
      </SectionBlock>,
    );

    expect(container.querySelector(".section-block--first")).not.toBeNull();
  });

  it("renders a description above the body", () => {
    render(
      <SectionBlock title="情绪周期" description="近 10 个交易日">
        <div>x</div>
      </SectionBlock>,
    );

    expect(screen.getByText("近 10 个交易日")).toBeInTheDocument();
  });

  it("renders without a header when no title or extra is given", () => {
    const { container } = render(<SectionBlock><div>x</div></SectionBlock>);
    expect(container.querySelector(".section-block__head")).toBeNull();
  });
});
