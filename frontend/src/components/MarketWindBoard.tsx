import { useEffect, useMemo } from "react";
import { Button, Card, Space, Table, Tag } from "antd";
import {
  ArrowRightOutlined,
  FireOutlined,
  ReloadOutlined,
  RiseOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useMarketWind, useMarketWindStocks } from "../api/queries";
import ChangeValue from "./ChangeValue";
import RefreshBadge from "./RefreshBadge";
import SectionDataState from "./SectionDataState";
import StockExternalLink from "./StockExternalLink";
import { useUrlSearchParam } from "../hooks/useUrlSearchParam";
import { semanticTagStyle } from "../styles/ui";
import type { MarketWindStock } from "../types/stock";
import "./market-wind.css";

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatPrice(value: number | null) {
  return value == null ? "-" : value.toFixed(2);
}

function strongestChange(stocks: MarketWindStock[]) {
  return stocks.reduce<number | null>((current, stock) => {
    if (stock.change_pct == null) return current;
    return current == null ? stock.change_pct : Math.max(current, stock.change_pct);
  }, null);
}

export default function MarketWindBoard({ embedded = false }: { embedded?: boolean }) {
  const windQuery = useMarketWind();
  const plates = useMemo(() => windQuery.data?.items ?? [], [windQuery.data?.items]);
  const [plateParam, setPlateParam] = useUrlSearchParam("plate", "", { replace: true });
  const selectedPlateCode = plates.some((plate) => plate.plate_code === plateParam)
    ? plateParam
    : plates[0]?.plate_code ?? "";

  useEffect(() => {
    if (plateParam && plates.length > 0 && !plates.some((plate) => plate.plate_code === plateParam)) {
      setPlateParam("");
    }
  }, [plateParam, plates, setPlateParam]);

  const stocksQuery = useMarketWindStocks(selectedPlateCode);
  const selectedPlate = plates.find((plate) => plate.plate_code === selectedPlateCode);
  const stocks = stocksQuery.data?.items ?? [];
  const maxChange = strongestChange(stocks);
  const maxBoardCount = Math.max(0, ...stocks.map((stock) => stock.limit_up_days));
  const stockMetricValue = stocksQuery.isLoading && stocks.length === 0 ? "-" : stocks.length;

  const columns: ColumnsType<MarketWindStock> = useMemo(() => [
    {
      title: "排名",
      key: "rank",
      width: 56,
      align: "center",
      render: (_value: unknown, _stock: MarketWindStock, index: number) => (
        <span className={`wind-stock-rank ${index < 3 ? "wind-stock-rank--top" : ""}`}>{index + 1}</span>
      ),
    },
    {
      title: "龙头股",
      key: "stock",
      width: 140,
      render: (_value: unknown, stock: MarketWindStock) => (
        <StockExternalLink code={stock.code} name={stock.name} className="wind-stock-link">
          <strong>{stock.name || "-"}</strong>
          <small>{stock.code}</small>
        </StockExternalLink>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      width: 95,
      align: "right",
      render: formatPrice,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 95,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={700} />,
    },
    {
      title: "连板高度",
      dataIndex: "limit_up_days",
      width: 95,
      align: "center",
      render: (value: number) => value > 0
        ? <Tag style={semanticTagStyle(value > 1 ? "up" : "warning")}>{value > 1 ? `${value}连板` : "首板"}</Tag>
        : <span className="wind-table-muted">-</span>,
    },
  ], []);

  const hasPlates = plates.length > 0;

  return (
    <SectionDataState
      isLoading={windQuery.isLoading && !hasPlates}
      error={hasPlates ? undefined : windQuery.error}
      onRetry={() => windQuery.refetch()}
      isEmpty={!windQuery.isLoading && !windQuery.error && !hasPlates}
      emptyText="暂无今日风口数据"
      errorTitle="今日风口加载失败"
      minHeight={480}
      skeletonRows={10}
    >
      <div className="market-wind">
        {embedded ? (
          <div className="wind-section-heading" style={{ marginBottom: 16 }}>
            <span className="wind-section-heading__icon"><ThunderboltOutlined /></span>
            <span>
              <strong>今日风口</strong>
              <small>当前聚焦：{selectedPlate?.plate_name || "等待选择"}{selectedPlate?.catalyst ? ` · ${selectedPlate.catalyst}` : ""}</small>
            </span>
            <Space size={[8, 8]} wrap style={{ marginLeft: "auto" }}>
              <Tag style={semanticTagStyle("primary")}>{plates.length} 个风口</Tag>
              <Tag style={semanticTagStyle("up")}>{stockMetricValue} 只龙头</Tag>
              <RefreshBadge />
            </Space>
          </div>
        ) : (
          <>
            <div className="wind-toolbar">
              <Space size={12} wrap>
                <span>更新时间：{formatFetchedAt(windQuery.data?.fetched_at)}</span>
                <RefreshBadge />
              </Space>
              <Button
                icon={<ReloadOutlined />}
                loading={windQuery.isFetching || stocksQuery.isFetching}
                onClick={() => {
                  void windQuery.refetch();
                  if (selectedPlateCode) void stocksQuery.refetch();
                }}
              >
                刷新
              </Button>
            </div>

            <section className="wind-hero">
              <div className="wind-hero__summary">
                <div className="wind-kicker"><ThunderboltOutlined /> 今日主线速览</div>
                <h2>今日风口</h2>
                <p>聚焦盘中正在发酵的题材催化，切换风口即可查看对应龙头股表现。</p>
                <Space size={[8, 8]} wrap>
                  <Tag style={semanticTagStyle("primary")}>{plates.length} 个风口</Tag>
                  <Tag style={semanticTagStyle("up")}>{stockMetricValue} 只龙头</Tag>
                </Space>
              </div>
              <div className="wind-hero__focus">
                <span className="wind-hero__focus-icon"><FireOutlined /></span>
                <span className="wind-hero__focus-content">
                  <small>当前聚焦</small>
                  <strong>{selectedPlate?.plate_name || "等待选择"}</strong>
                  <span>{selectedPlate?.catalyst || "选择风口后查看催化逻辑"}</span>
                </span>
              </div>
            </section>
          </>
        )}

        <section className="wind-plate-section" aria-labelledby="wind-plate-title">
          <div className="wind-section-heading">
            <span className="wind-section-heading__icon"><ThunderboltOutlined /></span>
            <span>
              <strong id="wind-plate-title">风口题材</strong>
              <small>选择题材查看催化逻辑与对应龙头表现</small>
            </span>
            <Tag>{plates.length} 个</Tag>
          </div>

          <div className="wind-plate-grid">
            {plates.map((plate, index) => {
              const selected = plate.plate_code === selectedPlateCode;
              return (
                <button
                  type="button"
                  key={plate.plate_code}
                  aria-label={`选择风口 ${plate.plate_name}`}
                  aria-pressed={selected}
                  className={`wind-plate-card ${selected ? "wind-plate-card--selected" : ""}`}
                  onClick={() => setPlateParam(plate.plate_code)}
                >
                  <span className="wind-plate-card__topline">
                    <span className="wind-plate-card__index">{String(index + 1).padStart(2, "0")}</span>
                    {selected ? <Tag style={semanticTagStyle("primary")}>正在查看</Tag> : null}
                  </span>
                  <strong>{plate.plate_name}</strong>
                  <span className="wind-plate-card__catalyst">{plate.catalyst || "暂无催化信息"}</span>
                  <span className="wind-plate-card__action">
                    {selected ? "龙头股已展开" : "查看龙头股"} <ArrowRightOutlined />
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <Card
          className="wind-leaders-card"
          title={(
            <div className="wind-leaders-heading">
              <span className="wind-section-heading__icon"><RiseOutlined /></span>
              <span>
                <strong>{selectedPlate?.plate_name || "风口"}龙头股</strong>
              </span>
            </div>
          )}
        >
          <div className="wind-leader-summary">
            <span><small>龙头数量</small><strong>{stockMetricValue}</strong></span>
            <span><small>最高涨幅</small><strong className="is-up">{maxChange == null ? "-" : `${maxChange.toFixed(2)}%`}</strong></span>
            <span><small>最高连板</small><strong className="is-up">{maxBoardCount > 0 ? `${maxBoardCount} 板` : "-"}</strong></span>
          </div>

          <SectionDataState
            isLoading={Boolean(selectedPlateCode) && stocksQuery.isLoading && stocks.length === 0}
            error={stocks.length > 0 ? undefined : stocksQuery.error}
            onRetry={() => stocksQuery.refetch()}
            isEmpty={Boolean(selectedPlateCode) && !stocksQuery.isLoading && !stocksQuery.error && stocks.length === 0}
            emptyText="暂无龙头股数据"
            errorTitle="龙头股加载失败"
            minHeight={240}
            skeletonRows={5}
          >
            <Table<MarketWindStock>
              className="wind-leaders-table"
              rowKey="code"
              columns={columns}
              dataSource={stocks}
              pagination={false}
              scroll={{ x: 480 }}
              size="middle"
              tableLayout="fixed"
            />
          </SectionDataState>
        </Card>
      </div>
    </SectionDataState>
  );
}
