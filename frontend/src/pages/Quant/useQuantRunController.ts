import { useEffect, useMemo } from "react";
import { message } from "antd";
import { ApiError } from "../../api/client";
import {
  useCancelQuantBacktest,
  useDeleteQuantBacktest,
  useQuantBacktest,
  useQuantBacktests,
  useRetryQuantBacktest,
} from "../../api/queries";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";

type RunAction = "cancel" | "retry" | "delete";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

function successText(action: RunAction): string {
  if (action === "cancel") return "回测已取消";
  if (action === "retry") return "回测已重新入队";
  return "回测已删除";
}

export function useQuantRunController() {
  const runsQuery = useQuantBacktests();
  const [selectedRunId, setSelectedRunId] = useUrlSearchParam("run", "", { replace: true });
  const selectedQuery = useQuantBacktest(selectedRunId || undefined);
  const cancelRun = useCancelQuantBacktest();
  const retryRun = useRetryQuantBacktest();
  const deleteRun = useDeleteQuantBacktest();
  const runs = useMemo(
    () => runsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [runsQuery.data?.pages],
  );
  const hasMoreRuns = runsQuery.hasNextPage;

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

  return {
    deletingRunId: deleteRun.isPending ? deleteRun.variables : undefined,
    hasMoreRuns,
    isHistoryFetching: runsQuery.isFetching,
    isHistoryLoading: runsQuery.isLoading,
    isLoadingMoreRuns: runsQuery.isFetchingNextPage,
    isRunActionPending: cancelRun.isPending || retryRun.isPending,
    retryingRunId: retryRun.isPending ? retryRun.variables : undefined,
    runHistoryError: runsQuery.error,
    runs,
    selectedRun,
    selectedRunId,
    cancelRun: (runId: string) => handleAction("cancel", runId),
    deleteRun: (runId: string) => handleAction("delete", runId),
    loadMoreRuns: () => runsQuery.fetchNextPage(),
    refreshRuns: () => runsQuery.refetch(),
    retryRun: (runId: string) => handleAction("retry", runId),
    selectRun: setSelectedRunId,
  };
}

export type QuantRunController = ReturnType<typeof useQuantRunController>;
