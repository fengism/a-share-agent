import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
};

function renderCard() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LlmConfigCard
        form={baseForm}
        onChange={vi.fn()}
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
});
