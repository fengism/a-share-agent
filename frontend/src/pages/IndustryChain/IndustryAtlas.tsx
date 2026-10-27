import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApartmentOutlined,
  AppstoreOutlined,
  ArrowLeftOutlined,
  BarsOutlined,
  CameraOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FireOutlined,
  ImportOutlined,
  InfoCircleOutlined,
  NodeIndexOutlined,
  RobotOutlined,
  SearchOutlined,
  ShareAltOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Popover,
  Popconfirm,
  Radio,
  Row,
  Segmented,
  Select,
  Spin,
  Switch,
  Tag,
  message,
} from "antd";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import {
  downloadIndustryChainAtlasYaml,
  useDeleteIndustryChainAtlasChain,
  useImportIndustryChainAtlas,
  useIndustryChainAtlasCatalog,
  useIndustryChainAtlasChain,
  useIndustryChainAtlasGraph,
} from "../../api/queryHooks/workflows";
import { queryKeys } from "../../api/queryKeys";
import { useAuthStore } from "../../store/authStore";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import type {
  AtlasChain,
  AtlasHubCompany,
} from "../../types/stock";
import QueryErrorState from "../../components/QueryErrorState";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import { AtlasBatchMineModal } from "./atlas/AtlasBatchMineModal";
import { AtlasImportModal } from "./atlas/AtlasImportModal";
import { AtlasLayerBand } from "./atlas/AtlasLayerBand";
import { AtlasMineModal } from "./atlas/AtlasMineModal";
import { CategoryChip } from "./atlas/CategoryChip";
import { LAYER_COLORS, LAYER_NAMES } from "./atlas/constants";

interface IndustryAtlasProps {
  onAnalyze: (name: string) => void;
}

