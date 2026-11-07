import { useCallback, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { Card, Segmented, Table, Tag } from "antd";
import {
  AppstoreOutlined,
  FireOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import ChangeValue from "./ChangeValue";
import DataRefreshIndicator from "./DataRefreshIndicator";
import ResponsiveMetricGrid from "./ResponsiveMetricGrid";
import SectionDataState from "./SectionDataState";
import StockExternalLink from "./StockExternalLink";
import { useContainerWidth } from "../hooks/useContainerWidth";
import {
  useThsHotConcept,
  useThsHotIndustry,
  useThsHotRank,
} from "../api/queries";
import type { ThsHotPlate, ThsHotStock } from "../types/stock";
import { formatHotValue } from "../utils/format";
import { useColors, useTokens } from "../styles/ui";
import { rankBadge } from "./rankBadge";
import "./hot-rank-board.css";

type TabKey = "stock" | "concept" | "industry";

/** 宽屏表格的内容宽度（= 各列 width 之和）。 */
const WIDE_STOCK_TABLE_WIDTH = 635;
const WIDE_PLATE_TABLE_WIDTH = 655;
/** 窄屏表格的内容宽度。 */
const NARROW_TABLE_WIDTH = 316;

/**
 * 是否使用窄屏（紧凑）表格。
 *
 * 判断依据必须是**容器宽度**而不是视口宽度：本看板在首页是放在 ~400px 宽的侧栏卡片里，
 * 1600px 视口下依然很窄。用 `max-width: 768px` 的视口断点会误判成宽屏，把 635px 的
 * 表格塞进 406px 容器，而横向滚动区是 `overflow-x: hidden` 的自定义拖拽容器、
 * 没有可见滚动条，导致右侧的涨跌幅/热度/关联概念列被永久裁掉、用户根本看不到。
 *
 * 容器尚未测量（首帧 width=0）时保守按窄屏渲染，避免先撑出宽表再跳变。
 */
function useIsNarrowContainer(containerWidth: number, wideWidth: number): boolean {
  return containerWidth === 0 || containerWidth < wideWidth;
}

const TAB_OPTIONS = [
  { label: <span><FireOutlined /> 热股榜</span>, value: "stock" as TabKey },
  { label: <span><RiseOutlined /> 概念榜</span>, value: "concept" as TabKey },
  { label: <span><AppstoreOutlined /> 行业榜</span>, value: "industry" as TabKey },
];

interface HorizontalScrollAreaProps {
  children: ReactNode;
  contentWidth: number;
  label: string;
}

function HorizontalScrollArea({ children, contentWidth, label }: HorizontalScrollAreaProps) {
  const contentStyle = useMemo(() => ({ minWidth: contentWidth }), [contentWidth]);
  const dragState = useRef({
    pointerId: -1,
    startX: 0,
    startScrollLeft: 0,
    moved: false,
    isDragging: false,
  });

  const stopDragging = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragState.current.pointerId !== event.pointerId) return;
    event.currentTarget.classList.remove("is-dragging");
    try {
      if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    } catch {
      // Ignore capture release errors
    }
    dragState.current.pointerId = -1;
    dragState.current.isDragging = false;
  };

  return (
    <div
      className="hot-rank-horizontal-scroll"
      role="region"
      aria-label={label}
      tabIndex={0}
      onPointerDown={(event) => {
        if (event.pointerType !== "mouse" || event.button !== 0) return;
        const target = event.target as HTMLElement | null;
        if (target?.closest("a, button, input, textarea, select, [role='button'], .ant-table-row-expand-icon")) {
          return;
        }
        dragState.current = {
          pointerId: event.pointerId,
          startX: event.clientX,
          startScrollLeft: event.currentTarget.scrollLeft,
          moved: false,
          isDragging: false,
        };
      }}
      onPointerMove={(event) => {
        const drag = dragState.current;
        if (drag.pointerId !== event.pointerId) return;
        const distance = event.clientX - drag.startX;
        if (!drag.isDragging) {
          if (Math.abs(distance) > 4) {
            drag.moved = true;
            drag.isDragging = true;
            try {
              event.currentTarget.setPointerCapture?.(event.pointerId);
            } catch {
              // Ignore pointer capture errors
            }
            event.currentTarget.classList.add("is-dragging");
          } else {
            return;
          }
        }
        event.currentTarget.scrollLeft = drag.startScrollLeft - distance;
        event.preventDefault();
      }}
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
      onClickCapture={(event) => {
        if (!dragState.current.moved) return;
        event.preventDefault();
        event.stopPropagation();
        dragState.current.moved = false;
      }}
    >
      <div
        className="hot-rank-horizontal-scroll__content"
        style={contentStyle}
      >
        {children}
      </div>
    </div>
  );
}

