import { useMemo, useState } from "react";
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  DeleteOutlined,
  ExperimentOutlined,
  ImportOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Button, Empty, Input, Modal, Popconfirm, Spin, Switch, Tag, Upload, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  useDeleteIndustryChainAtlasChain,
  useImportIndustryChainAtlas,
  useIndustryChainAtlasCatalog,
  useIndustryChainAtlasChain,
} from "../../api/queryHooks/workflows";
import { queryKeys } from "../../api/queryKeys";
import { useAuthStore } from "../../store/authStore";
import { useColors, useStyles } from "../../styles/ui";
import type { AtlasLayer } from "../../types/stock";
import QueryErrorState from "../../components/QueryErrorState";

const IMPORT_PLACEHOLDER = `slug: my-chain
name: 我的产业链
category: 新材料
summary: 一句话描述这条产业链。
tags: [新材料]
drivers:
  - 驱动因素一
layers:
  - key: upstream          # upstream / midstream / downstream
    name: 上游 · 原材料
    segments:
      - name: 某环节
        companies:
          - { name: 某公司, code: "600000", note: 一句话定位 }

# 也支持批量：顶层写 chains: [ ... ]，或直接给数组；JSON 同样可导入`;

const LAYER_ACCENTS = {
  upstream: "info",
  midstream: "primary",
  downstream: "success",
} as const;

interface IndustryAtlasProps {
  onAnalyze: (name: string) => void;
}