export default function IndustryAtlas({ onAnalyze }: IndustryAtlasProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false);
  const isMobile = useMediaQuery("(max-width: 576px)");

  const [activeView, setActiveView] = useState<"catalog" | "graph" | "reverse">("catalog");
  const [selectedSlug, setSelectedSlug] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [reverseStockKeyword, setReverseStockKeyword] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [mineOpen, setMineOpen] = useState(false);
  const [batchMineOpen, setBatchMineOpen] = useState(false);

  const catalogQuery = useIndustryChainAtlasCatalog();
  const chainQuery = useIndustryChainAtlasChain(selectedSlug);
  const graphQuery = useIndustryChainAtlasGraph();
  const importMutation = useImportIndustryChainAtlas();
  const deleteMutation = useDeleteIndustryChainAtlasChain();
  const catalog = catalogQuery.data;
  const graphData = graphQuery.data;

  // 用户个人专属图谱统计
  const userChainsCount = useMemo(
    () => catalog?.chains.filter((c) => c.source === "user").length ?? 0,
    [catalog],
  );

  // 产业链目录过滤
  const filteredChains = useMemo(() => {
    if (!catalog) return [];
    const keyword = search.trim().toLowerCase();
    return catalog.chains.filter((chain) => {
      if (category && chain.category !== category) return false;
      if (sourceFilter !== "all" && chain.source !== sourceFilter) return false;
      if (!keyword) return true;
      return (
        chain.name.toLowerCase().includes(keyword) ||
        chain.summary.toLowerCase().includes(keyword) ||
        (chain.aliases ?? []).some((alias) => alias.toLowerCase().includes(keyword)) ||
        (chain.tags ?? []).some((tag) => tag.toLowerCase().includes(keyword))
      );
    });
  }, [catalog, category, search, sourceFilter]);

  // 股票反查产业链匹配
  const reverseMatchedChains = useMemo(() => {
    if (!graphData || !reverseStockKeyword.trim()) return [];
    const kw = reverseStockKeyword.trim().toLowerCase();
    const matchedNodes = graphData.nodes.filter(
      (n) => n.name.toLowerCase().includes(kw) || n.id.includes(kw)
    );
    return matchedNodes;
  }, [graphData, reverseStockKeyword]);

  // 查看单条链详情
  if (selectedSlug) {
    return (
      <div>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => setSelectedSlug("")}
          style={{ marginBottom: 12, color: colors.textSecondary }}
        >
          返回知识库
        </Button>
        {chainQuery.isLoading && (
          <div style={{ ...cardStyle, padding: 60, textAlign: "center" }}>
            <Spin />
            <div style={{ marginTop: 12, color: colors.textMuted }}>正在加载产业链图谱…</div>
          </div>
        )}
        {chainQuery.isError && (
          <QueryErrorState
            error={chainQuery.error}
            onRetry={() => chainQuery.refetch()}
          />
        )}
        {chainQuery.data && (
          <ChainAtlasDetail
            chain={chainQuery.data}
            onAnalyze={onAnalyze}
            onCompanyClick={(code) => navigate(buildStockProfileUrl(code))}
            onDeleteSuccess={() => setSelectedSlug("")}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      {/* 头部控制栏：模式切换、自动挖掘状态与管理操作 */}
      <div style={{ ...cardStyle, padding: isMobile ? "12px 14px" : "16px 20px", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ width: isMobile ? "100%" : "auto" }}>
            <Segmented
              block={isMobile}
              value={activeView}
              onChange={(val) => setActiveView(val as "catalog" | "graph" | "reverse")}
              options={[
                { label: isMobile ? "目录" : "知识库目录", value: "catalog", icon: <AppstoreOutlined /> },
                { label: isMobile ? "全景图谱" : "全景关系图谱", value: "graph", icon: <ShareAltOutlined /> },
                { label: isMobile ? "个股反查" : "个股反查产业链", value: "reverse", icon: <NodeIndexOutlined /> },
              ]}
            />
          </div>

          {activeView === "catalog" && (
            <Input
              allowClear
              prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
              placeholder="搜索产业链、标签或别名…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              style={{ width: isMobile ? "100%" : 260, maxWidth: "100%" }}
            />
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
              {catalog
                ? `${catalog.total_chains} 条产业链 · ${catalog.total_companies} 家核心公司`
                : "加载中…"}
            </span>

            <Popover
              title="产业链知识库与自动挖掘机制"
              content={
                <div style={{ maxWidth: 360, fontSize: "var(--c-font-sm)", lineHeight: 1.6 }}>
                  <p style={{ margin: "0 0 8px" }}>
                    <b>AI 自动挖掘已启用</b>：每次执行产业链深度研究并生成分析报告后，后台将自动提取上中下游企业节点与所属环节。
                  </p>
                  <p style={{ margin: "0 0 8px" }}>
                    <b>双向核验防幻觉</b>：公司名称与股票代码必须完全通过 A 股官方名录校验才允许入库，防止模型幻觉污染知识库。
                  </p>
                  <p style={{ margin: "0 0 8px" }}>
                    <b>质量门禁与更新</b>：仅通过质量校验且具备完整环节与标的之报告才沉淀为知识库，同名链条稳定覆盖更新。
                  </p>
                  <p style={{ margin: 0, color: colors.textMuted }}>
                    知识库条目后续在同主题分析时将作为先验证据输入模型，形成持续演进的正向反馈闭环。
                  </p>
                </div>
              }
            >
              <Tag
                icon={<RobotOutlined />}
                color="cyan"
                style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}
              >
                {isMobile ? "AI 挖掘已开" : "自动挖掘已开启"} <InfoCircleOutlined style={{ fontSize: 11 }} />
              </Tag>
            </Popover>
          </div>

          <div style={{ marginLeft: isMobile ? 0 : "auto", width: isMobile ? "100%" : "auto", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <Button
              icon={<CloudDownloadOutlined />}
              size={isMobile ? "small" : "middle"}
              onClick={() => setMineOpen(true)}
            >
              {isAdmin ? "从分析挖掘" : "沉淀个人图谱"}
            </Button>
            <Button
              icon={<ImportOutlined />}
              size={isMobile ? "small" : "middle"}
              onClick={() => setImportOpen(true)}
            >
              {isAdmin ? "导入产业链" : "导入私有产业链"}
            </Button>
            {isAdmin && (
              <Button
                icon={<RobotOutlined />}
                size={isMobile ? "small" : "middle"}
                onClick={() => setBatchMineOpen(true)}
              >
                {isMobile ? "批量挖掘" : "批量挖掘历史研报"}
              </Button>
            )}
          </div>
        </div>

        {/* 目录视图：分类与来源标签 */}
        {activeView === "catalog" && catalog && (
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginRight: 4 }}>
                分类:
              </span>
              <CategoryChip
                label="全部"
                active={!category}
                colors={colors}
                onClick={() => setCategory("")}
              />
              {catalog.categories.map((item) => (
                <CategoryChip
                  key={item}
                  label={item}
                  active={category === item}
                  colors={colors}
                  onClick={() => setCategory(category === item ? "" : item)}
                />
              ))}
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted, marginRight: 4 }}>
                来源:
              </span>
              <Radio.Group
                size="small"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                <Radio.Button value="all">全部来源</Radio.Button>
                <Radio.Button value="user">
                  个人专属{userChainsCount > 0 ? ` (${userChainsCount})` : ""}
                </Radio.Button>
                <Radio.Button value="builtin">内置策划</Radio.Button>
                <Radio.Button value="mined">AI 自动挖掘</Radio.Button>
                <Radio.Button value="imported">外部导入</Radio.Button>
              </Radio.Group>
            </div>
          </div>
        )}
      </div>

      {/* 视图内容分发 */}
      {activeView === "reverse" ? (
        <AtlasReverseLookup
          keyword={reverseStockKeyword}
          onKeywordChange={setReverseStockKeyword}
          matchedNodes={reverseMatchedChains}
          chainIndex={graphData?.chain_index ?? {}}
          onSelectChain={(slug) => setSelectedSlug(slug)}
          onCompanyClick={(code) => navigate(buildStockProfileUrl(code))}
        />
      ) : activeView === "graph" ? (
        <AtlasGlobalGraph
          catalog={catalog}
          onCompanyClick={(code) => navigate(buildStockProfileUrl(code))}
          onSelectChain={(slug) => setSelectedSlug(slug)}
        />
      ) : (
        <>
          {catalogQuery.isLoading && (
            <div style={{ ...cardStyle, padding: 60, textAlign: "center" }}>
              <Spin />
              <div style={{ marginTop: 12, color: colors.textMuted }}>正在加载产业链知识库…</div>
            </div>
          )}
          {catalogQuery.isError && (
            <QueryErrorState
              error={catalogQuery.error}
              onRetry={() => catalogQuery.refetch()}
            />
          )}
          {catalog && filteredChains.length === 0 && (
            <div style={{ ...cardStyle, padding: 40, textAlign: "center" }}>
              {sourceFilter === "user" ? (
                <Empty
                  description={
                    <div style={{ maxWidth: 420, margin: "0 auto", lineHeight: "1.8" }}>
                      <p style={{ fontWeight: 500, marginBottom: 4 }}>暂无个人专属图谱</p>
                      <span style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)" }}>
                        您可以从已有的产业链分析研报中点击「沉淀到知识库」，或直接通过上方按钮导入 YAML 文件建立您的私有知识库。
                      </span>
                    </div>
                  }
                >
                  <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 12 }}>
                    <Button type="primary" icon={<CloudDownloadOutlined />} onClick={() => setMineOpen(true)}>
                      沉淀个人图谱
                    </Button>
                    <Button icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>
                      导入私有产业链
                    </Button>
                  </div>
                </Empty>
              ) : (
                <Empty description="没有匹配的产业链" />
              )}
            </div>
          )}
          {catalog && filteredChains.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))",
                gap: isMobile ? 10 : 14,
              }}
            >
              {filteredChains.map((chain) => (
                <div
                  key={chain.slug}
                  className="atlas-chain-card"
                  style={{
                    ...cardStyle,
                    padding: isMobile ? "12px 14px" : "16px 18px",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    borderColor: chain.source === "user" ? "rgba(114, 46, 209, 0.4)" : undefined,
                    background:
                      chain.source === "user"
                        ? "linear-gradient(180deg, rgba(114, 46, 209, 0.05), transparent 70%)"
                        : undefined,
                  }}
                  onClick={() => setSelectedSlug(chain.slug)}
                >
                  <div
                    className="atlas-chain-card__heading"
                    style={{ display: "flex", alignItems: "center", gap: 8 }}
                  >
                    <span
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: `linear-gradient(135deg, ${colors.primary}26, ${colors.accent}26)`,
                        color: colors.primary,
                        flexShrink: 0,
                      }}
                    >
                      <ApartmentOutlined />
                    </span>
                    <strong
                      className="atlas-chain-card__name"
                      style={{ fontSize: "var(--c-font-lg)", color: colors.textPrimary }}
                    >
                      {chain.name}
                    </strong>
                    {chain.source === "user" && <Tag color="purple">个人专属</Tag>}
                    {chain.source === "mined" && <Tag color="processing">AI 挖掘</Tag>}
                    {chain.source === "imported" && <Tag color="gold">外部导入</Tag>}
                    <Tag className="atlas-wrap-tag" style={{ marginLeft: "auto" }}>
                      {chain.category}
                    </Tag>
                  </div>
                  <div
                    className="atlas-chain-card__summary"
                    style={{
                      color: colors.textSecondary,
                      fontSize: "var(--c-font-md)",
                      lineHeight: "var(--c-leading-normal)",
                      flex: 1,
                    }}
                  >
                    {chain.summary}
                  </div>
                  <div
                    className="atlas-chain-card__stats"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      fontSize: "var(--c-font-sm)",
                      color: colors.textMuted,
                    }}
                  >
                    <span>{chain.segment_count} 个环节</span>
                    <span>·</span>
                    <span>{chain.company_count} 家公司</span>
                    {((isAdmin && (chain.source === "imported" || chain.source === "mined")) || chain.source === "user") && (
                      <Popconfirm
                        title="删除这条产业链？"
                        onConfirm={(event) => {
                          event?.stopPropagation();
                          deleteMutation.mutate(chain.slug, {
                            onSuccess: async () => {
                              message.success(`已删除产业链：${chain.name}`);
                              await queryClient.invalidateQueries({
                                queryKey: queryKeys.workflows.industryChainAtlasCatalog,
                              });
                              await queryClient.invalidateQueries({
                                queryKey: ["industryChainAtlas", "graph"],
                              });
                            },
                            onError: (error: Error) => message.error(error.message),
                          });
                        }}
                        onCancel={(event) => event?.stopPropagation()}
                      >
                        <Button
                          danger
                          type="text"
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={(event) => event.stopPropagation()}
                        />
                      </Popconfirm>
                    )}
                    <Button
                      type="link"
                      size="small"
                      icon={<ExperimentOutlined />}
                      style={{
                        marginLeft: isAdmin && chain.source !== "builtin" ? 0 : "auto",
                        padding: 0,
                        height: "auto",
                      }}
                      onClick={(event) => {
                        event.stopPropagation();
                        onAnalyze(chain.name);
                      }}
                    >
                      AI 深度分析
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* 导入与挖掘模态框 */}
      <AtlasImportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        importing={importMutation.isPending}
        onSubmit={(content, overwrite) => {
          importMutation.mutate(
            { content, overwrite },
            {
              onSuccess: async (chains) => {
                message.success(`导入成功：${chains.map((chain) => chain.name).join("、")}`);
                setImportOpen(false);
                await queryClient.invalidateQueries({
                  queryKey: queryKeys.workflows.industryChainAtlasCatalog,
                });
                await queryClient.invalidateQueries({
                  queryKey: ["industryChainAtlas", "graph"],
                });
              },
              onError: (error: Error) =>
                message.error({
                  content: error.message,
                  duration: 8,
                }),
            },
          );
        }}
      />

      {isAdmin && (
        <AtlasBatchMineModal
          open={batchMineOpen}
          onClose={() => setBatchMineOpen(false)}
          onSuccess={async () => {
            await queryClient.invalidateQueries({
              queryKey: queryKeys.workflows.industryChainAtlasCatalog,
            });
            await queryClient.invalidateQueries({
              queryKey: ["industryChainAtlas", "graph"],
            });
          }}
        />
      )}

      <AtlasMineModal
        open={mineOpen}
        onClose={() => setMineOpen(false)}
        onSuccess={async () => {
          setMineOpen(false);
          await queryClient.invalidateQueries({
            queryKey: queryKeys.workflows.industryChainAtlasCatalog,
          });
          await queryClient.invalidateQueries({
            queryKey: ["industryChainAtlas", "graph"],
          });
        }}
      />
    </div>
  );
}

