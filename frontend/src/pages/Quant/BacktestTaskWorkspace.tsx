import { ExperimentOutlined, LineChartOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import BacktestHistory from "./BacktestHistory";
import BacktestRunSummary from "./BacktestRunSummary";
import BacktestRunStatus from "./BacktestRunStatus";
import type { QuantRunController } from "./useQuantRunController";

export default function BacktestTaskWorkspace({
  controller,
  onOpenSetup,
  onOpenResult,
}: {
  controller: QuantRunController;
  onOpenSetup: () => void;
  onOpenResult: (runId: string) => void;
}) {
  const { runs, selectedRun, selectedRunId, selectRun } = controller;
  const handleSelect = (runId: string) => {
    const run = runs.find((item) => item.id === runId);
    if (run?.status === "succeeded" && run.result) {
      onOpenResult(runId);
      return;
    }
    selectRun(runId);
  };

  return (
    <section className="quant-task-workspace" aria-label="回测任务工作台">
      <div className="quant-side-header">
        <div>
          <span>任务工作台</span>
          <strong>运行状态与历史记录</strong>
        </div>
        <div className="quant-side-actions">
          <Tag>{runs.length} 个任务</Tag>
          <Button size="small" icon={<PlusOutlined />} onClick={onOpenSetup}>新建回测</Button>
          {selectedRun?.status === "succeeded" && selectedRun.result ? (
            <Button
              type="primary"
              size="small"
              icon={<LineChartOutlined />}
              onClick={() => onOpenResult(selectedRun.id)}
            >
              查看当前结果
            </Button>
          ) : null}
        </div>
      </div>
      <BacktestRunStatus
        run={selectedRun}
        isActionPending={controller.isRunActionPending}
        onCancel={(runId) => void controller.cancelRun(runId)}
        onRetry={(runId) => void controller.retryRun(runId)}
      />
      <div className="quant-task-columns">
        {selectedRun ? <BacktestRunSummary run={selectedRun} /> : (
          <div className="quant-side-empty">
            <ExperimentOutlined />
            <strong>尚未选择回测任务</strong>
            <span>提交新回测或从历史记录中选择任务。</span>
          </div>
        )}
        <BacktestHistory
          runs={runs}
          selectedRunId={selectedRunId}
          isLoading={controller.isHistoryLoading}
          isFetching={controller.isHistoryFetching}
          error={controller.runHistoryError}
          hasMore={controller.hasMoreRuns}
          isLoadingMore={controller.isLoadingMoreRuns}
          retryingRunId={controller.retryingRunId}
          deletingRunId={controller.deletingRunId}
          onRefresh={() => void controller.refreshRuns()}
          onLoadMore={() => void controller.loadMoreRuns()}
          onSelect={handleSelect}
          onRetryRun={(runId) => void controller.retryRun(runId)}
          onDeleteRun={(runId) => void controller.deleteRun(runId)}
        />
      </div>
    </section>
  );
}
