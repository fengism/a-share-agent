import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ConfigData, ConfigUpdate } from "../../types/settings";
import { useAuthStore } from "../../store/authStore";
import SettingsPage from ".";

const mocks = vi.hoisted(() => ({
  mutateConfig: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useConfig: () => ({ data: config, isLoading: false, error: null, refetch: vi.fn() }),
  useUpdateConfig: () => ({ mutate: mocks.mutateConfig, isPending: false }),
  useChatCapabilities: () => ({ data: undefined, isLoading: false, error: null, refetch: vi.fn() }),
  useChatCapabilityAvailability: () => ({ data: undefined, isFetching: false, refetch: vi.fn() }),
}));

vi.mock("./ConfigCards", () => ({
  BotConfigCard: ({ form, onSave }: { form: ConfigUpdate; onSave: () => void }) => (
    <button type="button" data-prefix={form.bot_command_prefix} onClick={onSave}>
      保存 Bot 配置
    </button>
  ),
  DataSourceCookiesCard: () => null,
  FeishuConfigCard: () => null,
  IwencaiConfigCard: () => null,
  LlmConfigCard: () => null,
  NotionConfigCard: () => null,
  ProviderDefaultsCard: () => null,
  TwitterConfigCard: () => null,
}));

vi.mock("./BotJobManagerCard", () => ({ default: () => null }));
vi.mock("./InviteManagerCard", () => ({ default: () => null }));
vi.mock("./SkillAgentConfigCard", () => ({ default: () => null }));
vi.mock("../../components/AdminResetCard", () => ({ default: () => null }));
vi.mock("../../components/ChangePasswordCard", () => ({ default: () => null }));

const config: ConfigData = {
  llm_provider: "openai",
  llm_api_mode: "openai",
  llm_api_version: "",
  llm_api_key: "",
  llm_base_url: "https://api.example.com",
  llm_model: "model",
  llm_temperature: 0.1,
  feishu_enabled: false,
  feishu_app_id: "",
  feishu_app_secret: "",
  feishu_folder_token: "",
  feishu_wiki_space_id: "",
  feishu_wiki_daily_review_parent: "",
  feishu_wiki_analysis_parent: "",
  feishu_daily_review_folder: "",
  feishu_analysis_folder: "",
  feishu_default_receiver: "",
  notion_enabled: false,
  notion_api_token: "",
  notion_parent_page_id: "",
  notion_database_id: "",
  iwencai_enabled: false,
  iwencai_base_url: "",
  iwencai_api_key: "",
  disabled_chat_skills: [],
  disabled_chat_agents: [],
  provider_defaults: {},
  twitter_feeds: [],
  eastmoney_cookie: "",
  baidu_cookie: "",
  ths_cookie: "",
  http_trust_env: false,
  eastmoney_min_interval_seconds: 0,
  eastmoney_datacenter_min_interval_seconds: 0,
  eastmoney_datacenter_cooldown_seconds: 10,
  eastmoney_jitter_min_seconds: 0,
  eastmoney_jitter_max_seconds: 0,
  eastmoney_cooldown_seconds: 0,
  eastmoney_transient_failure_threshold: 1,
  bot_enabled: true,
  bot_command_prefix: "/",
  bot_service_user_id: 7,
  bot_feishu_app_id: "cli_bot",
  bot_feishu_app_secret: "bot-***alue",
  feishu_verification_token: "verify-***oken",
  feishu_encrypt_key: "encrypt-***-key",
  bot_rate_limit_requests: 20,
  bot_rate_limit_window: 120,
  bot_webhook_max_skew_seconds: 180,
  bot_event_dedup_ttl_seconds: 900,
  bot_job_poll_seconds: 1.5,
  bot_job_lease_seconds: 600,
  bot_job_max_attempts: 4,
  bot_job_retry_base_seconds: 10,
  bot_job_worker_concurrency: 3,
  bot_batch_concurrency: 2,
  bot_batch_max_stocks: 12,
  bot_admin_users: [" ou_admin ", "", "ou_ops"],
  is_admin: true,
};

describe("SettingsPage Bot config", () => {
  afterEach(() => {
    mocks.mutateConfig.mockReset();
    act(() => useAuthStore.setState({ user: null }));
  });

  it("submits all Bot fields without writing masked secrets back", async () => {
    act(() => {
      useAuthStore.setState({
        user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
      });
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={queryClient}>
        <SettingsPage />
      </QueryClientProvider>,
    );

    const saveButton = screen.getByRole("button", { name: "保存 Bot 配置" });
    await waitFor(() => expect(saveButton).toHaveAttribute("data-prefix", "/"));
    fireEvent.click(saveButton);

    expect(mocks.mutateConfig).toHaveBeenCalledTimes(1);
    const patch = mocks.mutateConfig.mock.calls[0][0] as ConfigUpdate;
    expect(patch).toEqual({
      bot_enabled: true,
      bot_command_prefix: "/",
      bot_service_user_id: 7,
      bot_feishu_app_id: "cli_bot",
      bot_rate_limit_requests: 20,
      bot_rate_limit_window: 120,
      bot_webhook_max_skew_seconds: 180,
      bot_event_dedup_ttl_seconds: 900,
      bot_job_poll_seconds: 1.5,
      bot_job_lease_seconds: 600,
      bot_job_max_attempts: 4,
      bot_job_retry_base_seconds: 10,
      bot_job_worker_concurrency: 3,
      bot_batch_concurrency: 2,
      bot_batch_max_stocks: 12,
      bot_admin_users: ["ou_admin", "ou_ops"],
    });
    expect(patch).not.toHaveProperty("bot_feishu_app_secret");
    expect(patch).not.toHaveProperty("feishu_verification_token");
    expect(patch).not.toHaveProperty("feishu_encrypt_key");
    queryClient.clear();
  });
});