export default function IndustryAtlas({ onAnalyze }: IndustryAtlasProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.user?.is_admin ?? false);
  const [selectedSlug, setSelectedSlug] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [importOpen, setImportOpen] = useState(false);

  const catalogQuery = useIndustryChainAtlasCatalog();
  const chainQuery = useIndustryChainAtlasChain(selectedSlug);
  const importMutation = useImportIndustryChainAtlas();
  const deleteMutation = useDeleteIndustryChainAtlasChain();
  const catalog = catalogQuery.data;

  const filteredChains = useMemo(() => {
    if (!catalog) return [];
    const keyword = search.trim().toLowerCase();
    return catalog.chains.filter((chain) => {
      if (category && chain.category !== category) return false;
      if (!keyword) return true;
      return (
        chain.name.toLowerCase().includes(keyword)
        || chain.summary.toLowerCase().includes(keyword)
        || (chain.aliases ?? []).some((alias) => alias.toLowerCase().includes(keyword))
        || (chain.tags ?? []).some((tag) => tag.toLowerCase().includes(keyword))
      );
    });
  }, [catalog, category, search]);

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
            onCompanyClick={(code) => navigate(`/analysis/${code}`)}
          />
        )}
      </div>
    );
  }

  return (
    <div>
      <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <Input
            allowClear
            prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
            placeholder="搜索产业链、标签或别名…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            style={{ maxWidth: 320 }}
          />
          <span style={{ color: colors.textMuted, fontSize: 13 }}>
            {catalog
              ? `${catalog.total_chains} 条产业链 · ${catalog.total_companies} 家公司`
              : "加载中…"}
          </span>
          {isAdmin && (
            <Button
              icon={<ImportOutlined />}
              style={{ marginLeft: "auto" }}
              onClick={() => setImportOpen(true)}
            >
              导入产业链
            </Button>
          )}
        </div>
        {catalog && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
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
        )}
      </div>

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
        <div style={{ ...cardStyle, padding: 40 }}>
          <Empty description="没有匹配的产业链" />
        </div>
      )}
      {catalog && filteredChains.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: 14,
          }}
        >
          {filteredChains.map((chain) => (
            <div
              key={chain.slug}
              className="atlas-chain-card"
              style={{
                ...cardStyle,
                padding: "16px 18px",
                cursor: "pointer",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
              onClick={() => setSelectedSlug(chain.slug)}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    width: 30,
                    height: 30,
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
                <strong style={{ fontSize: 15, color: colors.textPrimary }}>{chain.name}</strong>
                {chain.source === "mined" && <Tag color="processing">AI 挖掘</Tag>}
                {chain.source === "imported" && <Tag color="gold">外部导入</Tag>}
                <Tag style={{ marginLeft: "auto" }}>{chain.category}</Tag>
              </div>
              <div style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 1.6, flex: 1 }}>
                {chain.summary}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: colors.textMuted }}>
                <span>{chain.segment_count} 个环节</span>
                <span>·</span>
                <span>{chain.company_count} 家公司</span>
                {isAdmin && (chain.source === "imported" || chain.source === "mined") && (
                  <Popconfirm
                    title="删除这条导入的产业链？"
                    onConfirm={(event) => {
                      event?.stopPropagation();
                      deleteMutation.mutate(chain.slug, {
                        onSuccess: async () => {
                          message.success(`已删除导入的产业链：${chain.name}`);
                          await queryClient.invalidateQueries({
                            queryKey: queryKeys.workflows.industryChainAtlasCatalog,
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
                  style={{ marginLeft: isAdmin && chain.source !== "builtin" ? 0 : "auto", padding: 0, height: "auto" }}
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

      {isAdmin && (
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
                },
                onError: (error: Error) => message.error({
                  content: error.message,
                  duration: 8,
                }),
              },
            );
          }}
        />
      )}
    </div>
  );
}

function AtlasImportModal({
  open,
  onClose,
  importing,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  importing: boolean;
  onSubmit: (content: string, overwrite: boolean) => void;
}) {
  const colors = useColors();
  const [content, setContent] = useState("");
  const [overwrite, setOverwrite] = useState(false);

  return (
    <Modal
      title="导入产业链知识库"
      open={open}
      onCancel={onClose}
      onOk={() => onSubmit(content, overwrite)}
      okText="导入"
      okButtonProps={{ disabled: !content.trim() || importing }}
      confirmLoading={importing}
      width={720}
      destroyOnClose
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <Upload
          accept=".yaml,.yml,.json,.txt"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file) => {
            void file.text().then((text) => setContent(text));
            return false;
          }}
        >
          <Button size="small">选择文件（.yaml / .json）</Button>
        </Upload>
        <span style={{ color: colors.textMuted, fontSize: 12 }}>或直接粘贴内容</span>
        <label style={{ marginLeft: "auto", fontSize: 13, color: colors.textSecondary, cursor: "pointer" }}>
          覆盖同名产业链
          <Switch
            size="small"
            checked={overwrite}
            onChange={setOverwrite}
            style={{ marginLeft: 8 }}
          />
        </label>
      </div>
      <Input.TextArea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder={IMPORT_PLACEHOLDER}
        rows={16}
        style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
      />
    </Modal>
  );
}

function CategoryChip({
  label,
  active,
  colors,
  onClick,
}: {
  label: string;
  active: boolean;
  colors: ReturnType<typeof useColors>;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="atlas-category-chip"
      onClick={onClick}
      style={{
        border: `1px solid ${active ? colors.primary : colors.border}`,
        background: active ? `${colors.primary}1f` : "transparent",
        color: active ? colors.primary : colors.textSecondary,
        borderRadius: 999,
        padding: "3px 14px",
        fontSize: 13,
        cursor: "pointer",
        transition: "all 0.15s ease",
      }}
    >
      {label}
    </button>
  );
}

function ChainAtlasDetail({
  chain,
  onAnalyze,
  onCompanyClick,
}: {
  chain: NonNullable<ReturnType<typeof useIndustryChainAtlasChain>["data"]>;
  onAnalyze: (name: string) => void;
  onCompanyClick: (code: string) => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();

  return (
    <div>
      <div style={{ ...cardStyle, padding: "18px 22px", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <strong style={{ fontSize: 18, color: colors.textPrimary }}>{chain.name}</strong>
          <Tag>{chain.category}</Tag>
          {(chain.tags ?? []).map((tag) => (
            <Tag key={tag} color="processing">{tag}</Tag>
          ))}
          <Button
            type="primary"
            icon={<ExperimentOutlined />}
            style={{ marginLeft: "auto" }}
            onClick={() => onAnalyze(chain.name)}
          >
            AI 深度分析
          </Button>
        </div>
        <div style={{ color: colors.textSecondary, fontSize: 13, lineHeight: 1.7, marginTop: 8 }}>
          {chain.summary}
        </div>
        {(chain.drivers ?? []).length > 0 && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {(chain.drivers ?? []).map((driver) => (
              <span
                key={driver}
                style={{
                  fontSize: 12,
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

      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {chain.layers.map((layer) => (
          <AtlasLayerBand key={layer.key} layer={layer} onCompanyClick={onCompanyClick} />
        ))}
      </div>

      <div style={{ color: colors.textMuted, fontSize: 12, marginTop: 16, textAlign: "center" }}>
        点击公司节点可跳转个股分析 · 数据为静态策划知识库，深度分析请使用 AI 分析
      </div>
    </div>
  );
}

function AtlasLayerBand({
  layer,
  onCompanyClick,
}: {
  layer: AtlasLayer;
  onCompanyClick: (code: string) => void;
}) {
  const colors = useColors();
  const accent = colors[LAYER_ACCENTS[layer.key]];

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        background: colors.cardBg,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 16px",
          borderBottom: `1px solid ${colors.border}`,
          background: `linear-gradient(90deg, ${accent}14, transparent)`,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: 999,
            background: accent,
            boxShadow: `0 0 8px ${accent}`,
            flexShrink: 0,
          }}
        />
        <strong style={{ color: colors.textPrimary, fontSize: 14 }}>{layer.name}</strong>
        <span style={{ color: colors.textMuted, fontSize: 12 }}>
          {layer.segments.length} 个环节
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: 12,
          padding: 14,
        }}
      >
        {layer.segments.map((segment) => (
          <div
            key={segment.name}
            style={{
              border: `1px solid ${colors.border}`,
              borderRadius: 10,
              background: colors.nestedBg,
              padding: "10px 12px",
            }}
          >
            <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 3, height: 12, borderRadius: 2, background: accent }} />
              <strong style={{ fontSize: 13, color: colors.textPrimary }}>{segment.name}</strong>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {segment.companies.map((company) => (
                <button
                  key={`${company.code}-${company.name}`}
                  type="button"
                  className="atlas-company-chip"
                  title={company.note || company.name}
                  onClick={() => onCompanyClick(company.code)}
                  style={{
                    border: `1px solid ${colors.border}`,
                    background: colors.cardBg,
                    borderRadius: 8,
                    padding: "4px 9px",
                    fontSize: 12,
                    color: colors.textPrimary,
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <span>{company.name}</span>
                  <span style={{ color: accent, fontFamily: "var(--font-mono, monospace)", fontSize: 11 }}>
                    {company.code}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
