import { useEffect, useMemo } from "react";
import { Typography, message } from "antd";
import { ApiError } from "../../api/client";
import {
  useCancelQuantBacktest,
  useDeleteQuantBacktest,
  useQuantBacktest,
  useQuantBacktests,
  useRetryQuantBacktest,
  type QuantBacktestRun,
} from "../../api/queries";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import BacktestForm from "./BacktestForm";
import BacktestHistory from "./BacktestHistory";
import BacktestResult from "./BacktestResult";
import BacktestRunSummary from "./BacktestRunSummary";
import BacktestRunStatus from "./BacktestRunStatus";
import "./quant.css";

const { Paragraph, Title } = Typography;
type RunAction = "cancel" | "retry" | "delete";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

function successText(action: RunAction): string {
  if (action === "cancel") return "回测已取消";
  if (action === "retry") return "回测已重新入队";
  return "回测已删除";
}

export default function QuantPage() {
  const { pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();
  const runsQuery = useQuantBacktests();
  const [selectedRunId, setSelectedRunId] = useUrlSearchParam("run", "", { replace: true });
  const selectedQuery = useQuantBacktest(selectedRunId || undefined);
  const cancelRun = useCancelQuantBacktest();
  const retryRun = useRetryQuantBacktest();
  const deleteRun = useDeleteQuantBacktest();
  const runs = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data?.items]);

  useEffect(() => {
    if (!selectedRunId && runs[0]) setSelectedRunId(runs[0].id);
  }, [runs, selectedRunId, setSelectedRunId]);

  useEffect(() => {
    if (!(selectedQuery.error instanceof ApiError) || selectedQuery.error.status !== 404) return;
    if (runs.some((run) => run.id === selectedRunId)) return;
    setSelectedRunId(runs[0]?.id ?? "");
  }, [runs, selectedQuery.error, selectedRunId, setSelectedRunId]);

  const selectedRun = selectedQuery.data ?? runs.find((run) => run.id === selectedRunId);

  const handleAction = async (action: RunAction, runId: string) => {
    const mutation = action === "cancel" ? cancelRun : action === "retry" ? retryRun : deleteRun;
    try {
      await mutation.mutateAsync(runId);
      message.success(successText(action));
      if (action === "delete" && selectedRunId === runId) {
        setSelectedRunId(runs.find((run) => run.id !== runId)?.id ?? "");
      }
    } catch (error) {
      message.error(`操作失败：${errorText(error)}`);
    }
  };

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>量化研究</Title>
        <Paragraph style={pageDescriptionStyle}>
          使用严格复权的历史行情验证交易策略，结果包含完整成本、基准收益与风险指标。
        </Paragraph>
      </div>

      <BacktestForm onCreated={(run: QuantBacktestRun) => setSelectedRunId(run.id)} />

      {selectedRun ? <BacktestRunSummary run={selectedRun} /> : null}

      <BacktestRunStatus
        run={selectedRun}
        isActionPending={cancelRun.isPending || retryRun.isPending}
        onCancel={(runId) => void handleAction("cancel", runId)}
        onRetry={(runId) => void handleAction("retry", runId)}
      />

      {selectedRun?.status === "succeeded" && selectedRun.result ? (
        <BacktestResult result={selectedRun.result} />
      ) : null}

      <BacktestHistory
        runs={runs}
        selectedRunId={selectedRunId}
        isLoading={runsQuery.isLoading}
        isFetching={runsQuery.isFetching}
        error={runsQuery.error}
        retryingRunId={retryRun.isPending ? retryRun.variables : undefined}
        deletingRunId={deleteRun.isPending ? deleteRun.variables : undefined}
        onRefresh={() => void runsQuery.refetch()}
        onSelect={setSelectedRunId}
        onRetryRun={(runId) => void handleAction("retry", runId)}
        onDeleteRun={(runId) => void handleAction("delete", runId)}
      />
    </div>
  );
}
