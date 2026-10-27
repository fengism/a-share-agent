import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import IndustryAtlas from "./IndustryAtlas";

const fixtures = vi.hoisted(() => {
  const longName = "超长产业链名称".repeat(10);
  const longCategory = "超长产业分类".repeat(8);
  const longTag = "VeryLongAtlasTagWithoutNaturalBreakpoints".repeat(5);
  const longDriver = "产业驱动因素需要在窄屏和桌面端完整换行展示".repeat(6);
  const longLayer = "超长上游层级名称".repeat(8);
  const longSegment = "超长细分环节名称".repeat(8);
  const longCompany = "ContinuousUnbrokenAtlasCompanyName".repeat(6);
  const summary = {
    slug: "long-chain",
    name: longName,
    category: longCategory,
    summary: "产业链摘要".repeat(20),
    source: "mined" as const,
    aliases: [],
    tags: [longTag],
    segment_count: 1,
    company_count: 1,
  };
  const userSummary = {
    slug: "user-chain-1",
    name: "量子通信私有链",
    category: "前沿科技",
    summary: "个人私有知识库",
    source: "user" as const,
    aliases: [],
    tags: ["个人专属"],
    segment_count: 1,
    company_count: 1,
  };
  return {
    longName,
    longCategory,
    longTag,
    longDriver,
    longLayer,
    longSegment,
    longCompany,
    catalog: {
      categories: [longCategory, "前沿科技"],
      chains: [summary, userSummary],
      total_chains: 2,
      total_companies: 2,
    },
    detail: {
      ...summary,
      drivers: [longDriver],
      layers: [{
        key: "upstream" as const,
        name: longLayer,
        segments: [{
          name: longSegment,
          companies: [{ name: longCompany, code: "000001" }],
        }],
      }],
    },
  };
});

vi.mock("@ant-design/icons", () => ({
  ApartmentOutlined: () => <span />,
  AppstoreOutlined: () => <span />,
  ArrowLeftOutlined: () => <span />,
  BarsOutlined: () => <span />,
  CameraOutlined: () => <span />,
  CloudDownloadOutlined: () => <span />,
  DeleteOutlined: () => <span />,
  ExperimentOutlined: () => <span />,
  FileTextOutlined: () => <span />,
  FireOutlined: () => <span />,
  ImportOutlined: () => <span />,
  InfoCircleOutlined: () => <span />,
  NodeIndexOutlined: () => <span />,
  RobotOutlined: () => <span />,
  SearchOutlined: () => <span />,
  ShareAltOutlined: () => <span />,
  TrophyOutlined: () => <span />,
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="echarts-graph-mock" />,
}));

vi.mock("../../charts/echarts-setup", () => ({
  default: { use: vi.fn() },
}));

vi.mock("../../api/queryHooks/workflows", () => ({
  useIndustryChainAtlasCatalog: () => ({ data: fixtures.catalog, isLoading: false, isError: false }),
  useIndustryChainAtlasChain: (slug: string) => ({
    data: slug ? fixtures.detail : undefined,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useIndustryChainAtlasGraph: () => ({ data: undefined, isLoading: false, isError: false }),
  useImportIndustryChainAtlas: () => ({ mutate: vi.fn(), isPending: false }),
  useMineIndustryChainAtlas: () => ({ mutate: vi.fn(), isPending: false }),
  useBatchMineIndustryChainAtlas: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteIndustryChainAtlasChain: () => ({ mutate: vi.fn(), isPending: false }),
  downloadIndustryChainAtlasYaml: vi.fn(),
}));

vi.mock("../../store/authStore", () => ({
  useAuthStore: (selector: (state: { user: { is_admin: boolean } }) => unknown) => selector({ user: { is_admin: false } }),
}));

function renderAtlas() {
  function LocationProbe() {
    return <span data-testid="location">{useLocation().pathname}</span>;
  }

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <IndustryAtlas onAnalyze={vi.fn()} />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("IndustryAtlas long content wrapping", () => {
  it("uses shrinkable wrapping containers in catalog cards and detail nodes", () => {
    renderAtlas();

    expect(screen.getByText(fixtures.longName)).toHaveClass("atlas-chain-card__name");
    expect(screen.getAllByText(fixtures.longCategory).some((node) => node.classList.contains("atlas-wrap-tag"))).toBe(true);

    fireEvent.click(screen.getByText(fixtures.longName));

    expect(screen.getByText(fixtures.longName)).toHaveClass("atlas-detail__name");
    expect(screen.getByText(fixtures.longTag)).toHaveClass("atlas-wrap-tag");
    expect(screen.getByText(`驱动 · ${fixtures.longDriver}`)).toHaveClass("atlas-driver-chip");
    expect(screen.getByText(fixtures.longLayer)).toHaveClass("atlas-layer__name");
    expect(screen.getByText(fixtures.longSegment)).toHaveClass("atlas-segment__name");
    expect(screen.getByText(fixtures.longCompany)).toHaveClass("atlas-company-chip__name");
    expect(screen.getByText("000001")).toHaveClass("atlas-company-chip__code");

    fireEvent.click(screen.getByText(fixtures.longCompany));
    expect(screen.getByTestId("location")).toHaveTextContent("/stock/000001");

    // 切换到拓扑流向
    fireEvent.click(screen.getByText("拓扑流向"));
    expect(screen.getByTestId("echarts-graph-mock")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("在当前拓扑图中高亮公司或细分环节…")).toBeInTheDocument();
  });

  it("supports switching between catalog, global graph, and reverse lookup views", () => {
    renderAtlas();

    // 切换到全景关系图谱
    fireEvent.click(screen.getByText("全景关系图谱"));
    expect(screen.getByText("全局拓扑图谱")).toBeInTheDocument();

    // 切换到个股反查产业链
    fireEvent.click(screen.getByText("个股反查产业链"));
    expect(screen.getByText("🔍 从个股反查产业链分布")).toBeInTheDocument();
  });

  it("renders personal atlas button and allows filtering by personal exclusive chains", () => {
    renderAtlas();

    // 存在普通用户沉淀入口
    expect(screen.getByRole("button", { name: /沉淀个人图谱/ })).toBeInTheDocument();

    // 展示个人专属单选与卡片标签
    expect(screen.getByRole("radio", { name: /个人专属/ })).toBeInTheDocument();
    expect(screen.getByText("个人专属")).toBeInTheDocument();

    // 点击个人专属来源过滤
    fireEvent.click(screen.getByRole("radio", { name: /个人专属/ }));
    expect(screen.getByText("量子通信私有链")).toBeInTheDocument();
  });
});

