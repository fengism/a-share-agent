import { useMemo, useState } from "react";
import { Row, Col, InputNumber, Select, Button, Space, Switch, Slider, Typography, Badge } from "antd";
import {
  SearchOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  SafetyCertificateOutlined,
  DownOutlined,
  UpOutlined,
  ControlOutlined,
} from "@ant-design/icons";
import type { ScreenerFilter } from "../../types/stock";
import { useStyles } from "../../styles/ui";
import { useScreenerPresets } from "../../api/queryHooks/screener";
import ActiveFiltersBar from "./ActiveFiltersBar";
import AiNaturalScreenerBar from "./AiNaturalScreenerBar";

const { Text } = Typography;

interface RangeFieldProps {
  label: string;
  min?: number | null;
  max?: number | null;
  onMinChange: (v: number | null) => void;
  onMaxChange: (v: number | null) => void;
  minPlaceholder?: string;
  maxPlaceholder?: string;
  step?: number;
  onPressEnter?: () => void;
}

function RangeField({
  label,
  min,
  max,
  onMinChange,
  onMaxChange,
  minPlaceholder = "最小",
  maxPlaceholder = "最大",
  step = 0.01,
  onPressEnter,
  xs = 12,
  sm = 12,
  md = 6,
}: RangeFieldProps & { xs?: number; sm?: number; md?: number }) {
  const { fieldLabelStyle } = useStyles();
  return (
    <Col xs={xs} sm={sm} md={md}>
      <div style={fieldLabelStyle}>{label}</div>
      <Space.Compact style={{ width: "100%" }}>
        <InputNumber
          style={{ width: "50%" }}
          value={min}
          onChange={onMinChange}
          onPressEnter={onPressEnter}
          placeholder={minPlaceholder}
          step={step}
          size="small"
        />
        <InputNumber
          style={{ width: "50%" }}
          value={max}
          onChange={onMaxChange}
          onPressEnter={onPressEnter}
          placeholder={maxPlaceholder}
          step={step}
          size="small"
        />
      </Space.Compact>
    </Col>
  );
}

interface Props {
  filters: ScreenerFilter;
  onFiltersChange: (filters: ScreenerFilter) => void;
  industries: string[];
  concepts?: string[];
  onSearch: () => void;
  onReset: () => void;
  showPercentile: boolean;
  onShowPercentileChange: (v: boolean) => void;
  pePercentileMax: number;
  pbPercentileMax: number;
  onPePercentileMaxChange: (v: number) => void;
  onPbPercentileMaxChange: (v: number) => void;
}

