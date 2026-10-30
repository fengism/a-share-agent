import { useMemo, useState } from "react";
import { Button, Input, Progress, Segmented, Table, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { FundOutlined, SearchOutlined, StarFilled, StarOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import dayjs from "dayjs";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, semanticTagStyle } from "../../styles/ui";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queryHooks/watchlist";
import { isHkStockCode } from "../../utils/stockLinks";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";
import type { ConceptConstituent } from "../../api/queryHooks/concept";
import BreadthBar from "./BreadthBar";
import { limitUpBadge } from "./conceptSelection";
import { closeSourceDate } from "./quoteSource";

type SortKey = "change_pct" | "amount" | "code";

interface Props {
  concept: string;
  items: ConceptConstituent[] | undefined;
  total: number;
  isLoading: boolean;
  error: unknown;
  onRetry: () => void;
  /** 已请求过行情的代码数量（0 = 尚未请求，走纯本地身份列表） */
  quoteRequested: number;
  /** 行情请求进行中 */
  quotePending: boolean;
  /** 上游行情不可用且无本地兜底：停止自动补齐时置位 */
  quoteUnavailable: boolean;
  /** 行情快照时间（全量补齐后展示，帮助判断数据新鲜度） */
  quotedAt?: string | null;
  /** 点击行内「其他概念」标签 → 切换到该概念 */
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
  total,
  isLoading,
  error,
  onRetry,
  quoteRequested,
  quotePending,
  quoteUnavailable,
  quotedAt,
  onSelectConcept,
}: Props) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  // 默认按涨跌幅：用户打开概念页最关心"谁在领涨"；缺失行情沉底（见排序器）
  const [sortKey, setSortKey] = useState<SortKey>("change_pct");
  const [descending, setDescending] = useState(true);
  const [pendingWatchCode, setPendingWatchCode] = useState<string | null>(null);
  // 本地筛选：方向/涨停 + 名称/代码关键字，全部纯前端即时计算
  const [directionFilter, setDirectionFilter] = useState<"all" | "up" | "down" | "limit">("all");
  const [filterText, setFilterText] = useState("");

  const maxAbsChange = useMemo(() => {
    let max = 1;
    for (const item of items ?? []) {
      if (item.change_pct != null && Math.abs(item.change_pct) > max) max = Math.abs(item.change_pct);
    }
    return max;
  }, [items]);

  const filteredItems = useMemo(() => {
    const text = filterText.trim().toLowerCase();
    return (items ?? []).filter((item) => {
      if (directionFilter === "up" && !(item.change_pct != null && item.change_pct > 0)) return false;
      if (directionFilter === "down" && !(item.change_pct != null && item.change_pct < 0)) return false;
      if (directionFilter === "limit" && !limitUpBadge(item.code, item.change_pct)) return false;
      if (text && !item.name.toLowerCase().includes(text) && !item.code.includes(text)) return false;
      return true;
    });
  }, [items, directionFilter, filterText]);

  const sorted = useMemo(() => {
    const rows = [...filteredItems];
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
  }, [filteredItems, sortKey, descending]);

  /**
   * 涨跌家数来自已加载行情：自动补齐完成后即与全样本一致。
   * 加载进度在表头展示（行情 x/y），不再需要用户手动触发全量。
   */
  const breadth = useMemo(() => {
    let up = 0;
    let down = 0;
    let flat = 0;
    for (const item of items ?? []) {
      if (item.change_pct == null) continue;
      if (item.change_pct > 0) up += 1;
      else if (item.change_pct < 0) down += 1;
      else flat += 1;
    }
    return { up, down, flat };
  }, [items]);

  const totalCount = total ?? 0;
  const quoteComplete = totalCount > 0 && quoteRequested >= totalCount;

  // ── 自选快捷操作 ──
  const watchlistQuery = useWatchlist();
  const addWatchlist = useAddWatchlistItem();
  const removeWatchlist = useDeleteWatchlistItem();
  const watchedCodes = useMemo(() => {
    const set = new Set<string>();
    for (const item of watchlistQuery.data?.items ?? []) {
      if (!isHkStockCode(item.stock_code)) set.add(item.stock_code);
    }
    return set;
  }, [watchlistQuery.data]);

  const toggleWatch = (record: ConceptConstituent) => {
    const code = record.code;
    setPendingWatchCode(code);
    const settle = () => setPendingWatchCode(null);
    if (watchedCodes.has(code)) {
      removeWatchlist.mutate(code, { onSettled: settle });
    } else {
      addWatchlist.mutate(
        { stock_code: code, note: "" },
        { onSettled: settle },
      );
    }
  };

  const columns: ColumnsType<ConceptConstituent> = [
      {
        title: "代码",
        dataIndex: "code",
        width: isNarrow ? 80 : 92,
        fixed: "left",
        render: (code: string, record) => (
          <StockExternalLink
            code={code}
            name={record.name}
            className="concept-stock-code financial-num"
            style={{ fontFamily: "var(--c-font-mono)", color: c.primary, fontWeight: 500 }}
          >
            {code}
          </StockExternalLink>
        ),
      },
      {
        title: "名称",
        dataIndex: "name",
        width: isNarrow ? 92 : 104,
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
        width: isNarrow ? 76 : 84,
        align: "right",
        render: (value: number | null, record: ConceptConstituent) => {
          // 实时行情缺失时后端会用本地当日已确认收盘价兜底，此时必须显式区分，
          // 否则用户会把收盘价误读成盘中实时价。
          const closeDate = closeSourceDate(record.quote_source);
          return (
            <Tooltip title={closeDate ? `收盘价（${closeDate}）` : undefined}>
              <span
                className="financial-num"
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
        width: isNarrow ? 104 : 124,
        align: "right",
        sorter: true,
        render: (value: number | null, record) => {
          const badge = limitUpBadge(record.code, value);
          // 涨跌幅背景条：以面板内最大波动为满格，红绿随方向，一眼扫出极端个股
          const strength = value == null ? 0 : Math.min(Math.abs(value) / maxAbsChange, 1);
          const barColor = value == null || value === 0 ? "transparent" : value > 0 ? c.up : c.down;
          return (
            <span
              className="concept-change-cell financial-num"
              style={{
                background:
                  strength > 0
                    ? `linear-gradient(to left, ${barColor}2e ${strength * 100}%, transparent ${strength * 100}%)`
                    : undefined,
              }}
            >
              <ChangeValue value={value} fontWeight={600} />
              {badge ? (
                <Tag
                  className="concept-change-cell__badge"
                  style={{
                    ...semanticTagStyle(badge),
                    fontSize: 10,
                    lineHeight: "16px",
                    paddingInline: 4,
                    marginInlineEnd: 0,
                  }}
                >
                  {badge === "up" ? "涨停" : "跌停"}
                </Tag>
              ) : null}
            </span>
          );
        },
      },
      {
        title: "成交额",
        dataIndex: "amount",
        width: isNarrow ? 80 : 92,
        align: "right",
        sorter: true,
        render: (value: number | null) => (
          <span className="financial-num" style={{ color: c.textSecondary }}>
            {formatAmount(value)}
          </span>
        ),
      },
      // 其他概念标签：只占宽屏空间，窄屏优先保证行情列可读
      ...(isNarrow
        ? []
        : [
            {
              title: "其他概念",
              key: "related_concepts",
              width: 190,
              render: (_: unknown, record: ConceptConstituent) => {
                const tags = record.related_concepts ?? [];
                if (!tags.length) return <span style={{ color: c.textMuted }}>-</span>;
                const [first, second, ...rest] = tags;
                return (
                  <span className="concept-other-tags">
                    {[first, second].filter(Boolean).map((name) => (
                      <Tooltip key={name} title={`查看「${name}」概念详情`}>
                        <Tag
                          className="concept-other-tags__tag"
                          style={{ ...semanticTagStyle("primary"), cursor: "pointer", marginInlineEnd: 0 }}
                          onClick={() => onSelectConcept(name)}
                        >
                          {name}
                        </Tag>
                      </Tooltip>
                    ))}
                    {rest.length ? (
                      <Tooltip title={rest.join("、")}>
                        <Tag
                          className="concept-other-tags__tag"
                          style={{ marginInlineEnd: 0, cursor: "help" }}
                        >
                          +{rest.length}
                        </Tag>
                      </Tooltip>
                    ) : null}
                  </span>
                );
              },
            },
          ]),
      // 自选/分析快捷操作只占宽屏空间，窄屏以行点击进详情为主
      ...(isNarrow
        ? []
        : [
            {
              title: "",
              key: "actions",
              width: 88,
              align: "right" as const,
              render: (_: unknown, record: ConceptConstituent) => {
                const watched = watchedCodes.has(record.code);
                return (
                  <span className="concept-row-actions">
                    <Tooltip title={watched ? "移出自选" : "加入自选"}>
                      <Button
                        type="text"
                        size="small"
                        aria-label={`${watched ? "移出自选" : "加入自选"}-${record.name || record.code}`}
                        icon={
                          watched ? <StarFilled style={{ color: c.warning }} /> : <StarOutlined />
                        }
                        loading={pendingWatchCode === record.code}
                        onClick={() => toggleWatch(record)}
                      />
                    </Tooltip>
                    <Tooltip title="个股深度分析">
                      <Link to={buildStockAnalysisUrl(record.code)} aria-label={`个股分析-${record.name || record.code}`}>
                        <Button type="text" size="small" icon={<FundOutlined />} />
                      </Link>
                    </Tooltip>
                  </span>
                );
              },
            },
          ]),
  ];

  const quoteProgress = quoteRequested > 0 && !quoteComplete;

  return (
    <div className="concept-constituent-panel" style={{ display: "flex", flexDirection: "column", gap: isNarrow ? 8 : 10, minWidth: 0 }}>
      <div className="concept-constituent-header">
        <div className="concept-constituent-info">
          <strong style={{ fontSize: 15, color: c.textPrimary }}>成分股</strong>
          <span style={{ fontSize: 12, color: c.textMuted }}>
            {totalCount} 只
            {filteredItems.length !== totalCount ? ` · 筛出 ${filteredItems.length}` : ""}
          </span>
          <BreadthBar up={breadth.up} flat={breadth.flat} down={breadth.down} />
          {quoteProgress ? (
            <Tooltip title="行情按批次自动补齐，完成后涨跌家数与排序即为全量结果">
              <span className="concept-quote-progress">
                <Progress
                  percent={Math.round((quoteRequested / Math.max(totalCount, 1)) * 100)}
                  size="small"
                  showInfo={false}
                  style={{ width: 72, marginInlineEnd: 6 }}
                  strokeColor={c.primary}
                />
                <span className="financial-num" style={{ color: c.textMuted, fontSize: 12 }}>
                  {quotePending ? `行情 ${quoteRequested}/${totalCount}…` : `行情 ${quoteRequested}/${totalCount}`}
                </span>
              </span>
            </Tooltip>
          ) : null}
          {quoteUnavailable ? (
            <span style={{ fontSize: 12, color: c.textMuted }}>实时行情暂不可用，已展示可获得的最新价格</span>
          ) : null}
          {quotedAt ? (
            <Tooltip title="当前行情的快照时间，随每次补齐更新">
              <span className="financial-num" style={{ fontSize: 12, color: c.textMuted }}>
                行情 {dayjs(quotedAt).format("HH:mm:ss")}
              </span>
            </Tooltip>
          ) : null}
        </div>
        <div className="concept-constituent-sort">
          <Segmented
            size="small"
            value={directionFilter}
            options={[
              { label: "全部", value: "all" },
              { label: "上涨", value: "up" },
              { label: "下跌", value: "down" },
              { label: "涨停", value: "limit" },
            ]}
            onChange={(value) => setDirectionFilter(value as typeof directionFilter)}
          />
          <Input
            size="small"
            allowClear
            value={filterText}
            onChange={(event) => setFilterText(event.target.value)}
            placeholder="搜名称/代码"
            prefix={<SearchOutlined style={{ color: c.textMuted }} />}
            style={{ width: isNarrow ? "100%" : 150 }}
          />
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
      </div>

      <SectionDataState
        isLoading={isLoading && !items?.length}
        error={items?.length ? undefined : error}
        onRetry={onRetry}
        isEmpty={!isLoading && !error && !items?.length}
        emptyText={`暂无「${concept}」的成分股数据`}
        errorTitle="成分股加载失败"
        minHeight={isNarrow ? 300 : 380}
      >
        <Table
          size="small"
          rowKey="code"
          columns={columns}
          dataSource={sorted}
          pagination={false}
          virtual
          scroll={{ x: isNarrow ? 432 : 774, y: isNarrow ? 320 : 400 }}
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

      <p className="concept-index-note" style={{ color: c.textMuted }}>
        点名称或代码进入个股详情，星标加入自选。灰色价格表示当日收盘价（实时行情暂缺时的兜底值）。
      </p>
    </div>
  );
}
