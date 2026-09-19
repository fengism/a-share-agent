import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import QuantPageHeader from "./QuantPageHeader";

describe("QuantPageHeader", () => {
  it("keeps the page introduction compact", () => {
    render(<QuantPageHeader />);

    expect(screen.getByRole("heading", { name: "量化研究" })).toBeInTheDocument();
    expect(screen.queryByText("READY")).not.toBeInTheDocument();
    expect(screen.getByLabelText("回测类型")).toHaveTextContent("日线回测");
    expect(screen.getByText("策略实验室")).toBeInTheDocument();
    expect(screen.getByText(/配置策略、跟踪任务/)).toBeInTheDocument();
    expect(screen.queryByLabelText("回测能力")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("量化研究流程")).not.toBeInTheDocument();
  });
});
