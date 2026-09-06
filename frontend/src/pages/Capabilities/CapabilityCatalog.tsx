import { useMemo, useState } from "react";
import {
  ApiOutlined,
  AppstoreOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  SearchOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Segmented,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { TableColumnsType } from "antd";
import { useColors, semanticTagStyle } from "../../styles/ui";
import type { SemanticTagColor } from "../../styles/ui";
import type {
  ChatCapabilitiesResponse,
  ToolCapabilityInfo,
  ToolCost,
  ToolFreshness,
  ToolParameterSchema,
} from "../../types/capabilities";
import { filterCapabilities, formatCacheTtl, formatToolTimeout } from "./capabilityHelpers";

const { Paragraph, Text, Title } = Typography;

const COST_META: Record<ToolCost, { label: string; color: SemanticTagColor | "" }> = {
  low: { label: "低成本", color: "down" },
  medium: { label: "中成本", color: "warning" },
  high: { label: "高成本", color: "up" },
};

const FRESHNESS_META: Record<ToolFreshness, { label: string; color: SemanticTagColor | "" }> = {
  realtime: { label: "实时", color: "accent" },
  near_realtime: { label: "近实时", color: "info" },
  daily: { label: "日级", color: "primary" },
  static: { label: "静态", color: "" },
};

interface ParameterRow {
  key: string;
  name: string;
  schema: ToolParameterSchema;
  required: boolean;
}

function schemaType(schema: ToolParameterSchema): string {
  if (Array.isArray(schema.type)) return schema.type.join(" / ");
  if (schema.type === "array" && schema.items?.type) return `array<${schema.items.type}>`;
  return schema.type || "-";
}

function schemaConstraints(schema: ToolParameterSchema): string {
  const values: string[] = [];
  if (schema.enum?.length) values.push(`可选 ${schema.enum.join(" / ")}`);
  if (schema.minimum !== undefined) values.push(`≥ ${schema.minimum}`);
  if (schema.maximum !== undefined) values.push(`≤ ${schema.maximum}`);
  if (schema.minItems !== undefined) values.push(`至少 ${schema.minItems} 项`);
  if (schema.maxItems !== undefined) values.push(`最多 ${schema.maxItems} 项`);
  if (schema.format) values.push(schema.format);
  if (schema.pattern) values.push(schema.pattern);
  return values.join(" · ") || "-";
}

function displayDefault(value: unknown): string {
  if (value === undefined) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export default function CapabilityCatalog({ capabilities }: { capabilities: ChatCapabilitiesResponse }) {
  const colors = useColors();
  const [view, setView] = useState<"skills" | "tools">("skills");
  const [query, setQuery] = useState("");
  const [selectedTool, setSelectedTool] = useState<ToolCapabilityInfo | null>(null);
  const filtered = useMemo(
    () => filterCapabilities(capabilities, query),
    [capabilities, query],
  );
  const toolByName = useMemo(
    () => new Map(capabilities.tools.map((tool) => [tool.name, tool])),
    [capabilities.tools],
  );
  const highCostCount = capabilities.tools.filter((tool) => tool.policy.cost === "high").length;
  const assignedToolCount = capabilities.tools.length - capabilities.unassigned_tools.length;
  const coverage = capabilities.tools.length
    ? Math.round((assignedToolCount / capabilities.tools.length) * 100)
    : 0;
  const parameterRows = useMemo<ParameterRow[]>(() => {
    if (!selectedTool) return [];
    const required = new Set(selectedTool.parameters.required || []);
    return Object.entries(selectedTool.parameters.properties).map(([name, schema]) => ({
      key: name,
      name,
      schema,
      required: required.has(name),
    }));
  }, [selectedTool]);
  const parameterColumns = useMemo<TableColumnsType<ParameterRow>>(() => [
    {
      title: "参数",
      dataIndex: "name",
      width: 150,
      render: (name: string) => <Text code>{name}</Text>,
    },
    {
      title: "类型",
      width: 120,
      render: (_, row) => <Text style={{ color: colors.textSecondary }}>{schemaType(row.schema)}</Text>,
    },
    {
      title: "必填",
      width: 72,
      align: "center",
      render: (_, row) => row.required ? <Tag style={semanticTagStyle("up")}>是</Tag> : <Tag>否</Tag>,
    },
    {
      title: "默认值",
      width: 100,
      render: (_, row) => displayDefault(row.schema.default),
    },
    {
      title: "约束 / 说明",
      render: (_, row) => (
        <div>
          <div style={{ color: colors.textSecondary }}>{row.schema.description || "-"}</div>
          <div style={{ color: colors.textMuted, fontSize: "var(--c-font-sm)", marginTop: 2 }}>
            {schemaConstraints(row.schema)}
          </div>
        </div>
      ),
    },
  ], [colors]);

  const openTool = (toolName: string) => {
    const tool = toolByName.get(toolName);
    if (tool) setSelectedTool(tool);
  };

  return (
    <>
      <div className="capability-summary-grid">
        <Card className="capability-summary-card">
          <Statistic title="Skills" value={capabilities.skills.length} prefix={<BranchesOutlined />} />
        </Card>
        <Card className="capability-summary-card">
          <Statistic title="Tools" value={capabilities.tools.length} prefix={<ApiOutlined />} />
        </Card>
        <Card className="capability-summary-card">
          <Statistic title="高成本工具" value={highCostCount} prefix={<ThunderboltOutlined />} />
        </Card>
        <Card className="capability-summary-card">
          <Statistic title="Skill 覆盖率" value={coverage} suffix="%" prefix={<AppstoreOutlined />} />
        </Card>
      </div>

      {capabilities.unassigned_tools.length > 0 && (
        <Alert
          className="capability-unassigned-alert"
          type="warning"
          showIcon
          title={`${capabilities.unassigned_tools.length} 个 Tool 尚未归属 Skill`}
          description={capabilities.unassigned_tools.join("、")}
        />
      )}

      <div className="capability-toolbar">
        <Segmented
          value={view}
          onChange={(value) => setView(value as "skills" | "tools")}
          options={[
            { label: `Skill 视图 (${filtered.skills.length})`, value: "skills", icon: <BranchesOutlined /> },
            { label: `Tool 视图 (${filtered.tools.length})`, value: "tools", icon: <ApiOutlined /> },
          ]}
        />
        <Input
          allowClear
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          prefix={<SearchOutlined />}
          placeholder="搜索名称、描述、规则或参数"
          aria-label="搜索能力"
          className="capability-search"
        />
      </div>

      {view === "skills" ? (
        filtered.skills.length ? (
          <div className="capability-card-grid capability-skill-grid">
            {filtered.skills.map((skill, index) => (
              <Card
                key={skill.name}
                className="capability-card capability-skill-card"
                title={(
                  <div className="capability-card-title">
                    <span className="capability-number">{index + 1}</span>
                    <span>
                      <span className="capability-title-text">{skill.description}</span>
                      <Text code className="capability-code-name">{skill.name}</Text>
                    </span>
                  </div>
                )}
                extra={<Tag style={semanticTagStyle("primary")}>P{skill.priority}</Tag>}
              >
                <div className="capability-label">触发条件</div>
                <Space size={[6, 6]} wrap>
                  {skill.triggers.map((trigger) => <Tag key={trigger}>{trigger}</Tag>)}
                </Space>

                <div className="capability-label capability-section-gap">路由规则</div>
                <ul className="capability-rule-list">
                  {skill.rules.map((rule) => <li key={rule}>{rule}</li>)}
                </ul>

                {skill.exclusions.length > 0 && (
                  <div className="capability-exclusions">
                    <strong>避免：</strong>{skill.exclusions.join("；")}
                  </div>
                )}

                <div className="capability-label capability-section-gap">
                  关联 Tools · {skill.tool_names.length}
                </div>
                <Space size={[6, 6]} wrap>
                  {skill.tool_names.map((toolName) => (
                    <Tag
                      key={toolName}
                      className="capability-tool-chip"
                      role="button"
                      tabIndex={0}
                      onClick={() => openTool(toolName)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") openTool(toolName);
                      }}
                    >
                      <ApiOutlined /> {toolName}
                    </Tag>
                  ))}
                </Space>
              </Card>
            ))}
          </div>
        ) : <Empty description="没有匹配的 Skill" />
      ) : (
        filtered.tools.length ? (
          <div className="capability-card-grid capability-tool-grid">
            {filtered.tools.map((tool) => {
              const cost = COST_META[tool.policy.cost];
              const freshness = FRESHNESS_META[tool.policy.freshness];
              const costStyle = cost.color ? semanticTagStyle(cost.color) : undefined;
              const freshnessStyle = freshness.color ? semanticTagStyle(freshness.color) : undefined;
              const requiredCount = tool.parameters.required?.length || 0;
              return (
                <Card
                  key={tool.name}
                  hoverable
                  className="capability-card capability-tool-card"
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedTool(tool)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") setSelectedTool(tool);
                  }}
                >
                  <div className="capability-tool-heading">
                    <div className="capability-tool-icon"><ApiOutlined /></div>
                    <div className="capability-tool-name-wrap">
                      <Text code className="capability-tool-name">{tool.name}</Text>
                      <div>
                        {costStyle ? <Tag style={costStyle}>{cost.label}</Tag> : <Tag>{cost.label}</Tag>}
                        {freshnessStyle
                          ? <Tag style={freshnessStyle}>{freshness.label}</Tag>
                          : <Tag>{freshness.label}</Tag>}
                      </div>
                    </div>
                  </div>
                  <Paragraph ellipsis={{ rows: 3 }} className="capability-tool-description">
                    {tool.description}
                  </Paragraph>
                  <div className="capability-policy-row">
                    <span><ClockCircleOutlined /> {formatCacheTtl(tool.policy.cache_ttl_seconds)}</span>
                    <span><DatabaseOutlined /> {requiredCount} 必填 / {Object.keys(tool.parameters.properties).length} 参数</span>
                  </div>
                  <div className="capability-linked-skills">
                    {tool.skill_names.length ? tool.skill_names.map((skillName) => (
                      <Tag key={skillName}>{skillName}</Tag>
                    )) : <Tag style={semanticTagStyle("warning")}>未归属 Skill</Tag>}
                  </div>
                </Card>
              );
            })}
          </div>
        ) : <Empty description="没有匹配的 Tool" />
      )}

      <Drawer
        open={Boolean(selectedTool)}
        onClose={() => setSelectedTool(null)}
        size="min(720px, 100vw)"
        title={selectedTool ? <Space><ApiOutlined /><Text code>{selectedTool.name}</Text></Space> : null}
      >
        {selectedTool && (
          <div className="capability-drawer-content">
            <Paragraph>{selectedTool.description}</Paragraph>
            <Descriptions bordered size="small" column={{ xs: 1, sm: 2 }}>
              <Descriptions.Item label="成本">
                {(() => {
                  const cost = COST_META[selectedTool.policy.cost];
                  const costStyle = cost.color ? semanticTagStyle(cost.color) : undefined;
                  return costStyle ? <Tag style={costStyle}>{cost.label}</Tag> : <Tag>{cost.label}</Tag>;
                })()}
              </Descriptions.Item>
              <Descriptions.Item label="数据时效">
                {FRESHNESS_META[selectedTool.policy.freshness].label}
              </Descriptions.Item>
              <Descriptions.Item label="缓存 TTL">
                {formatCacheTtl(selectedTool.policy.cache_ttl_seconds)}
              </Descriptions.Item>
              <Descriptions.Item label="作用域">
                {selectedTool.policy.scope === "user" ? "用户级" : "公共数据"}
              </Descriptions.Item>
              <Descriptions.Item label="执行超时">
                {formatToolTimeout(selectedTool.policy.timeout_seconds)}
              </Descriptions.Item>
              <Descriptions.Item label="并发上限">
                {selectedTool.policy.max_parallel_calls ?? "跟随运行时"}
              </Descriptions.Item>
              <Descriptions.Item label="结果预算">
                {selectedTool.policy.max_result_characters.toLocaleString()} 字符
              </Descriptions.Item>
              <Descriptions.Item label="关联 Skill" span={2}>
                <Space size={[4, 4]} wrap>
                  {selectedTool.skill_names.length
                    ? selectedTool.skill_names.map((name) => <Tag key={name}>{name}</Tag>)
                    : <Text type="secondary">暂未归属</Text>}
                </Space>
              </Descriptions.Item>
            </Descriptions>

            <Title level={5} className="capability-parameter-title">参数定义</Title>
            {parameterRows.length ? (
              <Table
                columns={parameterColumns}
                dataSource={parameterRows}
                pagination={false}
                size="small"
                scroll={{ x: 680 }}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无需参数" />
            )}
          </div>
        )}
      </Drawer>
    </>
  );
}
