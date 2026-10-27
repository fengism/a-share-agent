import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../../api/queryHooks/settings", () => ({
  useFetchLlmModels: () => ({ mutate: vi.fn(), isPending: false }),
}));

import LlmConfigCard from "./LlmConfigCard";

const baseForm = {
  llm_provider: "qwen",
  llm_base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  llm_api_key: "sk-test",
  llm_model: "qwen-plus",
  llm_extra_body: {},
};

function renderCard(onChange = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <LlmConfigCard
        form={baseForm}
        onChange={onChange}
        onSave={vi.fn()}
        isSaving={false}
        onProviderChange={vi.fn()}
        providerDefaults={{}}
      />
    </QueryClientProvider>,
  );
  // 高级面板默认收起：展开后才能编辑 extra_body。
  fireEvent.click(screen.getByText(/高级：超时/));
  return onChange;
}

describe("LlmConfigCard 厂商私有字段", () => {
  it("合法的 JSON 对象会写回表单", () => {
    const onChange = renderCard();
    const textarea = screen.getByLabelText("extra_body");
    fireEvent.change(textarea, {
      target: { value: '{"chat_template_kwargs": {"enable_thinking": true}}' },
    });
    expect(onChange).toHaveBeenCalledWith({
      llm_extra_body: { chat_template_kwargs: { enable_thinking: true } },
    });
  });

  it("非法 JSON 只提示错误，不写回表单", () => {
    const onChange = renderCard();
    const textarea = screen.getByLabelText("extra_body");
    fireEvent.change(textarea, { target: { value: "{oops" } });
    expect(onChange).not.toHaveBeenCalledWith(expect.objectContaining({ llm_extra_body: expect.anything() }));
    expect(screen.getByText(/JSON 解析失败/)).toBeTruthy();
  });

  it("数组等非对象形态被拒绝", () => {
    const onChange = renderCard();
    const textarea = screen.getByLabelText("extra_body");
    fireEvent.change(textarea, { target: { value: "[1,2]" } });
    expect(onChange).not.toHaveBeenCalledWith(expect.objectContaining({ llm_extra_body: expect.anything() }));
    expect(screen.getByText(/必须是 JSON 对象/)).toBeTruthy();
  });
});
