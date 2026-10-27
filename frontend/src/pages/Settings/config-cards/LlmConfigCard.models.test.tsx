import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchMock } = vi.hoisted(() => ({ fetchMock: vi.fn() }));

vi.mock("../../../api/queryHooks/settings", () => ({
  useFetchLlmModels: () => ({ mutate: fetchMock, isPending: false }),
}));

import LlmConfigCard from "./LlmConfigCard";

const baseForm = {
  llm_provider: "custom",
  llm_base_url: "https://api.example.com/v1",
  llm_api_key: "sk-test",
  llm_model: "",
  llm_sub_model: "",
  llm_simple_tasks: "",
};

function renderCard(onChange = vi.fn(), formOverride = {}) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LlmConfigCard
        form={{ ...baseForm, ...formOverride }}
        onChange={onChange}
        onSave={vi.fn()}
        isSaving={false}
        onProviderChange={vi.fn()}
        providerDefaults={{}}
      />
    </QueryClientProvider>,
  );
}

describe("LlmConfigCard 模型列表获取", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("点击获取模型按钮会携带 Base URL 与 API Key 发起请求", async () => {
    fetchMock.mockImplementation((_payload, options) => options?.onSuccess?.({ models: ["m1"] }));
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: /获取模型/ }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.objectContaining({
          base_url: "https://api.example.com/v1",
          api_key: "sk-test",
        }),
        expect.objectContaining({ onSuccess: expect.any(Function) }),
      );
    });
    expect(await screen.findByText("已获取 1 个模型")).toBeInTheDocument();
  });

  it("获取失败时提示错误信息", async () => {
    fetchMock.mockImplementation((_payload, options) => options?.onError?.(new Error("上游返回 401")));
    renderCard();

    fireEvent.click(screen.getByRole("button", { name: /获取模型/ }));

    expect(await screen.findByText(/获取模型列表失败：上游返回 401/)).toBeInTheDocument();
  });

  it("子模型输入会回传 llm_sub_model", () => {
    const onChange = vi.fn();
    renderCard(onChange);

    fireEvent.change(screen.getByLabelText("子模型"), {
      target: { value: "fast-model" },
    });

    expect(onChange).toHaveBeenCalledWith({ llm_sub_model: "fast-model" });
  });

  it("点击推荐搭配会同时应用主模型与子模型", () => {
    const onChange = vi.fn();
    renderCard(onChange, { llm_provider: "deepseek" });

    const pairTag = screen.getByText(/主 deepseek-reasoner \+ 子 deepseek-chat/);
    expect(pairTag).toBeInTheDocument();
    fireEvent.click(pairTag);

    expect(onChange).toHaveBeenCalledWith({
      llm_model: "deepseek-reasoner",
      llm_sub_model: "deepseek-chat",
    });
  });

  it("点击常用子模型 Tag 快速填入该子模型", () => {
    const onChange = vi.fn();
    renderCard(onChange, { llm_provider: "deepseek" });

    const subInput = screen.getByLabelText("子模型");
    const subCol = subInput.closest(".ant-col") as HTMLElement;
    const subTag = within(subCol).getByText("deepseek-v4-flash");
    expect(subTag).toBeInTheDocument();
    fireEvent.click(subTag);

    expect(onChange).toHaveBeenCalledWith({ llm_sub_model: "deepseek-v4-flash" });
  });

  it("子模型有值时提供清空跟随主模型快捷按钮", () => {
    const onChange = vi.fn();
    renderCard(onChange, { llm_sub_model: "some-sub-model" });

    const clearButton = screen.getByRole("button", { name: "清空（跟随主模型）" });
    expect(clearButton).toBeInTheDocument();
    fireEvent.click(clearButton);

    expect(onChange).toHaveBeenCalledWith({ llm_sub_model: "" });
  });

  it("当拉取的在线模型不包含当前子模型时显示失配警告并支持一键清空", async () => {
    fetchMock.mockImplementation((_payload, options) =>
      options?.onSuccess?.({ models: ["server-model-1", "server-model-2"] }),
    );
    const onChange = vi.fn();
    renderCard(onChange, { llm_sub_model: "unknown-sub-model" });

    fireEvent.click(screen.getByRole("button", { name: /获取模型/ }));

    await waitFor(() => {
      expect(screen.getByText(/当前子模型/)).toBeInTheDocument();
    });
    expect(screen.getByText(/不在已获取的服务端模型列表中/)).toBeInTheDocument();

    const fixButton = screen.getByRole("button", { name: "改为跟随主模型" });
    fireEvent.click(fixButton);

    expect(onChange).toHaveBeenCalledWith({ llm_sub_model: "" });
  });
});
