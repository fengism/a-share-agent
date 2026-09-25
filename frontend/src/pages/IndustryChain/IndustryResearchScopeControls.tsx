import { Input, Select, Typography } from "antd";
import type { IndustryChainResearchScope } from "../../types/stock";
import { useColors } from "../../styles/ui";

const { Text } = Typography;

interface IndustryResearchScopeControlsProps {
  value: IndustryChainResearchScope;
  disabled?: boolean;
  onChange: (value: IndustryChainResearchScope) => void;
}

export default function IndustryResearchScopeControls({
  value,
  disabled,
  onChange,
}: IndustryResearchScopeControlsProps) {
  const colors = useColors();
  const update = (patch: Partial<IndustryChainResearchScope>) => onChange({ ...value, ...patch });

  return (
    <details style={{ marginTop: 12 }}>
      <summary style={{ color: colors.textSecondary, cursor: "pointer", fontSize: "var(--c-font-md)" }}>分析范围（可选）</summary>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginTop: 12 }}>
        <label>
          <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>区域口径</Text>
          <Select
            value={value.region}
            disabled={disabled}
            onChange={(region) => update({ region })}
            style={{ width: "100%" }}
            options={[
              { value: "china_and_global", label: "中国与全球对比" },
              { value: "china", label: "仅中国" },
              { value: "global", label: "仅全球" },
            ]}
          />
        </label>
        <label>
          <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>时间范围</Text>
          <Select
            value={value.time_range}
            disabled={disabled}
            onChange={(time_range) => update({ time_range })}
            style={{ width: "100%" }}
            options={[
              { value: "half_year", label: "最近半年" },
              { value: "one_year", label: "最近一年" },
              { value: "three_years", label: "最近三年" },
              { value: "custom", label: "自定义" },
            ]}
          />
        </label>
        <label>
          <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>公司范围</Text>
          <Select
            value={value.company_scope}
            disabled={disabled}
            onChange={(company_scope) => update({ company_scope })}
            style={{ width: "100%" }}
            options={[
              { value: "a_share", label: "A 股公司映射" },
              { value: "all_public", label: "全部公开公司" },
            ]}
          />
        </label>
        <label style={{ gridColumn: "1 / -1" }}>
          <Text type="secondary" style={{ display: "block", marginBottom: 4 }}>强制刷新公共数据维度（其他维度复用有效缓存）</Text>
          <Select mode="multiple" aria-label="刷新公共数据维度" value={value.refresh_dimensions || []}
            disabled={disabled} onChange={(refresh_dimensions) => update({ refresh_dimensions })} style={{ width: "100%" }}
            options={[
              { value: "market", label: "市场与价格" }, { value: "stocks", label: "公司" },
              { value: "competition", label: "竞争" }, { value: "technology", label: "技术" },
              { value: "chain", label: "产业结构" }, { value: "drivers_risks", label: "驱动与风险" },
              { value: "reports", label: "研报" }, { value: "events", label: "事件" },
            ]} />
          <Text type="secondary">刷新后仍会执行 Agent 调研与报告合成，不承诺只消耗所选维度的模型调用。</Text>
        </label>
        <label>
          <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>分析基准日</Text>
          <Input
            type="date"
            value={value.as_of_date || ""}
            disabled={disabled}
            onChange={(event) => update({ as_of_date: event.target.value || undefined })}
          />
        </label>
        {value.time_range === "custom" && (
          <>
            <label>
              <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>开始日期</Text>
              <Input
                type="date"
                value={value.start_date || ""}
                disabled={disabled}
                onChange={(event) => update({ start_date: event.target.value || undefined })}
              />
            </label>
            <label>
              <Text type="secondary" style={{ display: "block", marginBottom: 4, fontSize: "var(--c-font-sm)" }}>结束日期</Text>
              <Input
                type="date"
                value={value.end_date || ""}
                disabled={disabled}
                onChange={(event) => update({ end_date: event.target.value || undefined })}
              />
            </label>
          </>
        )}
      </div>
    </details>
  );
}
