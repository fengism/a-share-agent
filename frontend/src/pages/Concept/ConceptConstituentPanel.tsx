import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Segmented, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { RiseOutlined } from "@ant-design/icons";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useColors, semanticTagStyle } from "../../styles/ui";
import type { ConceptConstituent, RelatedConcept } from "../../api/queryHooks/concept";
import { closeSourceDate } from "./quoteSource";

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
  /** 已请求过行情的代码数量（0 = 尚未请求，走纯本地身份列表） */
  quoteRequested: number;
  /** 行情请求进行中 */
  quotePending: boolean;
  /** 请求行情：传全部代码则补齐，传部分则只补该窗口 */
  onRequestQuotes: (codes: string[]) => void;
  /** 点击相关概念 → 切换左侧概念，实现概念间联动 */
  onSelectConcept: (concept: string) => void;
}

/** 首屏按需加载的行情窗口（约两屏），够用户看清前几十行 */
const INITIAL_QUOTE_WINDOW = 80;

/** 每次滚动触底追加的行情窗口 */
const QUOTE_WINDOW_STEP = 120;

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
  quoteRequested,
  quotePending,
  onRequestQuotes,
  onSelectConcept,
}: Props) {
  const c = useColors();
  const [sortKey, setSortKey] = useState<SortKey>("code");
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

  /**
   * 涨跌家数与涨幅/成交额排序都依赖全量行情，而全量行情在上游故障时
   * 要几十秒（上游按 80 只一批串行）。这里只在用户主动点这两个排序时
   * 才补齐全量行情，否则 breadth 只统计已加载的部分并标注覆盖率。
   */
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

  const totalCount = total ?? 0;
  const quotedCount = breadth.quoted;
  const partial = quotedCount > 0 && quotedCount < totalCount;

  const loadedWindow = useRef(0);
  const inFlight = useRef(false);

  const allCodes = useMemo(() => (items ?? []).map((item) => item.code), [items]);

  /** 按需加载：首屏先取一小段，滚动到底再追加一段 */
  const loadMore = useCallback(() => {
    if (inFlight.current || !allCodes.length) return;
    const start = loadedWindow.current;
    if (start >= allCodes.length) return;
    const next = allCodes.slice(start, start + QUOTE_WINDOW_STEP);
    inFlight.current = true;
    loadedWindow.current = start + next.length;
    onRequestQuotes([...allCodes.slice(0, loadedWindow.current)]);
  }, [allCodes, onRequestQuotes]);

  // 首屏：身份列表到齐后自动拉一小段行情
  useEffect(() => {
    if (!allCodes.length || quoteRequested > 0) return;
    const next = allCodes.slice(0, INITIAL_QUOTE_WINDOW);
    loadedWindow.current = next.length;
    onRequestQuotes(next);
    // 只在首次拿到列表时触发
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allCodes.length]);

  useEffect(() => {
    inFlight.current = false;
  }, [quotePending]);

  // 补齐全量：用户点了依赖全量行情的排序/涨跌家数时才做
  const requestFullQuotes = useCallback(() => {
    loadedWindow.current = allCodes.length;
    onRequestQuotes(allCodes);
  }, [allCodes, onRequestQuotes]);

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
      render: (value: number | null, record: ConceptConstituent) => {
        // 实时行情缺失时后端会用本地当日已确认收盘价兜底，此时必须显式区分，
        // 否则用户会把收盘价误读成盘中实时价。
        const closeDate = closeSourceDate(record.quote_source);
        return (
          <Tooltip
            title={closeDate ? `收盘价（${closeDate}）` : undefined}
          >
            <span
              style={{
                fontFamily: "var(--c-font-mono)",
                color: closeDate ? c.textSecondary : c.textPrimary,
              }}
            >
              {value == null ? "-" : value.toFixed(2)}
            </span>
          </Tooltip>
        );
      },
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
            {quotedCount > 0
              ? partial
                ? ` · 上涨 ${breadth.up} / 下跌 ${breadth.down}（已加载 ${quotedCount} 只）`
                : ` · 上涨 ${breadth.up} / 下跌 ${breadth.down}`
              : ""}
            {quoteSource ? ` · 行情 ${quoteSource}` : ""}
            {partial ? (
              <a
                role="button"
                onClick={requestFullQuotes}
                style={{ marginInlineStart: 6, color: c.primary, cursor: quotePending ? "wait" : "pointer" }}
              >
                {quotePending ? "加载中…" : "加载全部行情"}
              </a>
            ) : null}
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
            // 涨幅/成交额排序与涨跌家数依赖全量行情，未补齐时结果会误导
            if (next !== "code" && partial) requestFullQuotes();
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
          onScroll={(event) => {
            // 触底前 120px 时预取下一段，避免滚到底出现空白
            const el = event.currentTarget as HTMLElement;
            if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) loadMore();
          }}
          onChange={(_pagination, _filters, sorter) => {
            const target = Array.isArray(sorter) ? sorter[0] : sorter;
            if (target?.field === "change_pct") {
              setSortKey("change_pct");
              setDescending(target.order !== "ascend");
              if (partial) requestFullQuotes();
            } else if (target?.field === "amount") {
              setSortKey("amount");
              setDescending(target.order !== "ascend");
              if (partial) requestFullQuotes();
            }
          }}
        />
      </SectionDataState>

      <p style={{ margin: 0, fontSize: 11, lineHeight: 1.6, color: c.textMuted }}>
        成分股取自本地概念映射表（同花顺全A 口径），点「重叠概念」可跳到关联概念，
        点个股代码或名称进入个股详情。行情按可见区逐段加载（上游按 80 只一批串行，
        一次拉全部上千只在上游故障时会等几十秒）；按涨幅/成交额排序会先补齐全量。
      </p>
    </div>
  );
}

