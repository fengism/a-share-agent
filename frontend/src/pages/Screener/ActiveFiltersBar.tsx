import { CloseCircleOutlined, FilterOutlined } from "@ant-design/icons";
import { Button, Space, Tag } from "antd";
import type { ScreenerFilter } from "../../types/stock";
import { useColors } from "../../styles/ui";

export interface ActiveFiltersBarProps {
  filters: ScreenerFilter;
  onFiltersChange: (filters: ScreenerFilter) => void;
  onSearch: () => void;
  onReset: () => void;
  showPercentile?: boolean;
  onShowPercentileChange?: (v: boolean) => void;
  pePercentileMax?: number;
  pbPercentileMax?: number;
}

interface ActiveFilterItem {
  key: string;
  label: string;
  onRemove: () => void;
}

function formatRangeLabel(label: string, min?: number | null, max?: number | null, unit = ""): string | null {
  if (min != null && max != null) {
    return `${label}: ${min} ~ ${max}${unit}`;
  }
  if (min != null) {
    return `${label} ≥ ${min}${unit}`;
  }
  if (max != null) {
    return `${label} ≤ ${max}${unit}`;
  }
  return null;
}

export default function ActiveFiltersBar({
  filters,
  onFiltersChange,
  onSearch,
  onReset,
  showPercentile,
  onShowPercentileChange,
  pePercentileMax = 50,
  pbPercentileMax = 50,
}: ActiveFiltersBarProps) {
  const c = useColors();
  const activeItems: ActiveFilterItem[] = [];

  // Range filters
  const peLabel = formatRangeLabel("PE", filters.pe_min, filters.pe_max);
  if (peLabel) {
    activeItems.push({
      key: "pe",
      label: peLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, pe_min: null, pe_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const pbLabel = formatRangeLabel("PB", filters.pb_min, filters.pb_max);
  if (pbLabel) {
    activeItems.push({
      key: "pb",
      label: pbLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, pb_min: null, pb_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const priceLabel = formatRangeLabel("股价", filters.price_min, filters.price_max, "元");
  if (priceLabel) {
    activeItems.push({
      key: "price",
      label: priceLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, price_min: null, price_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const marketCapLabel = formatRangeLabel("市值", filters.market_cap_min, filters.market_cap_max, "亿");
  if (marketCapLabel) {
    activeItems.push({
      key: "market_cap",
      label: marketCapLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, market_cap_min: null, market_cap_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const changePctLabel = formatRangeLabel("涨跌幅", filters.change_pct_min, filters.change_pct_max, "%");
  if (changePctLabel) {
    activeItems.push({
      key: "change_pct",
      label: changePctLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, change_pct_min: null, change_pct_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const turnoverLabel = formatRangeLabel("换手率", filters.turnover_pct_min, filters.turnover_pct_max, "%");
  if (turnoverLabel) {
    activeItems.push({
      key: "turnover_pct",
      label: turnoverLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, turnover_pct_min: null, turnover_pct_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const amplitudeLabel = formatRangeLabel("振幅", filters.amplitude_min, filters.amplitude_max, "%");
  if (amplitudeLabel) {
    activeItems.push({
      key: "amplitude",
      label: amplitudeLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, amplitude_min: null, amplitude_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const volumeRatioLabel = formatRangeLabel("量比", filters.volume_ratio_min, filters.volume_ratio_max);
  if (volumeRatioLabel) {
    activeItems.push({
      key: "volume_ratio",
      label: volumeRatioLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, volume_ratio_min: null, volume_ratio_max: null, page: 1 });
        onSearch();
      },
    });
  }

  const changePct60dLabel = formatRangeLabel("60日涨幅", filters.change_pct_60d_min, filters.change_pct_60d_max, "%");
  if (changePct60dLabel) {
    activeItems.push({
      key: "change_pct_60d",
      label: changePct60dLabel,
      onRemove: () => {
        onFiltersChange({ ...filters, change_pct_60d_min: null, change_pct_60d_max: null, page: 1 });
        onSearch();
      },
    });
  }

  if (filters.is_broken_net) {
    activeItems.push({
      key: "is_broken_net",
      label: "仅破净股 (PB≤1.0)",
      onRemove: () => {
        onFiltersChange({ ...filters, is_broken_net: false, page: 1 });
        onSearch();
      },
    });
  }

  if (filters.exclude_st) {
    activeItems.push({
      key: "exclude_st",
      label: "剔除ST风险股",
      onRemove: () => {
        onFiltersChange({ ...filters, exclude_st: false, page: 1 });
        onSearch();
      },
    });
  }

  if (filters.min_amount_yi != null && filters.min_amount_yi > 0) {
    activeItems.push({
      key: "min_amount_yi",
      label: `成交额 ≥ ${filters.min_amount_yi}亿`,
      onRemove: () => {
        onFiltersChange({ ...filters, min_amount_yi: null, page: 1 });
        onSearch();
      },
    });
  }

  // Multi selects
  if (filters.markets && filters.markets.length > 0) {
    filters.markets.forEach((market) => {
      activeItems.push({
        key: `market-${market}`,
        label: `板块: ${market}`,
        onRemove: () => {
          const next = (filters.markets || []).filter((m) => m !== market);
          onFiltersChange({ ...filters, markets: next.length > 0 ? next : null, page: 1 });
          onSearch();
        },
      });
    });
  }

  if (filters.industries && filters.industries.length > 0) {
    filters.industries.forEach((industry) => {
      activeItems.push({
        key: `industry-${industry}`,
        label: `行业: ${industry}`,
        onRemove: () => {
          const next = (filters.industries || []).filter((i) => i !== industry);
          onFiltersChange({ ...filters, industries: next.length > 0 ? next : null, page: 1 });
          onSearch();
        },
      });
    });
  }

  if (filters.concepts && filters.concepts.length > 0) {
    filters.concepts.forEach((concept) => {
      activeItems.push({
        key: `concept-${concept}`,
        label: `概念: ${concept}`,
        onRemove: () => {
          const next = (filters.concepts || []).filter((c) => c !== concept);
          onFiltersChange({ ...filters, concepts: next.length > 0 ? next : null, page: 1 });
          onSearch();
        },
      });
    });
  }

  // Percentiles
  if (showPercentile) {
    activeItems.push({
      key: "percentile",
      label: `分位: PE≤${pePercentileMax}% · PB≤${pbPercentileMax}%`,
      onRemove: () => {
        onShowPercentileChange?.(false);
      },
    });
  }

  if (activeItems.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "6px 8px",
        padding: "var(--c-pad-inset, 7px 12px)",
        marginTop: 12,
        backgroundColor: c.nestedBg || "rgba(0, 0, 0, 0.02)",
        borderRadius: 6,
        border: `1px dashed ${c.border}`,
      }}
    >
      <Space orientation="horizontal" size={4} style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
        <FilterOutlined />
        <span>生效条件 ({activeItems.length})：</span>
      </Space>
      {activeItems.map((item) => (
        <Tag
          key={item.key}
          closable
          onClose={(e) => {
            e.preventDefault();
            item.onRemove();
          }}
          closeIcon={<CloseCircleOutlined style={{ fontSize: 11 }} />}
          style={{
            margin: 0,
            borderRadius: 4,
            fontSize: "var(--c-font-xs)",
            backgroundColor: c.cardBg,
            borderColor: c.border,
            color: c.textPrimary,
          }}
        >
          {item.label}
        </Tag>
      ))}
      <Button
        type="link"
        size="small"
        danger
        onClick={onReset}
        style={{ padding: "0 4px", fontSize: "var(--c-font-xs)", height: "auto" }}
      >
        清空全部
      </Button>
    </div>
  );
}
