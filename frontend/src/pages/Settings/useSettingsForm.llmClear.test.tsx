import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { useAuthStore } from "../../store/authStore";
import type { ConfigData } from "../../types/settings";
import { PERSONAL_LLM_CLEAR_PATCH } from "./llmInheritance";
import { useSettingsForm } from "./useSettingsForm";

const config = {
  provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
  is_admin: false,
  inherited_keys: [],
  llm_provider: "deepseek",
  llm_base_url: "https://my-gw.example.com/v1",
  llm_model: "deepseek-v4-flash",
  llm_api_key: "sk-mine***view",
} as unknown as ConfigData;

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("「改用管理员配置」的提交补丁", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, username: "alice", is_admin: false, must_change_password: false },
      bootstrapped: true,
    });
  });

  it("把显式空串的个人 LLM 字段一起提交（含 Key，否则清不掉）", () => {
    const saveConfig = vi.fn();
    const { result } = renderHook(() => useSettingsForm(config, saveConfig, false), { wrapper });

    act(() => {
      result.current.cards.save("llm", PERSONAL_LLM_CLEAR_PATCH);
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toMatchObject({
      llm_provider: "",
      llm_base_url: "",
      llm_model: "",
      llm_api_key: "",
      // Literal 契约不接受空串，统一写回 auto（跟随 Provider）
      llm_api_mode: "auto",
      llm_api_version: "",
      llm_sub_model: "",
      llm_simple_tasks: "",
    });
  });

  it("回退到管理员配置时不会因缺少个人 Key 被本地校验拦住", () => {
    const saveConfig = vi.fn();
    // 表单里生效 provider 是 openai（需要 Key），个人 Key 未填
    const needsKey = { ...config, llm_provider: "openai", llm_api_key: "" } as unknown as ConfigData;
    const { result } = renderHook(() => useSettingsForm(needsKey, saveConfig, false), { wrapper });

    act(() => {
      result.current.cards.save("llm", PERSONAL_LLM_CLEAR_PATCH);
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
  });

  it("只改温度时不会把管理员的端点/模型钉成个人覆盖", () => {
    const saveConfig = vi.fn();
    const { result } = renderHook(() => useSettingsForm(config, saveConfig, false), { wrapper });

    // 表单由生效配置初始化，用户只动了温度
    act(() => {
      result.current.updateForm({ llm_temperature: 0.7 });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toEqual({ llm_temperature: 0.7 });
    // 端点/模型/provider 都还在继承，绝不能被写进个人覆盖
    expect(patch).not.toHaveProperty("llm_base_url");
    expect(patch).not.toHaveProperty("llm_model");
    expect(patch).not.toHaveProperty("llm_provider");
  });

  it("用户确实改了端点时仍然提交", () => {
    const saveConfig = vi.fn();
    const { result } = renderHook(() => useSettingsForm(config, saveConfig, false), { wrapper });

    act(() => {
      result.current.updateForm({
        llm_base_url: "https://another-gw.example.com/v1",
        llm_api_key: "sk-own",
      });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toMatchObject({
      llm_base_url: "https://another-gw.example.com/v1",
      llm_api_key: "sk-own",
    });
  });

  it("普通保存仍会拦住缺少 Key 的个人端点配置", () => {
    const saveConfig = vi.fn();
    const needsKey = { ...config, llm_provider: "openai", llm_api_key: "" } as unknown as ConfigData;
    const { result } = renderHook(() => useSettingsForm(needsKey, saveConfig, false), { wrapper });

    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).not.toHaveBeenCalled();
  });

  it("继承管理员端点与 Key 时（Provider 需 Key），只改温度正常保存不被拦截", () => {
    const saveConfig = vi.fn();
    const inheritingConfig = {
      provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
      is_admin: false,
      inherited_keys: ["llm_provider", "llm_base_url", "llm_api_key"],
      llm_provider: "openai",
      llm_base_url: "https://api.openai.com/v1",
      llm_model: "gpt-4o",
      llm_api_key: "sk-admin***secret",
    } as unknown as ConfigData;

    const { result } = renderHook(() => useSettingsForm(inheritingConfig, saveConfig, false), { wrapper });

    act(() => {
      result.current.updateForm({ llm_temperature: 0.5 });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toEqual({ llm_temperature: 0.5 });
  });

  it("继承管理员配置的用户切换到需要 Key 的新端点且未填 Key 时被拦截", () => {
    const saveConfig = vi.fn();
    const inheritingConfig = {
      provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
      is_admin: false,
      inherited_keys: ["llm_provider", "llm_base_url", "llm_api_key"],
      llm_provider: "openai",
      llm_base_url: "https://api.openai.com/v1",
      llm_model: "gpt-4o",
      llm_api_key: "sk-admin***secret",
    } as unknown as ConfigData;

    const { result } = renderHook(() => useSettingsForm(inheritingConfig, saveConfig, false), { wrapper });

    act(() => {
      // 换端点但未自备 Key
      result.current.updateForm({ llm_base_url: "https://custom-gw.example.com/v1" });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).not.toHaveBeenCalled();
  });

  it("继承管理员配置的用户只填写 Key 而未修改 URL 时被拦截", () => {
    const saveConfig = vi.fn();
    const inheritingConfig = {
      provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
      is_admin: false,
      inherited_keys: ["llm_provider", "llm_base_url", "llm_api_key"],
      llm_provider: "openai",
      llm_base_url: "https://api.openai.com/v1",
      llm_model: "gpt-4o",
      llm_api_key: "sk-admin***secret",
    } as unknown as ConfigData;

    const { result } = renderHook(() => useSettingsForm(inheritingConfig, saveConfig, false), { wrapper });

    act(() => {
      // 试图只设 Key 不改 URL
      result.current.updateForm({ llm_api_key: "sk-my-own-key" });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).not.toHaveBeenCalled();
  });

  it("不改 URL 和 Key 时单独修改模型正常保存", () => {
    const saveConfig = vi.fn();
    const inheritingConfig = {
      provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
      is_admin: false,
      inherited_keys: ["llm_provider", "llm_base_url", "llm_api_key"],
      llm_provider: "openai",
      llm_base_url: "https://api.openai.com/v1",
      llm_model: "gpt-4o",
      llm_api_key: "sk-admin***secret",
    } as unknown as ConfigData;

    const { result } = renderHook(() => useSettingsForm(inheritingConfig, saveConfig, false), { wrapper });

    act(() => {
      // 只改模型，不改 URL 和 Key
      result.current.updateForm({ llm_model: "gpt-4o-mini" });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toEqual({ llm_model: "gpt-4o-mini" });
    expect(patch).not.toHaveProperty("llm_base_url");
    expect(patch).not.toHaveProperty("llm_api_key");
  });

  it("不改 URL 和 Key 时同时修改模型与温度正常保存", () => {
    const saveConfig = vi.fn();
    const inheritingConfig = {
      provider_defaults: { openai: { label: "OpenAI", api_key_required: true } },
      is_admin: false,
      inherited_keys: ["llm_provider", "llm_base_url", "llm_api_key"],
      llm_provider: "openai",
      llm_base_url: "https://api.openai.com/v1",
      llm_model: "gpt-4o",
      llm_api_key: "sk-admin***secret",
    } as unknown as ConfigData;

    const { result } = renderHook(() => useSettingsForm(inheritingConfig, saveConfig, false), { wrapper });

    act(() => {
      result.current.updateForm({ llm_model: "gpt-4o-mini", llm_temperature: 0.2 });
    });
    act(() => {
      result.current.cards.save("llm");
    });

    expect(saveConfig).toHaveBeenCalledTimes(1);
    const [patch] = saveConfig.mock.calls[0];
    expect(patch).toEqual({ llm_model: "gpt-4o-mini", llm_temperature: 0.2 });
  });
});