// ── 模式：个股反查产业链 ──────────────────────────────────────────────────────

function AtlasReverseLookup({
  keyword,
  onKeywordChange,
  matchedNodes,
  chainIndex,
  onSelectChain,
  onCompanyClick,
}: {
  keyword: string;
  onKeywordChange: (val: string) => void;
  matchedNodes: NonNullable<ReturnType<typeof useIndustryChainAtlasGraph>["data"]>["nodes"];
  chainIndex: Record<string, string>;
  onSelectChain: (slug: string) => void;
  onCompanyClick: (code: string) => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isMobile = useMediaQuery("(max-width: 576px)");

  return (
    <Card style={cardStyle} bodyStyle={{ padding: isMobile ? "14px 16px" : 20 }}>
      <div style={{ maxWidth: 600, marginBottom: 16 }}>
        <h3 style={{ fontSize: isMobile ? "var(--c-font-base)" : "var(--c-font-lg)", marginBottom: 8, color: colors.textPrimary }}>
          🔍 从个股反查产业链分布
        </h3>
        <p style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)", marginBottom: 12 }}>
          输入股票代码（如 002371）或企业名称（如 北方华创、中科创达），即可穿透查看该企业在全市场知识库中参与的所有产业链、所属上中下游及具体细分环节。
        </p>
        <Input
          allowClear
          prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
          placeholder="输入股票代码或名称，如：中科创达、300496、宁德时代"
          value={keyword}
          onChange={(e) => onKeywordChange(e.target.value)}
          size={isMobile ? "middle" : "large"}
        />
      </div>

      {!keyword.trim() ? (
        <div style={{ textAlign: "center", padding: "40px 0", color: colors.textMuted }}>
          请输入股票代码或名称开始反查
        </div>
      ) : matchedNodes.length === 0 ? (
        <Empty description="未在现有产业链知识库中检索到该股票" />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {matchedNodes.map((node) => (
            <div
              key={node.id}
              style={{
                border: `1px solid ${colors.border}`,
                borderRadius: 10,
                background: colors.nestedBg,
                padding: isMobile ? "12px 14px" : "16px 20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                <span
                  style={{
                    fontSize: isMobile ? "var(--c-font-lg)" : "var(--c-font-xl)",
                    fontWeight: 600,
                    color: colors.textPrimary,
                    cursor: "pointer",
                  }}
                  onClick={() => onCompanyClick(node.id)}
                >
                  {node.name}
                </span>
                <Tag color="blue" style={{ fontSize: 12, cursor: "pointer" }} onClick={() => onCompanyClick(node.id)}>
                  {node.id}
                </Tag>
                <Tag color={node.layer === "upstream" ? "orange" : node.layer === "midstream" ? "blue" : "green"}>
                  主要层级: {LAYER_NAMES[node.layer] || node.layer}
                </Tag>
                <span style={{ fontSize: "var(--c-font-xs)", color: colors.textMuted, marginLeft: isMobile ? 0 : "auto", width: isMobile ? "100%" : "auto" }}>
                  覆盖 <b>{node.chain_count}</b> 条产业链 · {node.segments.length} 个环节
                </span>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-sm)", color: colors.textSecondary }}>所属产业链：</span>
                {node.chains.map((slug) => {
                  const chainName = chainIndex[slug] || slug;
                  return (
                    <Button
                      key={slug}
                      size="small"
                      type="dashed"
                      icon={<ApartmentOutlined />}
                      onClick={() => onSelectChain(slug)}
                    >
                      {chainName}
                    </Button>
                  );
                })}
              </div>

              {node.segments.length > 0 && (
                <div style={{ marginTop: 10, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
                  细分环节：{node.segments.join("、")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── 模式：全局跨链图谱与枢纽龙头榜 ──────────────────────────────────────────────

function AtlasGlobalGraph({
  catalog,
  onCompanyClick,
  onSelectChain,
}: {
  catalog: ReturnType<typeof useIndustryChainAtlasCatalog>["data"];
  onCompanyClick: (code: string) => void;
  onSelectChain: (slug: string) => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const chartRef = useRef<ReactEChartsCore | null>(null);
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const isMobile = useMediaQuery("(max-width: 576px)");

  const [graphTab, setGraphTab] = useState<"topology" | "hubs" | "synergy">("topology");
  const [selectedChains, setSelectedChains] = useState<string[]>([]);
  const [layerFilter, setLayerFilter] = useState<string>("all");
  const [nodeSearch, setNodeSearch] = useState("");
  const [onlyHubs, setOnlyHubs] = useState(false);

  const chainFilterParam = selectedChains.length > 0 ? selectedChains.join(",") : undefined;
  const graphQuery = useIndustryChainAtlasGraph(chainFilterParam);
  const graphData = graphQuery.data;

  const handleExportImage = () => {
    const chart = chartRef.current?.getEchartsInstance?.();
    if (!chart) return;
    const url = chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: colors.cardBg,
    });
    const link = document.createElement("a");
    link.download = "A股产业链全景关系图谱.png";
    link.href = url;
    link.click();
  };

  const chainOptions = useMemo(() => {
    if (!catalog) return [];
    return catalog.chains.map((c) => ({
      label: `${c.name} (${c.company_count}家)`,
      value: c.slug,
    }));
  }, [catalog]);

  const chartOption = useMemo(() => {
    if (!graphData) return {};

    const searchKeyword = nodeSearch.trim().toLowerCase();

    // 过滤层级与枢纽标的
    const visibleNodes = graphData.nodes.filter((node) => {
      if (layerFilter !== "all" && node.layer !== layerFilter) return false;
      if (onlyHubs && node.chain_count < 2) return false;
      return true;
    });

    const visibleNodeIds = new Set(visibleNodes.map((n) => n.id));

    const nodes = visibleNodes.map((node) => {
      const color = LAYER_COLORS[node.layer] || colors.primary;
      const isMatch =
        searchKeyword &&
        (node.name.toLowerCase().includes(searchKeyword) || node.id.includes(searchKeyword));
      const minSz = isNarrow ? 16 : 20;
      const step = isNarrow ? 5 : 8;
      const maxSz = isNarrow ? 36 : 44;
      const baseSize = Math.max(minSz, Math.min(minSz - 2 + node.chain_count * step, maxSz));
      const symbolSize = isMatch ? baseSize * 1.35 : baseSize;

      return {
        id: node.id,
        name: node.name,
        symbolSize,
        category: node.layer,
        value: node.chain_count,
        itemStyle: {
          color,
          borderColor: isMatch ? colors.accent : colors.cardBg,
          borderWidth: isMatch ? 3 : 1.5,
          shadowColor: isMatch ? `${colors.accent}90` : `${color}30`,
          shadowBlur: isMatch ? 14 : 5,
        },
        label: {
          show: true,
          position: "bottom",
          color: isMatch ? colors.primary : colors.textSecondary,
          fontWeight: isMatch ? "bold" : "normal",
          fontSize: isNarrow ? 10 : 11,
          formatter: "{b}",
        },
        rawNode: node,
      };
    });

    const edges = graphData.edges
      .filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
      .map((edge) => ({
        source: edge.source,
        target: edge.target,
        chain_name: edge.chain_name,
        lineStyle: {
          color: colors.border,
          width: 1.2,
          curveness: 0.15,
          opacity: 0.5,
        },
      }));

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: colors.cardBg,
        borderColor: colors.border,
        textStyle: { color: colors.textPrimary },
        formatter: (params: { dataType?: string; name?: string; data?: { rawNode?: { layer: string; chains: string[]; name: string; id: string; segments: string[]; chain_count: number }; chain_name?: string } }) => {
          if (params.dataType === "node") {
            const raw = params.data?.rawNode;
            if (!raw) return params.name || "";
            const layerName = LAYER_NAMES[raw.layer] || raw.layer || "产业环节";
            const chainNames = raw.chains
              .map((slug: string) => graphData.chain_index[slug] || slug)
              .join("、");
            return `
              <div style="font-weight:600;font-size:14px;margin-bottom:4px;color:${colors.textPrimary};">
                ${raw.name} <span style="font-size:12px;color:${colors.textMuted};">(${raw.id})</span>
              </div>
              <div style="font-size:12px;color:${colors.textSecondary};margin-bottom:2px;">
                产业链层级：<b style="color:${LAYER_COLORS[raw.layer] || colors.primary};">${layerName}</b>
              </div>
              ${raw.segments.length > 0 ? `<div style="font-size:12px;color:${colors.textSecondary};margin-bottom:2px;">覆盖环节：${raw.segments.join("、")}</div>` : ""}
              <div style="font-size:12px;color:${colors.textSecondary};margin-bottom:4px;">
                跨链分布 (${raw.chain_count})：${chainNames}
              </div>
              <div style="font-size:11px;color:${colors.primary};margin-top:6px;">
                💡 点击节点直接跳转个股主页
              </div>
            `;
          }
          if (params.dataType === "edge") {
            const edge = params.data;
            return `<div style="font-size:12px;color:${colors.textPrimary};">产业链传导连接：<b>${edge?.chain_name || ""}</b></div>`;
          }
          return "";
        },
      },
      legend: {
        top: isMobile ? 8 : 12,
        left: isMobile ? 8 : 16,
        orient: "horizontal",
        data: [
          { name: "upstream", itemStyle: { color: LAYER_COLORS.upstream } },
          { name: "midstream", itemStyle: { color: LAYER_COLORS.midstream } },
          { name: "downstream", itemStyle: { color: LAYER_COLORS.downstream } },
        ],
        formatter: (name: string) => LAYER_NAMES[name] || name,
        textStyle: { color: colors.textSecondary, fontSize: isNarrow ? 10 : 12 },
      },
      series: [
        {
          type: "graph",
          layout: "force",
          force: {
            repulsion: isNarrow ? 160 : 220,
            edgeLength: isNarrow ? [40, 110] : [60, 160],
            gravity: 0.08,
            friction: 0.65,
          },
          roam: true,
          draggable: true,
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: [4, 8],
          data: nodes,
          links: edges,
          categories: [
            { name: "upstream" },
            { name: "midstream" },
            { name: "downstream" },
          ],
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 2.8,
              opacity: 0.9,
            },
          },
        },
      ],
    };
  }, [graphData, layerFilter, nodeSearch, onlyHubs, colors, isNarrow, isMobile]);

  const onChartClick = (params: { dataType?: string; data?: { id?: string } }) => {
    if (params.dataType === "node" && params.data?.id) {
      onCompanyClick(params.data.id);
    }
  };

  return (
    <Card style={cardStyle} bodyStyle={{ padding: isMobile ? 12 : 18 }}>
      {/* 子标签：力导向图谱 / 跨链枢纽龙头榜 / 产业协同矩阵 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div style={{ width: isMobile ? "100%" : "auto" }}>
          <Segmented
            block={isMobile}
            value={graphTab}
            onChange={(v) => setGraphTab(v as "topology" | "hubs" | "synergy")}
            options={[
              { label: isMobile ? "全景拓扑" : "全局拓扑图谱", value: "topology", icon: <ShareAltOutlined /> },
              { label: isMobile ? "枢纽龙头" : "跨链枢纽龙头榜", value: "hubs", icon: <TrophyOutlined /> },
              { label: isMobile ? "协同矩阵" : "产业协同共振矩阵", value: "synergy", icon: <FireOutlined /> },
            ]}
          />
        </div>

        {graphData && (
          <div style={{ fontSize: "var(--c-font-xs)", color: colors.textMuted }}>
            <span>已合并 <b>{graphData.summary.total_nodes}</b> 家公司</span>
            <span style={{ margin: "0 6px" }}>·</span>
            <span><b>{graphData.summary.total_edges}</b> 条传导关系</span>
            <span style={{ margin: "0 6px" }}>·</span>
            <span>覆盖 <b>{graphData.summary.total_chains}</b> 条产业链</span>
          </div>
        )}
      </div>

      {graphTab === "topology" && (
        <>
          {/* 筛选过滤工具栏 */}
          <div
            style={{
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              alignItems: "center",
              marginBottom: 12,
            }}
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="筛选特定产业链（默认展示全部）"
              style={{ width: isNarrow ? "100%" : undefined, minWidth: isNarrow ? "100%" : 220, flex: 1, maxWidth: isNarrow ? "100%" : 440 }}
              value={selectedChains}
              onChange={setSelectedChains}
              options={chainOptions}
              maxTagCount="responsive"
            />

            <Radio.Group
              size="small"
              value={layerFilter}
              onChange={(e) => setLayerFilter(e.target.value)}
            >
              <Radio.Button value="all">全层级</Radio.Button>
              <Radio.Button value="upstream">{isNarrow ? "上游" : "仅上游"}</Radio.Button>
              <Radio.Button value="midstream">{isNarrow ? "中游" : "仅中游"}</Radio.Button>
              <Radio.Button value="downstream">{isNarrow ? "下游" : "仅下游"}</Radio.Button>
            </Radio.Group>

            <Input
              allowClear
              prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
              placeholder="高亮公司代码或名称…"
              style={{ width: isNarrow ? "100%" : 190 }}
              value={nodeSearch}
              onChange={(e) => setNodeSearch(e.target.value)}
            />

            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: isMobile ? "100%" : "auto", gap: 10 }}>
              <Switch
                checkedChildren="仅跨链枢纽"
                unCheckedChildren="全部标的"
                checked={onlyHubs}
                onChange={setOnlyHubs}
              />

              <Button
                icon={<CameraOutlined />}
                size="small"
                onClick={handleExportImage}
              >
                导出全景图
              </Button>
            </div>
          </div>

          {graphQuery.isLoading && (
            <div style={{ height: isNarrow ? 360 : 600, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Spin tip="正在构建全局产业链图谱…" />
            </div>
          )}

          {graphQuery.isError && (
            <QueryErrorState error={graphQuery.error} onRetry={() => graphQuery.refetch()} />
          )}

          {graphData && graphData.nodes.length === 0 && (
            <div style={{ height: 320, display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Empty description="所选产业链中未包含公司节点" />
            </div>
          )}

          {graphData && graphData.nodes.length > 0 && (
            <div
              style={{
                height: isNarrow ? 420 : 640,
                position: "relative",
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
              }}
            >
              <ReactEChartsCore
                ref={chartRef}
                echarts={echarts}
                option={chartOption}
                notMerge
                onEvents={{ click: onChartClick }}
                style={{ width: "100%", height: "100%" }}
              />
              <div
                style={{
                  position: "absolute",
                  bottom: 12,
                  right: 16,
                  fontSize: "var(--c-font-xs)",
                  color: colors.textMuted,
                  pointerEvents: "none",
                }}
              >
                支持鼠标滚轮缩放与拖拽画布 · 节点尺寸随跨链协同度动态缩放
              </div>
            </div>
          )}
        </>
      )}

      {graphTab === "hubs" && (
        <HubCompaniesRanking
          hubCompanies={graphData?.hub_companies ?? []}
          onCompanyClick={onCompanyClick}
          onSelectChain={onSelectChain}
        />
      )}

      {graphTab === "synergy" && (
        <ChainSynergyMatrix
          synergies={graphData?.chain_synergies ?? []}
          onSelectChain={onSelectChain}
        />
      )}
    </Card>
  );
}

// ── 跨链枢纽龙头排行榜组件 ────────────────────────────────────────────────────

function HubCompaniesRanking({
  hubCompanies,
  onCompanyClick,
  onSelectChain,
}: {
  hubCompanies: AtlasHubCompany[];
  onCompanyClick: (code: string) => void;
  onSelectChain: (slug: string) => void;
}) {
  const colors = useColors();

  if (hubCompanies.length === 0) {
    return <Empty description="暂无跨足多条产业链的枢纽龙头" style={{ padding: 40 }} />;
  }

  return (
    <div>
      <div style={{ marginBottom: 12, color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
        💡 <b>跨链枢纽标的</b>：跨足 2 条及以上结构性高景气产业链的平台型或核心龙头企业，具备极强的跨产业抗周期与协同共振特征。
      </div>

      <Row gutter={[12, 12]}>
        {hubCompanies.map((comp, idx) => (
          <Col xs={24} sm={12} md={8} key={comp.id}>
            <div
              style={{
                border: `1px solid ${colors.border}`,
                borderRadius: 10,
                background: colors.nestedBg,
                padding: "12px 14px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <span
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    background: idx < 3 ? colors.primary : `${colors.primary}26`,
                    color: idx < 3 ? "#fff" : colors.primary,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                  }}
                >
                  {idx + 1}
                </span>
                <strong
                  style={{ fontSize: "var(--c-font-base)", color: colors.textPrimary, cursor: "pointer" }}
                  onClick={() => onCompanyClick(comp.id)}
                >
                  {comp.name}
                </strong>
                <Tag color="blue" style={{ cursor: "pointer", fontSize: 11 }} onClick={() => onCompanyClick(comp.id)}>
                  {comp.id}
                </Tag>
                <Tag color="purple" style={{ marginLeft: "auto", fontSize: 11 }}>
                  跨 {comp.chain_count} 链
                </Tag>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {comp.chains.map((slug, i) => (
                  <Tag
                    key={slug}
                    color="cyan"
                    style={{ cursor: "pointer", fontSize: 11 }}
                    onClick={() => onSelectChain(slug)}
                  >
                    {comp.chain_names[i] || slug}
                  </Tag>
                ))}
              </div>

              {comp.segments.length > 0 && (
                <div style={{ fontSize: "var(--c-font-xs)", color: colors.textMuted }}>
                  环节：{comp.segments.slice(0, 3).join("、")}
                </div>
              )}
            </div>
          </Col>
        ))}
      </Row>
    </div>
  );
}

// ── 产业协同共振矩阵组件 ────────────────────────────────────────────────────────

function ChainSynergyMatrix({
  synergies,
  onSelectChain,
}: {
  synergies: NonNullable<ReturnType<typeof useIndustryChainAtlasGraph>["data"]>["chain_synergies"];
  onSelectChain: (slug: string) => void;
}) {
  const colors = useColors();

  if (!synergies || synergies.length === 0) {
    return <Empty description="暂无跨产业链共现协同分析数据" style={{ padding: 40 }} />;
  }

  return (
    <div>
      <div style={{ marginBottom: 12, color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
        ⚡ <b>跨产业链协同共振</b>：两两产业之间共有供应链企业越多，表明产业间的需求协同、技术传导与共振效应越强。
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {synergies.map((s) => (
          <div
            key={`${s.source_slug}-${s.target_slug}`}
            style={{
              border: `1px solid ${colors.border}`,
              borderRadius: 8,
              background: colors.nestedBg,
              padding: "12px 14px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Button type="link" style={{ padding: 0 }} onClick={() => onSelectChain(s.source_slug)}>
                <b>{s.source_name}</b>
              </Button>
              <span style={{ color: colors.accent, fontWeight: 700 }}>⇄</span>
              <Button type="link" style={{ padding: 0 }} onClick={() => onSelectChain(s.target_slug)}>
                <b>{s.target_name}</b>
              </Button>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Tag color="volcano" style={{ fontWeight: 600 }}>
                共享 {s.shared_companies_count} 家龙头
              </Tag>
              <span style={{ fontSize: "var(--c-font-xs)", color: colors.textSecondary, overflowWrap: "anywhere", wordBreak: "break-word" }}>
                共有关联企业：{s.shared_companies.join("、")}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 单链详情与拓扑流向图 ────────────────────────────────────────────────────────

function ChainAtlasDetail({
  chain,
  onAnalyze,
  onCompanyClick,
  onDeleteSuccess,
}: {
  chain: AtlasChain;
  onAnalyze: (name: string) => void;
  onCompanyClick: (code: string) => void;
  onDeleteSuccess?: () => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false);
  const deleteMutation = useDeleteIndustryChainAtlasChain();
  const [detailMode, setDetailMode] = useState<"cards" | "graph">("cards");
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const isMobile = useMediaQuery("(max-width: 576px)");

  return (
    <div>
      <div style={{ ...cardStyle, padding: isMobile ? "14px 16px" : "18px 22px", marginBottom: 16 }}>
        <div
          className="atlas-detail__heading"
          style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}
        >
          <strong
            className="atlas-detail__name"
            style={{ fontSize: isMobile ? "var(--c-font-lg)" : "var(--c-font-xl)", color: colors.textPrimary }}
          >
            {chain.name}
          </strong>
          {chain.source === "user" && <Tag color="purple">个人专属</Tag>}
          {chain.source === "mined" && <Tag color="processing">AI 自动挖掘</Tag>}
          {chain.source === "imported" && <Tag color="gold">外部导入</Tag>}
          <Tag className="atlas-wrap-tag">{chain.category}</Tag>
          {(chain.tags ?? []).map((tag) => (
            <Tag key={tag} className="atlas-wrap-tag" color="processing">
              {tag}
            </Tag>
          ))}

          {chain.mined_at && (
            <span style={{ fontSize: "var(--c-font-xs)", color: colors.textMuted }}>
              挖掘入库: {chain.mined_at}
            </span>
          )}

          <div
            style={{
              marginLeft: isNarrow ? 0 : "auto",
              width: isNarrow ? "100%" : "auto",
              marginTop: isNarrow ? 6 : 0,
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <div style={{ width: isNarrow ? "100%" : "auto" }}>
              <Segmented
                block={isNarrow}
                value={detailMode}
                onChange={(val) => setDetailMode(val as "cards" | "graph")}
                options={[
                  { label: "分层环节", value: "cards", icon: <BarsOutlined /> },
                  { label: "拓扑流向", value: "graph", icon: <ApartmentOutlined /> },
                ]}
              />
            </div>
            {chain.archive_id && (
              <Button
                icon={<FileTextOutlined />}
                size={isMobile ? "small" : "middle"}
                onClick={() =>
                  navigate(
                    `/industry-chain/${encodeURIComponent(chain.name)}?archive_id=${chain.archive_id}`
                  )
                }
              >
                查看源研报
              </Button>
            )}
            <Button
              icon={<CloudDownloadOutlined />}
              size={isMobile ? "small" : "middle"}
              onClick={() => downloadIndustryChainAtlasYaml(chain.slug, chain.name)}
            >
              导出 YAML
            </Button>
            {((isAdmin && chain.source !== "builtin") || chain.source === "user") && (
              <Popconfirm
                title="确定删除这条产业链知识库图谱？"
                onConfirm={() => {
                  deleteMutation.mutate(chain.slug, {
                    onSuccess: async () => {
                      message.success(`已删除产业链：${chain.name}`);
                      onDeleteSuccess?.();
                      await queryClient.invalidateQueries({
                        queryKey: queryKeys.workflows.industryChainAtlasCatalog,
                      });
                      await queryClient.invalidateQueries({
                        queryKey: ["industryChainAtlas", "graph"],
                      });
                    },
                    onError: (error: Error) => message.error(error.message),
                  });
                }}
              >
                <Button danger icon={<DeleteOutlined />} size={isMobile ? "small" : "middle"}>
                  删除
                </Button>
              </Popconfirm>
            )}
            <Button
              type="primary"
              icon={<ExperimentOutlined />}
              size={isMobile ? "small" : "middle"}
              onClick={() => onAnalyze(chain.name)}
            >
              AI 深度分析
            </Button>
          </div>
        </div>

        <div
          className="atlas-detail__summary"
          style={{
            color: colors.textSecondary,
            fontSize: "var(--c-font-md)",
            lineHeight: "var(--c-leading-relaxed)",
            marginTop: 8,
          }}
        >
          {chain.summary}
        </div>

        {(chain.drivers ?? []).length > 0 && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {(chain.drivers ?? []).map((driver) => (
              <span
                key={driver}
                className="atlas-driver-chip"
                style={{
                  fontSize: "var(--c-font-sm)",
                  color: colors.warning,
                  background: `${colors.warning}14`,
                  border: `1px solid ${colors.warning}33`,
                  borderRadius: 6,
                  padding: "2px 8px",
                }}
              >
                驱动 · {driver}
              </span>
            ))}
          </div>
        )}
      </div>

      {detailMode === "graph" ? (
        <SingleChainGraph chain={chain} onCompanyClick={onCompanyClick} />
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {chain.layers.map((layer, index) => (
            <div key={layer.key}>
              <AtlasLayerBand layer={layer} onCompanyClick={onCompanyClick} />
              {index < chain.layers.length - 1 && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 0",
                    color: colors.textMuted,
                  }}
                >
                  <span style={{ height: 1, width: 40, background: colors.border }} />
                  <span style={{ fontSize: 12, opacity: 0.7, letterSpacing: 2 }}>↓ 传导流向</span>
                  <span style={{ height: 1, width: 40, background: colors.border }} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div
        style={{
          color: colors.textMuted,
          fontSize: "var(--c-font-sm)",
          marginTop: 16,
          textAlign: "center",
        }}
      >
        点击公司节点可跳转个股研究 · 知识库由官方名录核验并持续支持 AI 分析闭环挖掘
      </div>
    </div>
  );
}

// ── 单链清晰层次有向流向图（从左到右分列布局）──────────────────────────────

function SingleChainGraph({
  chain,
  onCompanyClick,
}: {
  chain: AtlasChain;
  onCompanyClick: (code: string) => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const chartRef = useRef<ReactEChartsCore | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!containerRef.current) return;
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.clientWidth);
      }
    };
    updateWidth();
    const ro = new ResizeObserver(updateWidth);
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const handleExport = () => {
    const chart = chartRef.current?.getEchartsInstance?.();
    if (!chart) return;
    const url = chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: colors.cardBg,
    });
    const link = document.createElement("a");
    link.download = `${chain.name}_产业链价值传导拓扑图.png`;
    link.href = url;
    link.click();
  };

  const chartOption = useMemo(() => {
    const nodes: Record<string, unknown>[] = [];
    const edges: Record<string, unknown>[] = [];
    const searchKeyword = search.trim().toLowerCase();

    // 动态计算三层（上中下游）列坐标以适配任何屏幕宽度（特别是移动端）
    const effectiveWidth = containerWidth || (typeof window !== "undefined" ? window.innerWidth - 64 : 800);
    const isSmall = effectiveWidth < 640;
    const leftMargin = isSmall ? 28 : Math.max(60, Math.floor(effectiveWidth * 0.1));
    const rightMargin = isSmall ? 80 : Math.max(140, Math.floor(effectiveWidth * 0.16));
    const spanWidth = Math.max(180, effectiveWidth - leftMargin - rightMargin);

    const layerXMap: Record<string, number> = {
      upstream: leftMargin,
      midstream: leftMargin + Math.floor(spanWidth * 0.5),
      downstream: leftMargin + spanWidth,
    };

    const layerCompanyMap: Record<string, string[]> = {
      upstream: [],
      midstream: [],
      downstream: [],
    };

    // 统计每层的公司数量以便均匀垂直排布
    const layerCounts: Record<string, number> = { upstream: 0, midstream: 0, downstream: 0 };
    for (const layer of chain.layers) {
      for (const seg of layer.segments) {
        layerCounts[layer.key] += seg.companies.length;
      }
    }

    const layerCurY: Record<string, number> = { upstream: 0, midstream: 0, downstream: 0 };

    for (const layer of chain.layers) {
      const color = LAYER_COLORS[layer.key] || colors.primary;
      const x = layerXMap[layer.key] || (leftMargin + Math.floor(spanWidth * 0.5));
      const totalInLayer = layerCounts[layer.key] || 1;
      const ySpacing = Math.max(isSmall ? 40 : 48, Math.min(isSmall ? 60 : 72, 600 / totalInLayer));

      for (const segment of layer.segments) {
        for (const company of segment.companies) {
          if (!layerCompanyMap[layer.key].includes(company.code)) {
            layerCompanyMap[layer.key].push(company.code);
            const y = (isSmall ? 32 : 40) + layerCurY[layer.key] * ySpacing;
            layerCurY[layer.key] += 1;

            const isMatch =
              searchKeyword &&
              (company.name.toLowerCase().includes(searchKeyword) ||
                company.code.includes(searchKeyword) ||
                segment.name.toLowerCase().includes(searchKeyword));
            const isDimmed = searchKeyword && !isMatch;

            const baseSymbolSize = isSmall ? 18 : 26;
            const matchSymbolSize = isSmall ? 24 : 34;

            nodes.push({
              id: company.code,
              name: company.name,
              x,
              y,
              symbolSize: isMatch ? matchSymbolSize : baseSymbolSize,
              category: layer.key,
              itemStyle: {
                color,
                borderColor: isMatch ? colors.accent : colors.cardBg,
                borderWidth: isMatch ? (isSmall ? 2.5 : 3.5) : 2,
                shadowBlur: isMatch ? (isSmall ? 10 : 16) : 6,
                shadowColor: isMatch ? `${colors.accent}90` : `${color}40`,
                opacity: isDimmed ? 0.35 : 1,
              },
              label: {
                show: true,
                position: "right",
                color: isMatch ? colors.primary : colors.textPrimary,
                fontWeight: isMatch ? "bold" : "normal",
                fontSize: isSmall ? 10 : 11,
                formatter: "{b}",
                opacity: isDimmed ? 0.35 : 1,
              },
              market: company.market || (company.code.length === 5 ? "hk" : "cn"),
              note: company.note,
              segment: segment.name,
              layerName: LAYER_NAMES[layer.key] || layer.key,
            });
          }
        }
      }
    }

    // 建立上游 -> 中游，中游 -> 下游的平滑贝塞尔传导流向边
    const connectLayers = (fromKey: string, toKey: string) => {
      const fromCodes = layerCompanyMap[fromKey] || [];
      const toCodes = layerCompanyMap[toKey] || [];
      if (!fromCodes.length || !toCodes.length) return;

      fromCodes.forEach((src, srcIdx) => {
        // 均匀按垂直相对高度映射到目标层相邻的 1-2 个节点，避免全部连线堆叠在顶部前3个节点
        const ratio = fromCodes.length > 1 ? srcIdx / (fromCodes.length - 1) : 0.5;
        const centerTgtIdx = Math.round(ratio * (toCodes.length - 1));
        const targetIndices = new Set<number>();
        targetIndices.add(centerTgtIdx);
        if (centerTgtIdx + 1 < toCodes.length && toCodes.length > 2) {
          targetIndices.add(centerTgtIdx + 1);
        } else if (centerTgtIdx - 1 >= 0 && toCodes.length > 2) {
          targetIndices.add(centerTgtIdx - 1);
        }

        targetIndices.forEach((tgtIdx) => {
          const tgt = toCodes[tgtIdx];
          if (!tgt) return;
          const curve = (tgtIdx - srcIdx) * 0.035;
          edges.push({
            source: src,
            target: tgt,
            lineStyle: {
              color: colors.border,
              width: 1.2,
              curveness: Math.max(-0.25, Math.min(0.25, curve || 0.08)),
              opacity: 0.48,
            },
          });
        });
      });
    };

    connectLayers("upstream", "midstream");
    connectLayers("midstream", "downstream");
    if (layerCompanyMap.midstream.length === 0) {
      connectLayers("upstream", "downstream");
    }

    const maxHeight = Math.max(
      isSmall ? 400 : 480,
      Math.max(layerCounts.upstream, layerCounts.midstream, layerCounts.downstream) * (isSmall ? 45 : 55) + 80
    );

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: colors.cardBg,
        borderColor: colors.border,
        textStyle: { color: colors.textPrimary },
        formatter: (params: { dataType?: string; data?: { name?: string; id?: string; layerName?: string; segment?: string; note?: string; market?: string } }) => {
          if (params.dataType === "node") {
            const data = params.data;
            if (!data) return "";
            const isHk = data.market === "hk" || data.id?.length === 5;
            const marketBadge = isHk
              ? `<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:rgba(14,165,233,0.15);color:#0284c7;font-weight:600;margin-left:6px;">港股</span>`
              : `<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:rgba(22,119,255,0.12);color:#1677ff;font-weight:600;margin-left:6px;">A股</span>`;
            return `
              <div style="font-weight:600;font-size:14px;margin-bottom:4px;color:${colors.textPrimary};display:flex;align-items:center;">
                ${data.name} <span style="font-size:12px;color:${colors.textMuted};margin-left:4px;">(${data.id})</span>${marketBadge}
              </div>
              <div style="font-size:12px;color:${colors.textSecondary};margin-bottom:2px;">
                层级环节：<b>${data.layerName} · ${data.segment}</b>
              </div>
              ${data.note ? `<div style="font-size:12px;color:${colors.textMuted};margin-bottom:4px;">业务定位：${data.note}</div>` : ""}
              <div style="font-size:11px;color:${colors.primary};margin-top:4px;">
                💡 点击跳转个股研究主页
              </div>
            `;
          }
          return "";
        },
      },
      legend: {
        top: 8,
        left: 12,
        data: [
          { name: "upstream", itemStyle: { color: LAYER_COLORS.upstream } },
          { name: "midstream", itemStyle: { color: LAYER_COLORS.midstream } },
          { name: "downstream", itemStyle: { color: LAYER_COLORS.downstream } },
        ],
        formatter: (name: string) => LAYER_NAMES[name] || name,
        textStyle: { color: colors.textSecondary, fontSize: isSmall ? 10 : 12 },
      },
      series: [
        {
          type: "graph",
          layout: "none",
          roam: true,
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: [4, 8],
          data: nodes,
          links: edges,
          categories: [
            { name: "upstream" },
            { name: "midstream" },
            { name: "downstream" },
          ],
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 3,
              opacity: 0.95,
            },
            itemStyle: {
              shadowBlur: 16,
            },
          },
        },
      ],
      maxHeight,
    };
  }, [chain, colors, search, containerWidth]);

  const onChartClick = (params: { dataType?: string; data?: { id?: string } }) => {
    if (params.dataType === "node" && params.data?.id) {
      onCompanyClick(params.data.id);
    }
  };

  const isSmall = (containerWidth || (typeof window !== "undefined" ? window.innerWidth : 800)) < 640;

  return (
    <Card style={cardStyle} bodyStyle={{ padding: isSmall ? 12 : 16 }}>
      {/* 搜索与导出工具栏 */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <Input
          allowClear
          placeholder="在当前拓扑图中高亮公司或细分环节…"
          prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: isSmall ? "100%" : 260 }}
        />
        <Button
          icon={<CameraOutlined />}
          size={isSmall ? "small" : "middle"}
          onClick={handleExport}
          style={{ width: isSmall ? "100%" : "auto" }}
        >
          导出高清拓扑图
        </Button>
      </div>

      {/* 层次列标题横幅 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: isSmall ? 4 : 12,
          padding: isSmall ? "6px 8px" : "8px 16px",
          background: `${colors.primary}08`,
          borderRadius: 6,
          marginBottom: 12,
          textAlign: "center",
          fontSize: isSmall ? "var(--c-font-xs)" : "var(--c-font-sm)",
          fontWeight: 600,
        }}
      >
        <span style={{ color: LAYER_COLORS.upstream }}>
          {isSmall ? "上游·材料/设备" : "上游 · 核心原材料 / 关键设备"}
        </span>
        <span style={{ color: LAYER_COLORS.midstream }}>
          {isSmall ? "中游·制造/集成" : "中游 · 制造封测 / 模组与系统集成"}
        </span>
        <span style={{ color: LAYER_COLORS.downstream }}>
          {isSmall ? "下游·终端/应用" : "下游 · 终端产品 / 行业应用场景"}
        </span>
      </div>

      <div
        ref={containerRef}
        style={{
          height: isSmall
            ? Math.max(400, Math.min(chartOption.maxHeight, 640))
            : Math.max(540, Math.min(chartOption.maxHeight || 540, 880)),
          position: "relative",
        }}
      >
        <ReactEChartsCore
          ref={chartRef}
          echarts={echarts}
          option={chartOption}
          notMerge
          onEvents={{ click: onChartClick }}
          style={{ width: "100%", height: "100%" }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 6,
            right: 12,
            fontSize: "var(--c-font-xs)",
            color: colors.textMuted,
            pointerEvents: "none",
            background: `${colors.cardBg}cc`,
            padding: "2px 6px",
            borderRadius: 4,
          }}
        >
          {isSmall ? "支持双指捏合缩放 · 点击节点查看个股" : "从左向右：上游原材料/设备 → 中游制造/方案 → 下游应用场景"}
        </div>
      </div>
    </Card>
  );
}
