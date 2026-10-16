import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import IwencaiConfigCard from "./IwencaiConfigCard";
import LlmConfigCard from "./LlmConfigCard";

// LlmConfigCard 内部使用 useMutation（模型列表获取），需要 QueryClientProvider 包裹
function withQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient();
  return <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>;
}

describe("个人凭证隔离提示", () => {
  it("解释 LLM 全局 Key 的使用边界并保留个人 Key 输入", () => {
    const onChange = vi.fn();
    render(
      withQueryClient(
        <LlmConfigCard
          form={{ llm_provider: "openai", llm_api_key: "glob***cret" }}
          onChange={onChange}
          onSave={vi.fn()}
          isSaving={false}
          onProviderChange={vi.fn()}
          providerDefaults={{}}
        />,
      ),
    );
    expect(screen.getByText(/管理员保存时将自动同步为系统全局配置/)).toBeInTheDocument();
    expect(screen.getByText(/未填写个人 Key 时自动使用系统全局 Key/)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/输入新的 API Key 以覆盖/), {
      target: { value: "personal-key" },
    });
    expect(onChange).toHaveBeenCalledWith({ llm_api_key: "personal-key" });
  });

  it("提示问财自定义地址需要个人 Key", () => {
    render(
      <IwencaiConfigCard
        form={{}}
        onChange={vi.fn()}
        onSave={vi.fn()}
        isSaving={false}
      />,
    );
    expect(screen.getByText(/自定义问财地址需要填写个人 API Key/)).toBeInTheDocument();
  });
});
