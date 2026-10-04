import { useMemo, useState } from "react";
import { Segmented, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { RiseOutlined } from "@ant-design/icons";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useColors, semanticTagStyle } from "../../styles/ui";
import type { ConceptConstituent, RelatedConcept } from "../../api/queryHooks/concept";

type SortKey = "change_pct" | "amount" | "code";

interface Props {
  concept: string;
  items: ConceptConstituent[] | undefined;
  related: RelatedConcept[];
  total: number;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  quoteSource: string | null;
  /** 点击相关概念 → 切换左侧概念，实现概念间联动 */
  onSelectConcept: (concept: string) => void;
}

function formatAmount(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return String(Math.round(value));
}

export default function ConceptConstituentPanel({
  concept,
  items,
  related,
  total,
  isLoading,
  error,
  onRetry,
  quoteSource,
  onSelectConcept,
}: Props) {
  const c = useColors();
  const [sortKey, setSortKey] = useState<SortKey>("change_pct");
  const [descending, setDescending] = useState(true);

  const sorted = useMemo(() => {
    const rows = [...(items ?? [])];
    rows.sort((a, b) => {
      if (sortKey === "code") return a.code.localeCompare(b.code);
      const left = sortKey === "change_pct" ? a.change_pct : a.amount;
      const right = sortKey === "change_pct" ? b.change_pct : b.amount;
      // 缺失值永远排在最后，不管升降序
      if (left == null && right == null) return 0;
      if (left == null) return 1;
      if (right == null) return -1;
      return descending ? right - left : left - right;
    });
    return rows;
  }, [items, sortKey, descending]);

  const breadth = useMemo(() => {
    let up = 0;
    let down = 0;
    let flat = 0;
    let quoted = 0;
    for (const item of items ?? []) {
      if (item.change_pct == null) continue;
      quoted += 1;
      if (item.change_pct > 0) up += 1;
      else if (item.change_pct < 0) down += 1;
      else flat += 1;
    }
    return { up, down, flat, quoted };
  }, [items]);

  const columns: ColumnsType<ConceptConstituent> = [
    {
      title: "代码",
      dataIndex: "code",
      width: 96,
      fixed: "left",
      render: (code: string, record) => (
        <StockExternalLink
          code={code}
          name={record.name}
          className="concept-stock-code"
          style={{ fontFamily: "var(--c-font-mono)", color: c.primary, fontWeight: 500 }}
        >
          {code}
        </StockExternalLink>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      width: 108,
      ellipsis: true,
      render: (name: string, record) => (
        <StockExternalLink code={record.code} name={name} style={{ color: c.textPrimary }}>
          {name || "-"}
        </StockExternalLink>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      width: 84,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontFamily: "var(--c-font-mono)", color: c.textPrimary }}>
          {value == null ? "-" : value.toFixed(2)}
        </span>
      ),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 92,
      align: "right",
      sorter: true,
      render: (value: number | null) => <ChangeValue value={value} fontWeight={600} />,
    },
    {
      title: "成交额",
      dataIndex: "amount",
      width: 92,
      align: "right",
      sorter: true,
      render: (value: number | null) => (
        <span className="financial-num" style={{ color: c.textSecondary }}>
          {formatAmount(value)}
        </span>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 10,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <strong style={{ fontSize: 15, color: c.textPrimary }}>成分股</strong>
          <span style={{ fontSize: 12, color: c.textMuted }}>
            {total} 只
            {breadth.quoted > 0 ? ` · 上涨 ${breadth.up} / 下跌 ${breadth.down}` : ""}
            {quoteSource ? ` · 行情 ${quoteSource}` : ""}
          </span>
        </div>
        <Segmented
          size="small"
          value={sortKey}
          options={[
            { label: "按涨幅", value: "change_pct" },
            { label: "按成交额", value: "amount" },
            { label: "按代码", value: "code" },
          ]}
          onChange={(value) => {
            const next = value as SortKey;
            setSortKey(next);
            // 代码按字典序升序更自然，其余默认从高到低
            setDescending(next !== "code");
          }}
        />
      </div>

      {related.length ? (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 12, color: c.textMuted }}>
            <RiseOutlined /> 重叠概念
          </span>
          {related.map((item) => (
            <Tooltip key={item.name} title={`${item.overlap} 只成分股同时属于该概念`}>
              <Tag
                style={{ ...semanticTagStyle("primary"), cursor: "pointer", marginInlineEnd: 0 }}
                onClick={() => onSelectConcept(item.name)}
              >
                {item.name} {item.overlap}
              </Tag>
            </Tooltip>
          ))}
        </div>
      ) : null}

      <SectionDataState
        isLoading={isLoading && !items?.length}
        error={items?.length ? undefined : error}
        onRetry={onRetry}
        isEmpty={!isLoading && !error && !items?.length}
        emptyText={`暂无「${concept}」的成分股数据`}
        errorTitle="成分股加载失败"
        minHeight={360}
      >
        <Table
          size="small"
          rowKey="code"
          columns={columns}
          dataSource={sorted}
          pagination={false}
          virtual
          scroll={{ x: 472, y: 360 }}
          onChange={(_pagination, _filters, sorter) => {
            const target = Array.isArray(sorter) ? sorter[0] : sorter;
            if (target?.field === "change_pct") {
              setSortKey("change_pct");
              setDescending(target.order !== "ascend");
            } else if (target?.field === "amount") {
              setSortKey("amount");
              setDescending(target.order !== "ascend");
            }
          }}
        />
      </SectionDataState>

      <p style={{ margin: 0, fontSize: 11, lineHeight: 1.6, color: c.textMuted }}>
        成分股取自本地概念映射表（同花顺全A 口径），点「重叠概念」可跳到关联概念，
        点个股代码或名称进入个股详情。表格可横向滚动查看完整列。
      </p>
    </div>
  );
}

