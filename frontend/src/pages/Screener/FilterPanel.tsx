import { Row, Col, InputNumber, Select, Button, Space, Switch, Slider, Typography } from "antd";
import { SearchOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ScreenerFilter } from "../../types/stock";
import { fieldLabelStyle, mutedTextStyle } from "../../styles/ui";

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
}

function RangeField({ label, min, max, onMinChange, onMaxChange, minPlaceholder = "最小", maxPlaceholder = "最大", step = 0.01 }: RangeFieldProps) {
  return (
    <Col span={8}>
      <div style={fieldLabelStyle}>{label}</div>
      <Space.Compact style={{ width: "100%" }}>
        <InputNumber
          style={{ width: "50%" }}
          value={min}
          onChange={onMinChange}
          placeholder={minPlaceholder}
          step={step}
          size="small"
        />
        <InputNumber
          style={{ width: "50%" }}
          value={max}
          onChange={onMaxChange}
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
  onSearch: () => void;
  onReset: () => void;
  // Percentile
  showPercentile: boolean;
  onShowPercentileChange: (v: boolean) => void;
  pePercentileMax: number;
  pbPercentileMax: number;
  onPePercentileMaxChange: (v: number) => void;
  onPbPercentileMaxChange: (v: number) => void;
}

export default function FilterPanel({
  filters, onFiltersChange, industries, onSearch, onReset,
  showPercentile, onShowPercentileChange,
  pePercentileMax, pbPercentileMax, onPePercentileMaxChange, onPbPercentileMaxChange,
}: Props) {
  const set = (patch: Partial<ScreenerFilter>) => {
    onFiltersChange({ ...filters, ...patch });
  };

  return (
    <div>
      <Row gutter={[16, 12]}>
        <RangeField label="PE(TTM)" min={filters.pe_min} max={filters.pe_max}
          onMinChange={(v) => set({ pe_min: v })} onMaxChange={(v) => set({ pe_max: v })}
          step={1} minPlaceholder="0" maxPlaceholder="100" />
        <RangeField label="PB" min={filters.pb_min} max={filters.pb_max}
          onMinChange={(v) => set({ pb_min: v })} onMaxChange={(v) => set({ pb_max: v })}
          step={0.1} minPlaceholder="0" maxPlaceholder="50" />
        <RangeField label="股价(元)" min={filters.price_min} max={filters.price_max}
          onMinChange={(v) => set({ price_min: v })} onMaxChange={(v) => set({ price_max: v })}
          step={1} minPlaceholder="0" maxPlaceholder="1000" />
        <RangeField label="市值(亿)" min={filters.market_cap_min} max={filters.market_cap_max}
          onMinChange={(v) => set({ market_cap_min: v })} onMaxChange={(v) => set({ market_cap_max: v })}
          step={10} minPlaceholder="0" maxPlaceholder="50000" />
        <RangeField label="涨跌幅(%)" min={filters.change_pct_min} max={filters.change_pct_max}
          onMinChange={(v) => set({ change_pct_min: v })} onMaxChange={(v) => set({ change_pct_max: v })}
          step={0.1} minPlaceholder="-10" maxPlaceholder="10" />
        <RangeField label="换手率(%)" min={filters.turnover_pct_min} max={filters.turnover_pct_max}
          onMinChange={(v) => set({ turnover_pct_min: v })} onMaxChange={(v) => set({ turnover_pct_max: v })}
          step={0.5} minPlaceholder="0" maxPlaceholder="50" />
      </Row>

      <Row gutter={[16, 12]} style={{ marginTop: 12 }}>
        <Col span={12}>
          <div style={fieldLabelStyle}>行业板块</div>
          <Select
            mode="multiple"
            style={{ width: "100%" }}
            placeholder="选择行业（可多选）"
            value={filters.industries || []}
            onChange={(v) => set({ industries: v.length > 0 ? v : null })}
            options={industries.map((n) => ({ label: n, value: n }))}
            size="small"
            maxTagCount={3}
            allowClear
          />
        </Col>
        <Col span={6}>
          <div style={fieldLabelStyle}>排序</div>
          <Space>
            <Select
              size="small"
              value={filters.sort_by}
              onChange={(v) => set({ sort_by: v })}
              style={{ width: 100 }}
              options={[
                { label: "市值", value: "market_cap" },
                { label: "PE", value: "pe" },
                { label: "PB", value: "pb" },
                { label: "价格", value: "price" },
                { label: "涨跌幅", value: "change_pct" },
                { label: "换手率", value: "turnover_pct" },
                { label: "成交量", value: "volume" },
              ]}
            />
            <Select
              size="small"
              value={filters.sort_order}
              onChange={(v) => set({ sort_order: v as "asc" | "desc" })}
              style={{ width: 70 }}
              options={[
                { label: "降序", value: "desc" },
                { label: "升序", value: "asc" },
              ]}
            />
          </Space>
        </Col>
        <Col span={6} style={{ textAlign: "right", paddingTop: 20 }}>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={onReset} size="small">重置</Button>
            <Button type="primary" icon={<SearchOutlined />} onClick={onSearch} size="small">筛选</Button>
          </Space>
        </Col>
      </Row>

      {/* 估值百分位 */}
      <Row gutter={[16, 12]} style={{ marginTop: 12, borderTop: "1px solid #f2f3f5", paddingTop: 12 }}>
        <Col span={24}>
          <Space>
            <Switch size="small" checked={showPercentile} onChange={onShowPercentileChange} />
            <Text style={{ fontSize: 13, color: "#9ca3af" }}>估值百分位过滤</Text>
            {showPercentile && <Text type="secondary" style={{ ...mutedTextStyle, fontSize: 11 }}>（按需计算，可能需要较长时间）</Text>}
          </Space>
        </Col>
        {showPercentile && (
          <>
            <Col span={12}>
              <div style={fieldLabelStyle}>PE百分位 ≤ {pePercentileMax}%</div>
              <Slider min={0} max={100} value={pePercentileMax} onChange={onPePercentileMaxChange}
                marks={{ 0: "0%", 30: "30%", 50: "50%", 100: "100%" }} />
            </Col>
            <Col span={12}>
              <div style={fieldLabelStyle}>PB百分位 ≤ {pbPercentileMax}%</div>
              <Slider min={0} max={100} value={pbPercentileMax} onChange={onPbPercentileMaxChange}
                marks={{ 0: "0%", 30: "30%", 50: "50%", 100: "100%" }} />
            </Col>
          </>
        )}
      </Row>
    </div>
  );
}
