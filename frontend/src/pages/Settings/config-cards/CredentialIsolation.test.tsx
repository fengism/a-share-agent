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
          form={{ llm_provider: "openai", llm_api_key: "" }}
          onChange={onChange}
          onSave={vi.fn()}
          isSaving={false}
          onProviderChange={vi.fn()}
          providerDefaults={{}}
          inheritedKeys={["llm_provider", "llm_base_url", "llm_api_key"]}
        />,
      ),
    );
    // 继承状态下用一行说明代替原来的多处提示，且没有「改用管理员配置」按钮
    expect(screen.getByText("沿用管理员配置")).toBeInTheDocument();
    expect(screen.getByText(/留空即沿用管理员端点与 Key/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "改用管理员配置" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/留空即使用管理员配置的 Key/), {
      target: { value: "personal-key" },
    });
    expect(onChange).toHaveBeenCalledWith({ llm_api_key: "personal-key" });
  });

  it("自建端点时必须自备 Key，管理员 Key 不再自动跟随", () => {
    render(
      withQueryClient(
        <LlmConfigCard
          form={{ llm_provider: "openai", llm_base_url: "http://my-ollama:11434/v1", llm_api_key: "" }}
          onChange={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          onProviderChange={vi.fn()}
          providerDefaults={{}}
          inheritedKeys={["llm_api_key"]}
        />,
      ),
    );
    expect(screen.getByText("个人端点")).toBeInTheDocument();
    // 端点面板自动展开（已在个人端点状态），并给出"成对配置"说明
    expect(screen.getByText(/Base URL 与 API Key 必须成对配置/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("http://my-ollama:11434/v1")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/请输入该端点对应的 API Key/)).toBeInTheDocument();
  });

  it("管理员看到的是全局配置标签，没有「改用管理员配置」", () => {
    render(
      withQueryClient(
        <LlmConfigCard
          form={{ llm_provider: "openai", llm_api_key: "sk-admin" }}
          onChange={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          onProviderChange={vi.fn()}
          providerDefaults={{}}
          isAdmin
        />,
      ),
    );
    expect(screen.getByText("全局配置")).toBeInTheDocument();
    expect(screen.getByText(/这里的改动会同步为全局配置/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "改用管理员配置" })).not.toBeInTheDocument();
  });

  it("「改用管理员配置」触发携带显式清空补丁的保存", () => {
    const onUseAdminConfig = vi.fn();
    render(
      withQueryClient(
        <LlmConfigCard
          form={{ llm_provider: "deepseek", llm_api_key: "sk-mine" }}
          onChange={vi.fn()}
          onSave={vi.fn()}
          isSaving={false}
          onProviderChange={vi.fn()}
          providerDefaults={{}}
          inheritedKeys={[]}
          onUseAdminConfig={onUseAdminConfig}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "改用管理员配置" }));
    expect(onUseAdminConfig).toHaveBeenCalledTimes(1);
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