function StockTable({ enabled, scrollY }: { enabled: boolean; scrollY: number }) {
  const c = useColors();
  const t = useTokens();
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const isNarrow = useIsNarrowContainer(containerWidth, WIDE_STOCK_TABLE_WIDTH);
  const { data, isLoading, isFetching, error, refetch } = useThsHotRank(enabled);
  const hasData = (data?.length ?? 0) > 0;

  const columns: ColumnsType<ThsHotStock> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "股票",
          key: "stock",
          render: (_: unknown, record: ThsHotStock) => {
            const conceptTags = record.concept_tag ? record.concept_tag.split(";").filter(Boolean).slice(0, 2) : [];
            return (
              <div className="hot-rank-stock-row">
                <div className="hot-rank-badge-wrap">{rankBadge(record.rank, c, t)}</div>
                <div className="hot-rank-stock-col">
                  <StockExternalLink
                    code={record.code}
                    name={record.name}
                    className="hot-rank-stock-link"
                  >
                    <div className="hot-rank-name-row">
                      <span className="hot-rank-name-text">
                        {record.name}
                      </span>
                      <span className="hot-rank-code-text">
                        {record.code}
                      </span>
                    </div>
                  </StockExternalLink>
                  {(conceptTags.length > 0 || record.pop_tag) ? (
                    <div className="hot-rank-tags-row">
                      {conceptTags.map((tag) => (
                        <span
                          key={tag}
                          className="hot-rank-concept-badge"
                        >
                          {tag}
                        </span>
                      ))}
                      {record.pop_tag ? (
                        <span className="hot-rank-pop-badge">
                          {record.pop_tag}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          },
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 76,
          align: "right",
          render: (value: number | null) => (
            <span className="hot-rank-val--up-sm">
              {formatHotValue(value)}
            </span>
          ),
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number | null) => rankBadge(rank, c, t) },
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      render: (code: string, record: ThsHotStock) => (
        <StockExternalLink
          code={code}
          name={record.name}
          className="hot-rank-stock-link hot-rank-stock-code"
        >
          {code}
        </StockExternalLink>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      width: 100,
      ellipsis: true,
      render: (name: string, record: ThsHotStock) => (
        <StockExternalLink
          code={record.code}
          name={name}
          className="hot-rank-stock-link hot-rank-stock-name"
        >
          {name}
        </StockExternalLink>
      ),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span className="hot-rank-val--up">
          {formatHotValue(value)}
        </span>
      ),
    },
    {
      title: "关联概念",
      dataIndex: "concept_tag",
      width: 220,
      render: (tags: string) =>
        tags
          ? tags
              .split(";")
              .slice(0, 3)
              .map((tag, index) => (
                <Tag key={index} className="hot-rank-concept-tag">
                  {tag}
                </Tag>
              ))
          : "-",
    },
    ];
  }, [c, t, isNarrow]);

  const renderExpandedRow = useCallback((record: ThsHotStock) => (
    <ResponsiveMetricGrid
      items={[
        { key: "concept", label: "关联概念", value: record.concept_tag || "-" },
        { key: "pop", label: "人气标签", value: record.pop_tag || "-" },
      ]}
    />
  ), []);

  return (
    <div ref={containerRef}>
      <div className="hot-rank-refresh-row">
        <DataRefreshIndicator active={isFetching && !isLoading} />
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无热股排行数据"
        errorTitle="热股排行加载失败"
        minHeight={320}
      >
        <HorizontalScrollArea
          contentWidth={isNarrow ? NARROW_TABLE_WIDTH : WIDE_STOCK_TABLE_WIDTH}
          label="热股榜左右滑动区域"
        >
          <Table
            columns={columns}
            dataSource={data || []}
            rowKey={(record) => `${record.code}-${record.name}-${record.rank}`}
            size="small"
            pagination={false}
            virtual={!isNarrow}
            expandable={isNarrow ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 32,
            } : undefined}
            scroll={{ x: isNarrow ? undefined : WIDE_STOCK_TABLE_WIDTH, y: scrollY }}
            className="u-w-full"
          />
        </HorizontalScrollArea>
      </SectionDataState>
    </div>
  );
}

