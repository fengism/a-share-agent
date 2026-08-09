import { DeleteOutlined, LoadingOutlined } from "@ant-design/icons";
import { Button, Card, Input, Popconfirm, Tooltip, Typography } from "antd";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainHistoryItem } from "../../types/stock";

const { Text } = Typography;

interface HistoryPanelProps {
  history: IndustryChainHistoryItem[];
  filter: string;
  activeName: string;
  archiveId: string;
  isLoading: boolean;
  error: unknown;
  hasMore: boolean;
  isLoadingMore: boolean;
  loadingArchiveKey: string;
  deletingArchiveKey: string;
  embedded?: boolean;
  onFilterChange: (value: string) => void;
  onLoadArchive: (item: IndustryChainHistoryItem) => void;
  onDelete: (item: IndustryChainHistoryItem) => Promise<void>;
  onLoadMore: () => void;
  onRetry: () => void;
}

export default function HistoryPanel({
  history,
  filter,
  activeName,
  archiveId,
  isLoading,
  error,
  hasMore,
  isLoadingMore,
  loadingArchiveKey,
  deletingArchiveKey,
  embedded = false,
  onFilterChange,
  onLoadArchive,
  onDelete,
  onLoadMore,
  onRetry,
}: HistoryPanelProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();

  const content = (
    <>
      <Input
        placeholder="按名称过滤"
        value={filter}
        onChange={(event) => onFilterChange(event.target.value)}
        allowClear
        style={{ marginBottom: 12 }}
      />
      <SectionDataState
        isLoading={isLoading && history.length === 0}
        error={history.length === 0 ? error : undefined}
        onRetry={onRetry}
        isEmpty={!isLoading && !error && history.length === 0}
        emptyText="暂无历史产业链"
        errorTitle="历史产业链加载失败"
        skeletonRows={5}
        minHeight={240}
      >
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {history.map((item) => {
            const itemKey = `${item.name}-${item.archive_id}`;
            const isActive = item.name === activeName && item.archive_id === archiveId;
            const isLoadingArchive = loadingArchiveKey === itemKey;
            const isDeletingArchive = deletingArchiveKey === itemKey;
            return (
              <li key={itemKey} style={{ display: "flex", alignItems: "center", gap: 4, padding: 0 }}>
                <Tooltip title={item.summary || item.title} placement="left">
                  <button
                    type="button"
                    onClick={() => onLoadArchive(item)}
                    disabled={Boolean(loadingArchiveKey || deletingArchiveKey)}
                    aria-busy={isLoadingArchive}
                    aria-pressed={isActive}
                    className={isActive ? undefined : "hover-mutedrow"}
                    style={{
                      flex: 1,
                      minWidth: 0,
                      padding: "12px 8px",
                      border: 0,
                      borderLeft: isActive ? `3px solid ${colors.primary}` : "3px solid transparent",
                      borderRadius: 4,
                      cursor: loadingArchiveKey ? "wait" : "pointer",
                      background: isActive ? colors.elevatedBg : "transparent",
                      opacity: loadingArchiveKey && !isLoadingArchive ? 0.6 : 1,
                      transition: "background 0.15s, border-color 0.15s",
                      textAlign: "left",
                      font: "inherit",
                    }}
                  >
                    <span style={{ display: "flex", minWidth: 0, justifyContent: "space-between", gap: 8 }}>
                      <span style={{ minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {item.title || `${item.name} 产业链`}
                      </span>
                      {isLoadingArchive ? (
                        <Text style={{ color: colors.primary, whiteSpace: "nowrap", fontSize: 12 }}>
                          <LoadingOutlined /> 加载中
                        </Text>
                      ) : null}
                    </span>
                    <Text type="secondary" style={{ display: "block", marginTop: 4 }}>
                      {(item.saved_at || item.archive_id).replace("T", " ").slice(0, 16)}
                    </Text>
                  </button>
                </Tooltip>
                {item.can_delete ? (
                  <Popconfirm
                    title="删除这条产业链记录？"
                    description="删除后无法恢复"
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => onDelete(item)}
                  >
                    <Button
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                      loading={isDeletingArchive}
                      disabled={Boolean(loadingArchiveKey)}
                      aria-label={`删除 ${item.title || item.name} 记录`}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                      }}
                    />
                  </Popconfirm>
                ) : null}
              </li>
            );
          })}
        </ul>
        {hasMore ? (
          <Button block loading={isLoadingMore} onClick={onLoadMore} style={{ marginTop: 12 }}>
            加载更多
          </Button>
        ) : null}
      </SectionDataState>
    </>
  );

  if (embedded) return content;

  return <Card title="历史产业链" style={cardStyle}>{content}</Card>;
}
