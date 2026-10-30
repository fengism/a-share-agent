import {
  AppstoreOutlined,
  BarsOutlined,
  DownloadOutlined,
  LineChartOutlined,
  MinusCircleOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Button, Empty, Input, Segmented, Space, Table, Tag, Tooltip } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo, useState } from "react";
import ChangeValue from "../../components/ChangeValue";
import PreloadLink from "../../components/PreloadLink";
import type { PortfolioStockSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import {
  formatInteger,
  formatMoney,
  formatPrice,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import { marketDateStamp } from "../../utils/marketTime";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioStockTableProps {
  stocks: PortfolioStockSummary[];
  renderers: PortfolioTableRenderers;
  onSell: (stock: PortfolioStockSummary) => void;
  onViewKline?: (stockCode: string) => void;
  bare?: boolean;
}

function PortfolioStockTable({
  stocks,
  renderers,
  onSell,
  onViewKline,
  bare = false,
}: PortfolioStockTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"table" | "card">("table");
  const { colors, isMobile, renderProfit, renderStock } = renderers;

  const displayStocks = useMemo(() => {
    if (!searchQuery.trim()) return stocks;
    const q = searchQuery.trim().toLowerCase();
    return stocks.filter(
      (s) =>
        s.stock_code.toLowerCase().includes(q) ||
        s.stock_name.toLowerCase().includes(q),
    );
  }, [searchQuery, stocks]);

  const handleExportCsv = () => {
    const headers = [
      "股票代码",
      "股票名称",
      "币种",
      "汇率(CNY)",
      "剩余批次",
      "持仓股数",
      "可卖股数",
      "冻结股数",
      "平均成本",
      "当前价",
      "当日涨跌(%)",
      "当日盈亏",
      "持仓成本",
      "最新市值",
      "仓位占比(%)",
      "浮动盈亏额",
      "浮动盈亏率(%)",
      "已实现盈亏",
      "综合盈亏",
      "可加仓金额",
      "可加仓股数",
    ];
    const lines = stocks.map((s) => [
      `\t${s.stock_code}`,
      `"${s.stock_name.replace(/"/g, '""')}"`,
      s.currency,
      s.fx_rate_to_cny,
      s.position_count,
      s.total_shares,
      s.sellable_shares ?? "",
      s.frozen_shares ?? "",
      s.average_cost != null ? s.average_cost.toFixed(2) : "",
      s.current_price != null ? s.current_price.toFixed(2) : "",
      s.change_pct != null ? s.change_pct.toFixed(2) : "",
      s.daily_profit_amount != null ? s.daily_profit_amount.toFixed(2) : "",
      s.cost_value != null ? s.cost_value.toFixed(2) : "",
      s.market_value != null ? s.market_value.toFixed(2) : "",
      s.allocation_pct != null ? s.allocation_pct.toFixed(2) : "",
      s.profit_amount != null ? s.profit_amount.toFixed(2) : "",
      s.profit_pct != null ? s.profit_pct.toFixed(2) : "",
      s.realized_profit_amount != null ? s.realized_profit_amount.toFixed(2) : "",
      s.total_profit_amount != null ? s.total_profit_amount.toFixed(2) : "",
      s.max_additional_value != null ? s.max_additional_value.toFixed(2) : "",
      s.max_additional_shares ?? "",
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `投资组合当前持仓_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };

  const columns = useMemo<TableColumnsType<PortfolioStockSummary>>(() => [
    {
      title: "股票",
      key: "stock",
      width: 150,
      fixed: isMobile ? undefined : "left",
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "剩余批次",
      dataIndex: "position_count",
      width: 95,
      align: "right",
      className: "financial-num",
    },
    {
      title: "持仓股数",
      dataIndex: "total_shares",
      width: 110,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.total_shares - b.total_shares,
      render: formatInteger,
    },
    {
      title: <Tooltip title="A 股 T+1：当日买入的股份次一交易日才可卖出；港股按 T+0 展示">可卖股数</Tooltip>,
      dataIndex: "sellable_shares",
      width: 105,
      align: "right",
      className: "financial-num",
      render: (value: number | null | undefined) => value == null ? "-" : formatInteger(value),
    },
    {
      title: <Tooltip title="当日买入、暂不可卖出的股份">冻结股数</Tooltip>,
      dataIndex: "frozen_shares",
      width: 100,
      align: "right",
      className: "financial-num",
      render: (value: number | null | undefined) => value == null ? "-" : formatInteger(value),
    },
    {
      title: <Tooltip title="按标的原币显示；港股为港币">平均成本</Tooltip>,
      dataIndex: "average_cost",
      width: 110,
      align: "right",
      className: "financial-num",
      render: (value: number | null | undefined, record) => formatPrice(value, record.currency),
    },
    {
      title: "当前价",
      dataIndex: "current_price",
      width: 105,
      align: "right",
      className: "financial-num",
      render: (value: number | null | undefined, record) => formatPrice(value, record.currency),
    },
    {
      title: "当日涨跌",
      dataIndex: "change_pct",
      width: 110,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "当日盈亏(CNY)",
      key: "daily_profit",
      width: 125,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.daily_profit_amount ?? 0) - (b.daily_profit_amount ?? 0),
      render: (_, record) => renderProfit(record.daily_profit_amount, record.daily_profit_pct),
    },
    {
      title: "持仓成本(CNY)",
      dataIndex: "cost_value",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.cost_value ?? 0) - (b.cost_value ?? 0),
      render: (value) => formatMoney(value),
    },
    {
      title: "最新市值(CNY)",
      dataIndex: "market_value",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.market_value ?? 0) - (b.market_value ?? 0),
      render: (value) => formatMoney(value),
    },
    {
      title: <Tooltip title="按已成功定价股票的最新市值计算">仓位占比</Tooltip>,
      dataIndex: "allocation_pct",
      width: 110,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.allocation_pct ?? 0) - (b.allocation_pct ?? 0),
      render: (value: number | null) =>
        value == null ? "-" : (
          <div>
            <div>{value.toFixed(2)}%</div>
            <div
              style={{
                height: 3,
                borderRadius: 2,
                background: colors.nestedBg,
                overflow: "hidden",
                marginTop: 2,
                display: "flex",
                justifyContent: "flex-end",
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, Math.max(0, value))}%`,
                  height: "100%",
                  background: "var(--c-primary)",
                  borderRadius: 2,
                }}
              />
            </div>
          </div>
        ),
    },
    {
      title: (
        <Tooltip title="受单股、行业、总仓位上限和可用现金约束，按最小交易单位向下取整">
          可加仓(CNY)
        </Tooltip>
      ),
      key: "max_additional",
      width: 130,
      align: "right",
      className: "financial-num",
      render: (_, record) =>
        record.max_additional_value == null ? "-" : (
          <Tooltip
            title={`约 ${formatInteger(record.max_additional_shares ?? 0)} 股 · 每手 ${record.lot_size ?? "-"} 股`}
          >
            <div>{formatMoney(record.max_additional_value)}</div>
            <div style={{ fontSize: 11, color: colors.textMuted }}>
              {formatInteger(record.max_additional_shares ?? 0)} 股
            </div>
          </Tooltip>
        ),
    },
    {
      title: "浮动盈亏(CNY)",
      key: "profit",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.profit_amount ?? 0) - (b.profit_amount ?? 0),
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
    {
      title: <Tooltip title="单股浮动盈亏占全部股票绝对浮动盈亏的比例">盈亏贡献</Tooltip>,
      dataIndex: "profit_contribution_pct",
      width: 110,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.profit_contribution_pct ?? 0) - (b.profit_contribution_pct ?? 0),
      render: (value: number | null) => (
        value == null
          ? "-"
          : <span style={{ color: changeColor(value, colors) }}>{value.toFixed(2)}%</span>
      ),
    },
    {
      title: "已实现盈亏",
      dataIndex: "realized_profit_amount",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.realized_profit_amount - b.realized_profit_amount,
      render: (value: number) => renderProfit(value),
    },
    {
      title: "综合盈亏",
      dataIndex: "total_profit_amount",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.total_profit_amount ?? 0) - (b.total_profit_amount ?? 0),
      render: (value: number | null) => renderProfit(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 128,
      fixed: isMobile ? undefined : "right",
      render: (_, record) => {
        const sellable = record.sellable_shares ?? record.total_shares;
        const frozen = record.frozen_shares ?? Math.max(record.total_shares - sellable, 0);
        return (
          <Space size={4}>
            <PreloadLink
              to={`/analysis?code=${record.stock_code}`}
              aria-label={`查看${record.stock_name}研报`}
            >
              <Button
                type="link"
                size="small"
                style={{ padding: "0 2px" }}
              >
                研报
              </Button>
            </PreloadLink>
            {onViewKline ? (
              <Button
                type="link"
                size="small"
                icon={<LineChartOutlined />}
                onClick={() => onViewKline(record.stock_code)}
                style={{ padding: "0 2px" }}
                title="跳转查看买卖点复盘"
              >
                复盘
              </Button>
            ) : null}
            <Tooltip title={sellable > 0 ? undefined : `当日买入的 ${formatInteger(frozen)} 股已冻结，下一交易日可卖`}>
              <span>
                <Button
                  type="link"
                  size="small"
                  icon={<MinusCircleOutlined />}
                  aria-label={`卖出 ${record.stock_name}`}
                  disabled={sellable <= 0}
                  onClick={() => onSell(record)}
                  style={{ padding: "0 2px" }}
                >
                  卖出
                </Button>
              </span>
            </Tooltip>
          </Space>
        );
      },
    },
  ], [colors, isMobile, onSell, onViewKline, renderProfit, renderStock]);

  return (
    <PortfolioTableCard
      title="当前持仓汇总"
      stacked={!bare}
      bare={bare}
      extra={
        stocks.length > 0 ? (
          <Space size={8} wrap>
            <Segmented
              size="small"
              value={viewMode}
              onChange={(val) => setViewMode(val as "table" | "card")}
              options={[
                { label: "表格", value: "table", icon: <BarsOutlined /> },
                { label: "卡片", value: "card", icon: <AppstoreOutlined /> },
              ]}
            />
            <Input
              size="small"
              placeholder="搜索股票"
              prefix={<SearchOutlined style={{ color: colors.textMuted }} />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              style={{ width: 130 }}
            />
            <Button size="small" icon={<DownloadOutlined />} onClick={handleExportCsv}>
              导出 CSV
            </Button>
          </Space>
        ) : null
      }
    >
      {viewMode === "card" ? (
        <div className="portfolio-stock-cards-container">
          {displayStocks.length === 0 ? (
            <Empty description="未找到匹配持仓" />
          ) : (
            displayStocks.map((stock) => {
              const sellable = stock.sellable_shares ?? stock.total_shares;
              const frozen = stock.frozen_shares ?? Math.max(stock.total_shares - sellable, 0);
              return (
                <div
                  key={stock.stock_code}
                  style={{
                    background: colors.nestedBg,
                    borderRadius: 8,
                    border: `1px solid ${colors.border ?? "rgba(128,128,128,0.15)"}`,
                    padding: "var(--c-pad-card, 16px 18px)",
                    marginBottom: 10,
                  }}
                  className="portfolio-stock-card-item"
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                    <div>
                      {renderStock(stock.stock_name, stock.stock_code)}
                      {stock.currency && stock.currency !== "CNY" ? (
                        <Tag style={{ marginLeft: 4 }}>{stock.currency}</Tag>
                      ) : null}
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <ChangeValue value={stock.change_pct} style={{ fontSize: 14, fontWeight: 700 }} />
                      <div style={{ fontSize: 11, color: colors.textMuted }}>当日涨跌</div>
                    </div>
                  </div>

                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(3, 1fr)",
                    gap: 8,
                    padding: "8px 0",
                    borderTop: `1px dashed ${colors.border ?? "rgba(128,128,128,0.15)"}`,
                    borderBottom: `1px dashed ${colors.border ?? "rgba(128,128,128,0.15)"}`,
                    marginBottom: 8,
                  }}>
                    <div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>持仓市值(CNY)</div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{formatMoney(stock.market_value)}</div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>成本 {formatMoney(stock.cost_value)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>现价 / 成本</div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{formatPrice(stock.current_price, stock.currency)}</div>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>成本 {formatPrice(stock.average_cost, stock.currency)}</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 11, color: colors.textMuted }}>浮动盈亏(CNY)</div>
                      {renderProfit(stock.profit_amount, stock.profit_pct)}
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, fontSize: 12 }}>
                    <span style={{ color: colors.textMuted }}>
                      持仓 <strong>{formatInteger(stock.total_shares)}</strong> 股
                      {stock.sellable_shares != null ? ` · 可卖 ${formatInteger(stock.sellable_shares)}` : ""}
                      {frozen > 0 ? ` · 冻结 ${formatInteger(frozen)}` : ""}
                    </span>
                    {stock.allocation_pct != null ? (
                      <div>
                        <span style={{ fontWeight: 600, fontSize: 12 }}>
                          占比 {stock.allocation_pct.toFixed(2)}%
                        </span>
                      </div>
                    ) : null}
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                    <PreloadLink
                      to={`/analysis?code=${stock.stock_code}`}
                      aria-label={`查看${stock.stock_name}研报`}
                    >
                      <Button size="small">研报</Button>
                    </PreloadLink>
                    {onViewKline ? (
                      <Button
                        size="small"
                        icon={<LineChartOutlined />}
                        onClick={() => onViewKline(stock.stock_code)}
                      >
                        复盘
                      </Button>
                    ) : null}
                    <Button
                      size="small"
                      type="primary"
                      ghost
                      danger
                      icon={<MinusCircleOutlined />}
                      aria-label={`卖出 ${stock.stock_name}`}
                      disabled={sellable <= 0}
                      onClick={() => onSell(stock)}
                    >
                      卖出
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      ) : (
        <Table<PortfolioStockSummary>
          rowKey="stock_code"
          columns={columns}
          dataSource={displayStocks}
          pagination={PORTFOLIO_TABLE_PAGINATION}
          size="middle"
          scroll={{ x: 1_888 }}
          locale={{ emptyText: <Empty description="当前没有持仓" /> }}
        />
      )}
    </PortfolioTableCard>
  );
}

export default memo(PortfolioStockTable);
