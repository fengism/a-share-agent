import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConfigData } from "../../types/settings";
import { useAuthStore } from "../../store/authStore";
import SettingsPage from ".";

vi.mock("../../api/queries", () => ({
  useConfig: () => ({ data: config, isLoading: false, error: null, refetch: vi.fn() }),
  useTestOutboundProxy: () => ({ mutate: vi.fn(), isPending: false }),
  useTestTdxProxy: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("./useSettingsForm", () => ({
  useSettingsForm: () => ({
    form: {},
    updateForm: vi.fn(),
    dirtyFlags: { hasUnsavedChanges: false, ai: false, dataSources: false, integrations: false, admin: false },
    cards: { save: vi.fn(), reset: vi.fn(), dirty: {} },
    handleResetAllUnsaved: vi.fn(),
    handleProviderChange: vi.fn(),
  }),
}));

vi.mock("./useConfigSectionSave", () => ({
  useConfigSectionSave: () => ({ save: vi.fn(), isSaving: false }),
}));

vi.mock("./PersonalSettingsSections", () => ({
  AiSettingsSection: () => <div>AI 分区内容</div>,
  IntegrationsSettingsSection: () => <div>协同分区内容</div>,
}));

vi.mock("./AdminSettingsSections", () => ({
  DataSourcesSettingsSection: () => <div>数据源分区内容</div>,
  AdminSettingsSection: () => <div>管理员分区内容</div>,
}));

vi.mock("../../components/ChangePasswordCard", () => ({ default: () => <div>账号分区内容</div> }));
vi.mock("./SessionManagerCard", () => ({ default: () => null }));
vi.mock("./LoginHistoryCard", () => ({ default: () => null }));
vi.mock("./SystemUpdateCard", () => ({ default: () => null }));

const config = {
  is_admin: true,
  provider_defaults: {},
  inherited_keys: [],
  anysearch_api_key: "",
  fuyao_api_key: "",
} as unknown as ConfigData;

function SearchProbe() {
  const location = useLocation();
  return <output data-testid="search">{location.search}</output>;
}

const routers: ReturnType<typeof createMemoryRouter>[] = [];

/** 读取最后一次渲染的 data router 当前 URL（含查询串） */
function currentSearch() {
  const router = routers[routers.length - 1];
  return router?.state.location.search ?? "";
}

function renderPage(initialEntry: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // data router：设置页的离开拦截依赖 useBlocker，只有 data router 提供
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element: (
          <>
            <SettingsPage />
            <SearchProbe />
          </>
        ),
      },
    ],
    { initialEntries: [initialEntry] },
  );
  routers.push(router);
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return currentSearch;
}

describe("SettingsPage section URL state", () => {
  beforeEach(() => {
    routers.length = 0;
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
    });
  });

  it("restores the section from ?section= on first render", async () => {
    renderPage("/settings?section=admin");

    expect(await screen.findByText("管理员分区内容")).toBeVisible();
    // 访问过的分区会保留在 DOM 中（preserveVisited），但非当前分区不可见
    expect(screen.queryByText("账号分区内容")).not.toBeVisible();
  });

  it("writes the active section into the URL and drops the default one", async () => {
    const search = renderPage("/settings");

    expect(await screen.findByText("账号分区内容")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /AI 模型配置/ }));
    await waitFor(() => {
      expect(search()).toBe("?section=ai");
    });

    fireEvent.click(screen.getByRole("button", { name: /账号与安全/ }));
    await waitFor(() => {
      expect(search()).toBe("");
    });
  });

  it("falls back to the default section for an unknown ?section= value", async () => {
    renderPage("/settings?section=unknown");

    expect(await screen.findByText("账号分区内容")).toBeInTheDocument();
  });
});