function PlateTable({
  type,
  enabled,
  scrollY,
}: {
  type: "concept" | "industry";
  enabled: boolean;
  scrollY?: number;
}) {
  const c = useColors();
  const t = useTokens();
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>();
  const isNarrow = useIsNarrowContainer(containerWidth, WIDE_PLATE_TABLE_WIDTH);
  const hook = type === "concept" ? useThsHotConcept : useThsHotIndustry;
  const { data, isLoading, isFetching, error, refetch } = hook(enabled);
  const hasData = (data?.length ?? 0) > 0;

  const columns: ColumnsType<ThsHotPlate> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: type === "concept" ? "概念" : "行业",
          key: "plate",
          render: (_: unknown, record: ThsHotPlate) => (
            <div className="hot-rank-stock-row">
              <div className="hot-rank-badge-wrap">{rankBadge(record.rank, c, t)}</div>
              <div className="hot-rank-stock-col">
                <span
                  className="hot-rank-plate-name"
                  title={record.name}
                >
                  {record.name}
                </span>
                {(record.hot_tag || record.tag) ? (
                  <div className="hot-rank-tags-row">
                    {record.hot_tag ? (
                      <span className="hot-rank-concept-badge">
                        {record.hot_tag}
                      </span>
                    ) : null}
                    {record.tag ? (
                      <span className="hot-rank-pop-badge">
                        {record.tag}
                      </span>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 76,
          align: "right",
          render: (value: number | null) => (
            <span className="hot-rank-val--up-sm">
              {formatHotValue(value)}
            </span>
          ),
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c, t) },
    {
      title: type === "concept" ? "概念名称" : "行业名称",
      dataIndex: "name",
      width: 160,
      ellipsis: true,
      render: (name: string) => <span className="hot-rank-name--medium">{name}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span className="hot-rank-val--up">
          {formatHotValue(value)}
        </span>
      ),
    },
    {
      title: "上榜标签",
      dataIndex: "hot_tag",
      width: 140,
      render: (tag: string) =>
        tag ? <Tag className="hot-rank-tag-primary">{tag}</Tag> : "-",
    },
    {
      title: "涨跌停",
      dataIndex: "tag",
      width: 110,
      render: (tag: string) =>
        tag ? <Tag className="hot-rank-tag-warning">{tag}</Tag> : "-",
    },
    ];
  }, [c, t, isNarrow, type]);

  const renderExpandedRow = useCallback((record: ThsHotPlate) => (
    <ResponsiveMetricGrid
      items={[
        { key: "hot-tag", label: "上榜标签", value: record.hot_tag || "-" },
        { key: "limit-tag", label: "涨跌停", value: record.tag || "-" },
      ]}
    />
  ), []);

  return (
    <div ref={containerRef}>
      <div className="hot-rank-refresh-row">
        <DataRefreshIndicator active={isFetching && !isLoading} />
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText={`暂无${type === "concept" ? "概念" : "行业"}热榜数据`}
        errorTitle={`${type === "concept" ? "概念" : "行业"}热榜加载失败`}
        minHeight={320}
      >
        <HorizontalScrollArea
          contentWidth={isNarrow ? NARROW_TABLE_WIDTH : WIDE_PLATE_TABLE_WIDTH}
          label={type === "concept" ? "概念榜左右滑动区域" : "行业榜左右滑动区域"}
        >
          <Table
            columns={columns}
            dataSource={data || []}
            rowKey={(record) => `${record.code}-${record.name}-${record.rank}`}
            size="small"
            pagination={false}
            scroll={{ x: isNarrow ? undefined : WIDE_PLATE_TABLE_WIDTH, y: scrollY }}
            expandable={isNarrow ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 32,
            } : undefined}
            className="u-w-full"
          />
        </HorizontalScrollArea>
      </SectionDataState>
    </div>
  );
}

interface HotRankContentProps {
  embedded?: boolean;
}

export function HotRankContent({ embedded = false }: HotRankContentProps) {
  const [tab, setTab] = useState<TabKey>("stock");
  const tableScrollY = embedded ? 440 : 600;

  return (
    <>
      <Card
        size="small"
        className={`hot-rank-card ${embedded ? "hot-rank-card--embedded-header" : "hot-rank-card--header"}`}
      >
        <div className="hot-rank-header-content">
          <Segmented
            size={embedded ? "small" : "middle"}
            options={TAB_OPTIONS}
            value={tab}
            onChange={(value) => setTab(value as TabKey)}
          />
          <span className="hot-rank-update-text">
            {embedded ? "每分钟自动更新" : "5分钟更新"}
          </span>
        </div>
      </Card>
      <Card
        size="small"
        className={`hot-rank-card ${embedded ? "hot-rank-card--embedded-body" : "hot-rank-card--body"}`}
      >
        {tab === "stock" && (
          <StockTable enabled={tab === "stock"} scrollY={tableScrollY} />
        )}
        {tab === "concept" && (
          <PlateTable
            type="concept"
            enabled={tab === "concept"}
            scrollY={tableScrollY}
          />
        )}
        {tab === "industry" && (
          <PlateTable
            type="industry"
            enabled={tab === "industry"}
            scrollY={tableScrollY}
          />
        )}
      </Card>
    </>
  );
}
