import { useMemo, useState } from "react";
import { ClockCircleOutlined, DeleteOutlined, FilterOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Input, Popconfirm, Select, Tag, Typography } from "antd";
import dayjs from "dayjs";
import type { QuantBacktestRun } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useStyles, semanticTagStyle } from "../../styles/ui";
import { QUANT_RUN_STATUS_META, quantStrategyLabel, quantUniverseLabel } from "./quantRun";

const { Text } = Typography;
type StatusFilter = "all" | QuantBacktestRun["status"];

interface BacktestHistoryProps {
  runs: QuantBacktestRun[];
  selectedRunId?: string;
  isLoading: boolean;
  isFetching: boolean;
  error?: unknown;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  retryingRunId?: string;
  deletingRunId?: string;
  onRefresh: () => void;
  onLoadMore?: () => void;
  onSelect: (runId: string) => void;
  onRetryRun: (runId: string) => void;
  onDeleteRun: (runId: string) => void;
}

export default function BacktestHistory({
  runs,
  selectedRunId,
  isLoading,
  isFetching,
  error,
  hasMore,
  isLoadingMore,
  retryingRunId,
  deletingRunId,
  onRefresh,
  onLoadMore,
  onSelect,
  onRetryRun,
  onDeleteRun,
}: BacktestHistoryProps) {
  const { cardStyle } = useStyles();
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [strategyFilter, setStrategyFilter] = useState("all");
  const [isFiltersOpen, setIsFiltersOpen] = useState(() => runs.length > 8);
  const strategyOptions = useMemo(() => {
    const labels = new Map<string, string>();
    runs.forEach((run) => {
      const strategy = run.request.strategy ?? { type: "ma_cross" };
      labels.set(strategy.type, quantStrategyLabel(strategy));
    });
    return Array.from(labels, ([value, label]) => ({ value, label }))
      .sort((left, right) => left.label.localeCompare(right.label, "zh-CN"));
  }, [runs]);
  const filteredRuns = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    return runs.filter((run) => {
      const strategy = run.request.strategy ?? { type: "ma_cross" };
      const strategyLabel = quantStrategyLabel(strategy).toLowerCase();
      if (statusFilter !== "all" && run.status !== statusFilter) return false;
      if (strategyFilter !== "all" && strategy.type !== strategyFilter) return false;
      if (!normalizedKeyword) return true;
      const codes = (run.request.universe.codes ?? []).join(" ").toLowerCase();
      return run.name.toLowerCase().includes(normalizedKeyword)
        || strategy.type.toLowerCase().includes(normalizedKeyword)
        || strategyLabel.includes(normalizedKeyword)
        || codes.includes(normalizedKeyword);
    });
  }, [keyword, runs, statusFilter, strategyFilter]);
  const activeFilterCount = Number(Boolean(keyword.trim()))
    + Number(statusFilter !== "all")
    + Number(strategyFilter !== "all");

  return (
    <Card
      title={<span className="quant-history-card-title"><ClockCircleOutlined />历史回测</span>}
      size="small"
      style={cardStyle}
      className="quant-history-card"
    >
      <div className="quant-history-toolbar">
        {isFiltersOpen ? <div className="quant-history-filters">
          <Input
            aria-label="搜索历史回测"
            placeholder="搜索名称或股票代码"
            value={keyword}
            allowClear
            onChange={(event) => setKeyword(event.target.value)}
          />
          <Select<StatusFilter>
            aria-label="历史状态"
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: "all", label: "全部状态" },
              ...Object.entries(QUANT_RUN_STATUS_META).map(([value, meta]) => ({ value: value as StatusFilter, label: meta.label })),
            ]}
          />
          <Select
            aria-label="历史策略"
            value={strategyFilter}
            onChange={setStrategyFilter}
            options={[{ value: "all", label: "全部策略" }, ...strategyOptions]}
          />
        </div> : null}
        <div className="quant-history-toolbar-actions">
          <Button
            size="small"
            type={activeFilterCount > 0 ? "primary" : "default"}
            icon={<FilterOutlined />}
            aria-label="筛选历史回测"
            aria-expanded={isFiltersOpen}
            onClick={() => setIsFiltersOpen((current) => !current)}
          >
            筛选{activeFilterCount > 0 ? ` ${activeFilterCount}` : ""}
          </Button>
          <Text type="secondary">{filteredRuns.length}/{runs.length} 条</Text>
          <Button size="small" icon={<ReloadOutlined />} loading={isFetching} onClick={onRefresh}>刷新</Button>
        </div>
      </div>
      <SectionDataState
        isLoading={isLoading && runs.length === 0}
        error={runs.length === 0 ? error : undefined}
        onRetry={onRefresh}
        isEmpty={!isLoading && filteredRuns.length === 0 && (runs.length > 0 || !error)}
        emptyText={runs.length > 0 ? "没有匹配的回测记录" : "暂无回测记录，先创建一次策略回测"}
        errorTitle="历史回测加载失败"
        minHeight={180}
      >
        <ul className="quant-history-list">
          {filteredRuns.map((run) => {
            const status = QUANT_RUN_STATUS_META[run.status];
            const isSelected = selectedRunId === run.id;
            const codes = quantUniverseLabel(run);
            const strategy = quantStrategyLabel(run.request.strategy ?? { type: "ma_cross" });
            return (
              <li key={run.id} className={isSelected ? "quant-history-item is-selected" : "quant-history-item"}>
                <button
                  type="button"
                  className="quant-history-summary"
                  aria-current={isSelected ? "true" : undefined}
                  aria-label={`查看回测 ${run.name}`}
                  onClick={() => onSelect(run.id)}
                >
                  <span className="quant-history-title-row">
                    <span className="quant-history-name">{run.name}</span>
                    <Tag style={semanticTagStyle(status.color)}>{status.label}</Tag>
                  </span>
                  <Text type="secondary" className="quant-history-meta">
                    {strategy} · {codes} · {run.request.start_date} 至 {run.request.end_date} · {dayjs.unix(run.created_at).format("MM-DD HH:mm")}
                  </Text>
                </button>
                <div className="quant-history-actions">
                  <Button type="link" size="small" onClick={() => onSelect(run.id)}>查看</Button>
                  {run.status === "failed" ? (
                    <Button
                      type="link"
                      size="small"
                      loading={retryingRunId === run.id}
                      onClick={() => onRetryRun(run.id)}
                    >
                      重试
                    </Button>
                  ) : null}
                  {!(["pending", "running"] as QuantBacktestRun["status"][]).includes(run.status) ? (
                    <Popconfirm
                      title="确认删除该回测记录？"
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => onDeleteRun(run.id)}
                    >
                      <Button
                        type="link"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={deletingRunId === run.id}
                        aria-label={`删除回测 ${run.name}`}
                      >
                        删除
                      </Button>
                    </Popconfirm>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
        {hasMore ? (
          <div className="quant-history-load-more">
            <Button
              size="small"
              loading={isLoadingMore}
              onClick={onLoadMore}
            >
              加载更多
            </Button>
          </div>
        ) : null}
      </SectionDataState>
    </Card>
  );
}
