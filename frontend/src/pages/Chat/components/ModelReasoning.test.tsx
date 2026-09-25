import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModelReasoning } from "./ModelReasoning";

describe("ModelReasoning", () => {
  it("follows new reasoning only while the reader stays near the bottom", () => {
    const { rerender } = render(<ModelReasoning content="第一段" isStreaming />);
    const scroll = screen.getByLabelText("模型返回的推理内容，可滚动查看");
    Object.defineProperties(scroll, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 360 },
    });
    rerender(<ModelReasoning content="第一段。第二段" isStreaming />);
    expect(scroll.scrollTop).toBe(1000);

    scroll.scrollTop = 0;
    fireEvent.scroll(scroll);
    rerender(<ModelReasoning content="第一段。第二段。第三段" isStreaming />);
    expect(scroll.scrollTop).toBe(0);

    scroll.scrollTop = 640;
    fireEvent.scroll(scroll);
    rerender(<ModelReasoning content="第一段。第二段。第三段。第四段" isStreaming />);
    expect(scroll.scrollTop).toBe(1000);
  });

  it("does not auto-scroll completed history", () => {
    const { rerender } = render(<ModelReasoning content="历史推理" isStreaming={false} />);
    const scroll = screen.getByLabelText("模型返回的推理内容，可滚动查看");
    Object.defineProperty(scroll, "scrollHeight", { value: 1000 });
    rerender(<ModelReasoning content="历史推理补全" isStreaming={false} />);
    expect(scroll.scrollTop).toBe(0);
  });
});

it("renders separate source/turn/retry labels and keeps legacy gaps", () => {
  render(<ModelReasoning content="旧前分析一分析二旧后" isStreaming={false} blocks={[
    { block_id: "a", source: "财务分析", stage: "agent", turn: 1, attempt: 1, start: 2, end: 5 },
    { block_id: "b", source: "财务分析", stage: "agent", turn: 2, attempt: 2, task_id: "task", start: 5, end: 8 },
  ]} />);
  expect(screen.getByText("财务分析 · 第 1 轮")).toBeInTheDocument();
  expect(screen.getByText("财务分析 · 第 2 轮 · 第 2 次尝试 · task")).toBeInTheDocument();
  for (const text of ["旧前", "分析一", "分析二", "旧后"]) expect(screen.getByText(text)).toBeInTheDocument();
});
