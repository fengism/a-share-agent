import { useMemo, useState } from "react";
import { BellOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { AutoComplete, Button, Card, Input, InputNumber, Modal, Select, Space, Tag, Tooltip, Typography, message } from "antd";
import {
  useAddWatchlistAlert,
  useAddWatchlistItem,
  useDeleteWatchlistAlert,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useStyles } from "../../styles/ui";
import type { WatchlistAlertCondition, WatchlistItem } from "../../types/watchlist";
import ChangeValue from "../../components/ChangeValue";
import PreloadLink from "../../components/PreloadLink";

const { Text } = Typography;
const CONDITION_LABELS: Record<WatchlistAlertCondition, string> = {
  price_above: "价格高于",
  price_below: "价格低于",
  change_pct_above: "涨跌幅高于",
  change_pct_below: "涨跌幅低于",
};

const SOURCE_LABELS: Record<string, string> = {
  tencent: "腾讯行情",
  sina: "新浪行情",
  sina_direct: "新浪行情",
  eastmoney: "东方财富",
  eastmoney_direct: "东方财富",
};

function sourceLabel(value: string | undefined): string {
  if (!value) return "等待行情";
  return SOURCE_LABELS[value] || value;
}

function formatQuotedTime(value: string | undefined): string {
  if (!value) return "尚未更新";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "尚未更新";
  return parsed.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function WatchlistPanel() {
  const { cardStyle } = useStyles();
  const watchlist = useWatchlist();
  const addItem = useAddWatchlistItem();
  const deleteItem = useDeleteWatchlistItem();
  const addAlert = useAddWatchlistAlert();
  const deleteAlert = useDeleteWatchlistAlert();
  const search = useStockSearchController();
  const [alertStock, setAlertStock] = useState<WatchlistItem | null>(null);
  const [condition, setCondition] = useState<WatchlistAlertCondition>("price_above");
  const [threshold, setThreshold] = useState<number | null>(null);

  const options = useMemo(() => search.currentResults.slice(0, 8).map((stock) => ({
    value: stock.code,
    label: (
      <span style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
        <span>{stock.name}</span>
        <Text type="secondary">{stock.code}</Text>
      </span>
    ),
  })), [search.currentResults]);

  const handleAdd = async (stockCode: string) => {
    try {
      await addItem.mutateAsync({ stock_code: stockCode, note: "" });
      search.clear();
      message.success("已加入自选");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "添加自选失败");
    }
  };

  const handleCreateAlert = async () => {
    if (!alertStock || threshold == null) return;
    try {
      await addAlert.mutateAsync({ stockCode: alertStock.stock_code, request: { condition, threshold } });
      setAlertStock(null);
      setThreshold(null);
      message.success("提醒规则已添加");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "添加提醒失败");
    }
  };

  return (
    <Card
      className="dashboard-watchlist-card"
      style={cardStyle}
    >
      <header className="dashboard-watchlist__header">
        <div>
          <span className="dashboard-watchlist__eyebrow">WATCHLIST</span>
          <h2>我的自选</h2>
        </div>
        <span className="dashboard-watchlist__count">{watchlist.data?.items.length ?? 0} 只</span>
      </header>
      <div className="dashboard-watchlist__meta">
        <span>{sourceLabel(watchlist.data?.source)} · {formatQuotedTime(watchlist.data?.quoted_at)}</span>
      </div>
      <div className="dashboard-watchlist__search">
        <span>添加自选</span>
        <AutoComplete
          aria-label="搜索并添加自选股"
          value={search.inputValue}
          options={options}
          onChange={search.setInputValue}
          onSelect={handleAdd}
          filterOption={false}
          style={{ width: "100%" }}
        >
          <Input prefix={<PlusOutlined />} placeholder="搜索股票并加入自选" allowClear />
        </AutoComplete>
      </div>

      <SectionDataState
        isLoading={watchlist.isLoading}
        error={!watchlist.data ? watchlist.error : undefined}
        onRetry={() => watchlist.refetch()}
        isEmpty={(watchlist.data?.items.length ?? 0) === 0}
        emptyText="还没有自选股"
        errorTitle="自选股加载失败"
        skeletonRows={2}
        minHeight={120}
      >
        <div className="dashboard-watchlist__scroll">
          <ul className="dashboard-watchlist">
            {(watchlist.data?.items ?? []).map((item) => (
              <li className={`dashboard-watchlist__item${(item.change_pct ?? 0) > 0 ? " is-up" : (item.change_pct ?? 0) < 0 ? " is-down" : " is-flat"}`} key={item.id}>
                <div className="dashboard-watchlist__row">
                  <PreloadLink className="dashboard-watchlist__identity" to={`/analysis/${encodeURIComponent(item.stock_code)}`}>
                    <strong>{item.stock_name}</strong>
                    <Text type="secondary">{item.stock_code}</Text>
                  </PreloadLink>
                  <div className="dashboard-watchlist__quote-cluster">
                    <strong>{item.current_price?.toFixed(2) ?? "-"}</strong>
                    <ChangeValue value={item.change_pct} />
                  </div>
                </div>
                {item.alerts.length > 0 ? (
                  <div className="dashboard-watchlist__alerts">
                      {item.alerts.map((alert) => (
                        <Tag
                          key={alert.id}
                          color={alert.triggered ? "red" : "default"}
                          closable
                          onClose={(event) => {
                            event.preventDefault();
                            deleteAlert.mutateAsync(alert.id);
                          }}
                        >
                          {alert.triggered ? "已触发 · " : ""}{CONDITION_LABELS[alert.condition]} {alert.threshold}
                        </Tag>
                      ))}
                  </div>
                ) : null}
                <div className="dashboard-watchlist__actions dashboard-watchlist__actions--overlay">
                  <Tooltip title="设置提醒">
                    <Button size="small" type="text" aria-label={`设置${item.stock_name}提醒`} icon={<BellOutlined />} onClick={() => setAlertStock(item)} />
                  </Tooltip>
                  <Tooltip title="移除自选">
                    <Button size="small" type="text" danger aria-label={`移除${item.stock_name}`} icon={<DeleteOutlined />} onClick={() => deleteItem.mutateAsync(item.stock_code)} />
                  </Tooltip>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </SectionDataState>

      <Modal
        title={alertStock ? `设置 ${alertStock.stock_name} 提醒` : "设置提醒"}
        open={Boolean(alertStock)}
        onCancel={() => setAlertStock(null)}
        onOk={handleCreateAlert}
        okButtonProps={{ disabled: threshold == null, loading: addAlert.isPending }}
        okText="添加提醒"
      >
        <Space orientation="vertical" style={{ width: "100%" }}>
          <Select
            value={condition}
            onChange={setCondition}
            options={Object.entries(CONDITION_LABELS).map(([value, label]) => ({ value, label }))}
            style={{ width: "100%" }}
          />
          <InputNumber
            value={threshold}
            onChange={setThreshold}
            placeholder={condition.startsWith("change_pct") ? "阈值（%）" : "价格阈值"}
            style={{ width: "100%" }}
          />
        </Space>
      </Modal>
    </Card>
  );
}