export default function FilterPanel({
  filters,
  onFiltersChange,
  industries,
  concepts = [],
  onSearch,
  onReset,
  showPercentile,
  onShowPercentileChange,
  pePercentileMax,
  pbPercentileMax,
  onPePercentileMaxChange,
  onPbPercentileMaxChange,
}: Props) {
  const { fieldLabelStyle, mutedTextStyle } = useStyles();
  const { data: presets } = useScreenerPresets();
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const industryOptions = useMemo(
    () => industries.map((n) => ({ label: n, value: n })),
    [industries],
  );
  const conceptOptions = useMemo(
    () => concepts.map((n) => ({ label: n, value: n })),
    [concepts],
  );

  const activeAdvancedCount = useMemo(() => {
    let count = 0;
    if (filters.change_pct_min != null || filters.change_pct_max != null) count++;
    if (filters.turnover_pct_min != null || filters.turnover_pct_max != null) count++;
    if (filters.volume_ratio_min != null || filters.volume_ratio_max != null) count++;
    if (filters.change_pct_60d_min != null || filters.change_pct_60d_max != null) count++;
    if (filters.amplitude_min != null || filters.amplitude_max != null) count++;
    if (filters.min_amount_yi != null && filters.min_amount_yi > 0) count++;
    if (showPercentile) count++;
    return count;
  }, [filters, showPercentile]);

  const set = (patch: Partial<ScreenerFilter>) => {
    onFiltersChange({ ...filters, ...patch });
  };

  const isPresetActive = (preset: { filters: Partial<ScreenerFilter> }) => {
    const keys = Object.keys(preset.filters) as (keyof ScreenerFilter)[];
    return keys.length > 0 && keys.every((k) => {
      const pv = preset.filters[k];
      if (pv === null || pv === undefined) return true;
      return filters[k] === pv;
    });
  };

  return (
    <div>
      {/* AI 自然语言语义选股 */}
      <AiNaturalScreenerBar
        currentFilters={filters}
        onApplyFilters={(patch) => {
          onFiltersChange({ ...filters, ...patch });
        }}
        onSearch={onSearch}
        industries={industries}
        concepts={concepts}
      />

      {/* 题材与低估值快捷场景模版：移动端横滑优化 */}
      {presets && presets.length > 0 && (
        <div
          style={{
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 8,
            overflowX: "auto",
            whiteSpace: "nowrap",
            paddingBottom: 4,
            WebkitOverflowScrolling: "touch",
            scrollbarWidth: "none",
          }}
        >
          <span style={{ fontSize: "var(--c-font-sm)", color: mutedTextStyle.color, fontWeight: 600, flexShrink: 0 }}>
            场景挖掘:
          </span>
          {presets.map((preset) => {
            const active = isPresetActive(preset);
            return (
              <Button
                key={preset.key}
                size="small"
                type={active ? "primary" : "default"}
                icon={preset.category === "theme" ? <ThunderboltOutlined /> : <SafetyCertificateOutlined />}
                onClick={() => {
                  onFiltersChange({
                    ...filters,
                    ...preset.filters,
                    page: 1,
                  });
                }}
                title={preset.description}
                style={{
                  fontSize: "var(--c-font-sm)",
                  flexShrink: 0,
                  borderColor: active ? undefined : preset.category === "theme" ? "#fa8c16" : preset.category === "value" ? "#1890ff" : undefined,
                  color: active ? undefined : preset.category === "theme" ? "#fa8c16" : preset.category === "value" ? "#1890ff" : undefined,
                }}
              >
                {preset.name}
              </Button>
            );
          })}
        </div>
      )}

      {/* 常用基础筛选（首屏常驻，紧凑栅格） */}
      <Row gutter={[12, 10]}>
        <RangeField label="PE(TTM)" min={filters.pe_min} max={filters.pe_max} onMinChange={(v) => set({ pe_min: v })} onMaxChange={(v) => set({ pe_max: v })} onPressEnter={onSearch} step={1} minPlaceholder="0" maxPlaceholder="100" />
        <RangeField label="PB" min={filters.pb_min} max={filters.pb_max} onMinChange={(v) => set({ pb_min: v })} onMaxChange={(v) => set({ pb_max: v })} onPressEnter={onSearch} step={0.1} minPlaceholder="0" maxPlaceholder="50" />
        <RangeField label="股价(元)" min={filters.price_min} max={filters.price_max} onMinChange={(v) => set({ price_min: v })} onMaxChange={(v) => set({ price_max: v })} onPressEnter={onSearch} step={1} minPlaceholder="0" maxPlaceholder="1000" />
        <RangeField label="市值(亿)" min={filters.market_cap_min} max={filters.market_cap_max} onMinChange={(v) => set({ market_cap_min: v })} onMaxChange={(v) => set({ market_cap_max: v })} onPressEnter={onSearch} step={10} minPlaceholder="0" maxPlaceholder="50000" />

        <Col xs={12} sm={12} md={6}>
          <div style={fieldLabelStyle}>市场板块</div>
          <Select
            mode="multiple"
            style={{ width: "100%" }}
            placeholder="全部市场"
            value={filters.markets || []}
            onChange={(v) => set({ markets: v.length > 0 ? v : null, page: 1 })}
            options={[
              { label: "主板", value: "主板" },
              { label: "创业板", value: "创业板" },
              { label: "科创板", value: "科创板" },
              { label: "北交所", value: "北交所" },
            ]}
            size="small"
            maxTagCount={1}
            allowClear
          />
        </Col>

        <Col xs={12} sm={12} md={6}>
          <div style={fieldLabelStyle}>行业板块</div>
          <Select
            mode="multiple"
            style={{ width: "100%" }}
            placeholder="选择行业（可多选）"
            value={filters.industries || []}
            onChange={(v) => set({ industries: v.length > 0 ? v : null, page: 1 })}
            options={industryOptions}
            filterOption={(input, option) => (option?.label ?? "").toLowerCase().includes(input.toLowerCase())}
            size="small"
            maxTagCount={1}
            allowClear
            showSearch
          />
        </Col>

        <Col xs={12} sm={12} md={6}>
          <div style={fieldLabelStyle}>概念题材</div>
          <Select
            mode="multiple"
            style={{ width: "100%" }}
            placeholder="选择概念（可多选）"
            value={filters.concepts || []}
            onChange={(v) => set({ concepts: v.length > 0 ? v : null, page: 1 })}
            options={conceptOptions}
            filterOption={(input, option) => (option?.label ?? "").toLowerCase().includes(input.toLowerCase())}
            size="small"
            maxTagCount={1}
            allowClear
            showSearch
          />
        </Col>

        <Col xs={12} sm={12} md={6}>
          <div style={fieldLabelStyle}>排序维度</div>
          <Space.Compact style={{ width: "100%" }}>
            <Select
              size="small"
              value={filters.sort_by}
              onChange={(v) => set({ sort_by: v })}
              style={{ width: "65%" }}
              options={[
                { label: "综合评分", value: "composite_score" },
                { label: "市值", value: "market_cap" },
                { label: "PE", value: "pe" },
                { label: "PB", value: "pb" },
                { label: "价格", value: "price" },
                { label: "涨跌幅", value: "change_pct" },
                { label: "换手率", value: "turnover_pct" },
                { label: "量比", value: "volume_ratio" },
                { label: "60日涨幅", value: "change_pct_60d" },
                { label: "振幅", value: "amplitude" },
                { label: "成交量", value: "volume" },
              ]}
            />
            <Select
              size="small"
              value={filters.sort_order}
              onChange={(v) => set({ sort_order: v as "asc" | "desc" })}
              style={{ width: "35%" }}
              options={[
                { label: "降序", value: "desc" },
                { label: "升序", value: "asc" },
              ]}
            />
          </Space.Compact>
        </Col>
      </Row>

      {/* 快捷开关与折叠控制条 */}
      <div
        style={{
          marginTop: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Space size="middle" wrap>
          <Space>
            <Switch size="small" checked={filters.exclude_st || false} onChange={(v) => set({ exclude_st: v, page: 1 })} />
            <Text style={{ fontSize: "var(--c-font-sm)", color: mutedTextStyle.color }}>剔除ST风险股</Text>
          </Space>
          <Space>
            <Switch size="small" checked={filters.is_broken_net || false} onChange={(v) => set({ is_broken_net: v, page: 1 })} />
            <Text style={{ fontSize: "var(--c-font-sm)", color: mutedTextStyle.color }}>仅破净股 (PB≤1.0)</Text>
          </Space>
          <Button
            type="text"
            size="small"
            icon={<ControlOutlined />}
            onClick={() => setAdvancedOpen((v) => !v)}
            style={{ fontSize: "var(--c-font-sm)" }}
          >
            高级筛选{" "}
            {activeAdvancedCount > 0 ? (
              <Badge count={activeAdvancedCount} size="small" style={{ backgroundColor: "#1890ff" }} />
            ) : null}
            {advancedOpen ? <UpOutlined style={{ fontSize: 10, marginLeft: 4 }} /> : <DownOutlined style={{ fontSize: 10, marginLeft: 4 }} />}
          </Button>
        </Space>

        <Space>
          <Button icon={<ReloadOutlined />} onClick={onReset} size="small">重置</Button>
          <Button type="primary" icon={<SearchOutlined />} onClick={onSearch} size="small">筛选</Button>
        </Space>
      </div>

      {/* 高级筛选区（折叠/展开，量价动量与估值百分位） */}
      {advancedOpen && (
        <div
          style={{
            marginTop: 12,
            padding: "var(--c-pad-inset, 7px 12px)",
            borderRadius: 6,
            background: "var(--c-nested-bg)",
            border: "1px dashed var(--c-border)",
          }}
        >
          <div style={{ marginBottom: 8, fontSize: "var(--c-font-sm)", fontWeight: 600, color: mutedTextStyle.color }}>
            量价动量与风险控制
          </div>
          <Row gutter={[12, 10]}>
            <RangeField label="涨跌幅(%)" min={filters.change_pct_min} max={filters.change_pct_max} onMinChange={(v) => set({ change_pct_min: v })} onMaxChange={(v) => set({ change_pct_max: v })} onPressEnter={onSearch} step={0.1} minPlaceholder="-10" maxPlaceholder="10" />
            <RangeField label="换手率(%)" min={filters.turnover_pct_min} max={filters.turnover_pct_max} onMinChange={(v) => set({ turnover_pct_min: v })} onMaxChange={(v) => set({ turnover_pct_max: v })} onPressEnter={onSearch} step={0.5} minPlaceholder="0" maxPlaceholder="50" />
            <RangeField label="量比" min={filters.volume_ratio_min} max={filters.volume_ratio_max} onMinChange={(v) => set({ volume_ratio_min: v })} onMaxChange={(v) => set({ volume_ratio_max: v })} onPressEnter={onSearch} step={0.2} minPlaceholder="0" maxPlaceholder="10" />
            <RangeField label="60日涨幅(%)" min={filters.change_pct_60d_min} max={filters.change_pct_60d_max} onMinChange={(v) => set({ change_pct_60d_min: v })} onMaxChange={(v) => set({ change_pct_60d_max: v })} onPressEnter={onSearch} step={1} minPlaceholder="-50" maxPlaceholder="200" />
            <RangeField label="振幅(%)" min={filters.amplitude_min} max={filters.amplitude_max} onMinChange={(v) => set({ amplitude_min: v })} onMaxChange={(v) => set({ amplitude_max: v })} onPressEnter={onSearch} step={0.5} minPlaceholder="0" maxPlaceholder="30" />
            <Col xs={12} sm={12} md={6}>
              <div style={fieldLabelStyle}>最低日成交额(亿)</div>
              <InputNumber
                style={{ width: "100%" }}
                size="small"
                min={0}
                step={0.5}
                placeholder="0"
                value={filters.min_amount_yi}
                onChange={(v) => set({ min_amount_yi: v })}
                onPressEnter={onSearch}
              />
            </Col>
          </Row>

          <Row gutter={[12, 10]} style={{ marginTop: 10, paddingTop: 10, borderTop: "1px dashed var(--c-border)" }}>
            <Col span={24}>
              <Space>
                <Switch size="small" checked={showPercentile} onChange={onShowPercentileChange} />
                <Text style={{ fontSize: "var(--c-font-sm)", color: mutedTextStyle.color }}>估值百分位过滤</Text>
                {showPercentile && <Text type="secondary" style={{ ...mutedTextStyle, fontSize: "var(--c-font-xs)" }}>（近三年历史分位）</Text>}
              </Space>
            </Col>
            {showPercentile && (
              <>
                <Col xs={24} sm={12}>
                  <div style={fieldLabelStyle}>PE百分位 ≤ {pePercentileMax}%</div>
                  <Slider min={0} max={100} value={pePercentileMax} onChange={onPePercentileMaxChange} marks={{ 0: "0%", 30: "30%", 50: "50%", 100: "100%" }} />
                </Col>
                <Col xs={24} sm={12}>
                  <div style={fieldLabelStyle}>PB百分位 ≤ {pbPercentileMax}%</div>
                  <Slider min={0} max={100} value={pbPercentileMax} onChange={onPbPercentileMaxChange} marks={{ 0: "0%", 30: "30%", 50: "50%", 100: "100%" }} />
                </Col>
              </>
            )}
          </Row>
        </div>
      )}

      {/* 已选条件快捷清除条 */}
      <ActiveFiltersBar
        filters={filters}
        onFiltersChange={onFiltersChange}
        onSearch={onSearch}
        onReset={onReset}
        showPercentile={showPercentile}
        onShowPercentileChange={onShowPercentileChange}
        pePercentileMax={pePercentileMax}
        pbPercentileMax={pbPercentileMax}
      />
    </div>
  );
}
