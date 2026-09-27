import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ResearchBudgetCard from "./ResearchBudgetCard";

const baseForm = {
  analysis_llm_timeout_seconds: 1200,
  agent_research_timeout_seconds: 1200,
  industry_chain_repair_timeout_seconds: 600,
  industry_chain_tool_calls_total: 72,
  industry_chain_repair_tool_calls_total: 36,
  chat_max_tool_calls_total: 32,
};

describe("ResearchBudgetCard", () => {
  it("renders all six budget fields with current values", () => {
    render(<ResearchBudgetCard form={baseForm} onChange={vi.fn()} onSave={vi.fn()} isSaving={false} />);

    expect(screen.getByText("研究预算与超时（全局）")).toBeInTheDocument();
    // 两个超时字段默认同为 1200，其余值唯一
    expect(screen.getAllByDisplayValue(1200)).toHaveLength(2);
    expect(screen.getByDisplayValue(600)).toBeInTheDocument();
    expect(screen.getByDisplayValue(72)).toBeInTheDocument();
    expect(screen.getByDisplayValue(36)).toBeInTheDocument();
    expect(screen.getByDisplayValue(32)).toBeInTheDocument();
  });

  it("emits the changed field through onChange", () => {
    const onChange = vi.fn();
    render(<ResearchBudgetCard form={baseForm} onChange={onChange} onSave={vi.fn()} isSaving={false} />);

    const spinButtons = screen.getAllByRole("spinbutton");
    fireEvent.change(spinButtons[0]!, { target: { value: "1800" } });

    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ analysis_llm_timeout_seconds: 1800 }));
  });

  it("falls back to defaults when form fields are missing", () => {
    render(<ResearchBudgetCard form={{}} onChange={vi.fn()} onSave={vi.fn()} isSaving={false} />);

    expect(screen.getAllByDisplayValue(1200)).toHaveLength(2);
    expect(screen.getByDisplayValue(600)).toBeInTheDocument();
  });
});
