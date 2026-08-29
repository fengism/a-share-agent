import { useCallback, useEffect, useState } from "react";
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  SearchOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { Button, Input, Tabs, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useNavigate, useParams } from "react-router-dom";
import {
  useConfig,
  useDeleteIndustryChainArchive,
  useIndustryChainArchive,
  useInfiniteIndustryChainHistory,
} from "../../api/queries";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowProgressPanel from "../../components/workflows/WorkflowProgressPanel";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainHistoryItem, IndustryChainResearchScope } from "../../types/stock";
import HistoryPanel from "./HistoryPanel";
import IndustryAtlas from "./IndustryAtlas";
import IndustryReport, { type IndustryPushResult } from "./IndustryReport";
import { INDUSTRY_CHAIN_STAGES } from "./industryWorkflow";
import { useIndustryChainWorkflowController } from "../../hooks/useIndustryChainWorkflowController";
import IndustryResearchScopeControls from "./IndustryResearchScopeControls";
import {
  DEFAULT_INDUSTRY_SCOPE,
  industryScopeRequest,
  validateIndustryScope,
} from "./industryScope";

const { Search } = Input;

export default function IndustryChain() {
  const colors = useColors();
  const { pageContainerStyle, cardStyle } = useStyles();
  const { name: urlName } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeName = urlName ? decodeURIComponent(urlName) : "";

  const [inputValue, setInputValue] = useState(activeName);
  const [activeTab, setActiveTab] = useState<"atlas" | "analysis">(activeName ? "analysis" : "atlas");
  const [historyFilter, setHistoryFilter] = useState(activeName);
  const [pushResult, setPushResult] = useState<IndustryPushResult | null>(null);
  const [researchScope, setResearchScope] = useState<IndustryChainResearchScope>(DEFAULT_INDUSTRY_SCOPE);

  const { data: config } = useConfig();
  const { push, isPushing } = useWorkflowPush();
  const debouncedHistoryFilter = useDebouncedValue(historyFilter, 300);
  const {
    data: historyPages,
    isLoading: isHistoryLoading,
    error: historyError,
    hasNextPage: hasMoreHistory,
    fetchNextPage: fetchMoreHistory,
    isFetchingNextPage: isLoadingMoreHistory,
    refetch: refetchHistory,
  } = useInfiniteIndustryChainHistory(debouncedHistoryFilter);
  const history = historyPages?.pages.flat() ?? [];
  const latestArchiveId = history.find((item) => item.name === activeName)?.archive_id ?? "";
  const archiveMutation = useIndustryChainArchive();
  const deleteArchiveMutation = useDeleteIndustryChainArchive();

  const {
    name: runningName,
    isAnalyzing,
    isCancelling,
    currentStage,
    stageMessage,
    result,
    archiveId,
    error,
    agentProcess,
    runAnalysis,
    cancelAnalysis,
    loadResult,
    clearResult,
  } = useIndustryChainWorkflowController({
    onSuccess: () => message.success("产业链分析完成"),
    onError: (runError) => message.error(runError.message),
    onCancelled: (cancelResult) => message.info(
      cancelResult === "cancelled"
        ? "已停止产业研究"
        : cancelResult === "completed"
          ? "任务已完成，正在刷新产业研究"
          : "已停止等待，后台共享任务仍在运行",
    ),
  });
  const displayedResult = result && runningName === activeName ? result : null;
  const displayedArchiveId = displayedResult ? archiveId : latestArchiveId;
  const isActiveRouteRun = isAnalyzing && runningName === activeName;

  useEffect(() => {
    setInputValue(activeName);
    setHistoryFilter(activeName);
  }, [activeName]);

  const handleAnalyze = useCallback((value: string) => {
    const name = value.trim();
    if (!name) return;
    const scopeError = validateIndustryScope(researchScope);
    if (scopeError) {
      message.warning(scopeError);
      return;
    }

    navigate(`/industry-chain/${encodeURIComponent(name)}`, { replace: true });
    setPushResult(null);
    runAnalysis(name, industryScopeRequest(researchScope), {
      force: Boolean(displayedResult && runningName === name),
    });
  }, [displayedResult, navigate, researchScope, runAnalysis, runningName]);

  const handleLoadArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      const data = await archiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      setActiveTab("analysis");
      loadResult(item.name, data, item.archive_id);
      setPushResult(null);
      navigate(`/industry-chain/${encodeURIComponent(item.name)}`, { replace: true });
    } catch (loadError) {
      message.error(loadError instanceof Error ? loadError.message : "加载历史存档失败");
    }
  }, [archiveMutation, loadResult, navigate]);

  const handleDeleteArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      await deleteArchiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      if (item.name === activeName && item.archive_id === archiveId) {
        clearResult();
        setPushResult(null);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainHistoryRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(item.name) }),
      ]);
      message.success("产业链记录已删除");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除产业链记录失败");
    }
  }, [activeName, archiveId, clearResult, deleteArchiveMutation, queryClient]);

  const handlePush = useCallback(async (target: "feishu" | "notion", feishuReceiver = "") => {
    if (!displayedResult || !activeName) {
      message.warning("请先完成一次产业链分析");
      return;
    }
    if (!displayedArchiveId) {
      message.warning("当前报告未关联存档，无法推送");
      return;
    }

    const response = await push({
      target,
      type: "industry_chain",
      industry_name: activeName,
      archive_id: displayedArchiveId,
      feishu_receiver: target === "feishu" ? feishuReceiver.trim() : "",
    });
    if (response) {
      setPushResult({ url: response.url, message: response.message, target });
    }
  }, [activeName, displayedArchiveId, displayedResult, push]);

  const handleAnalyzeFromAtlas = useCallback((name: string) => {
    setActiveTab("analysis");
    handleAnalyze(name);
  }, [handleAnalyze]);

  const historyPanelProps = {
    history,
    filter: historyFilter,
    activeName,
    archiveId: displayedArchiveId,
    isLoading: isHistoryLoading,
    error: historyError,
    hasMore: Boolean(hasMoreHistory),
    isLoadingMore: isLoadingMoreHistory,
    loadingArchiveKey: archiveMutation.isPending
      ? `${archiveMutation.variables?.name}-${archiveMutation.variables?.archiveId}`
      : "",
    deletingArchiveKey: deleteArchiveMutation.isPending
      ? `${deleteArchiveMutation.variables?.name}-${deleteArchiveMutation.variables?.archiveId}`
      : "",
    onFilterChange: setHistoryFilter,
    onLoadArchive: handleLoadArchive,
    onDelete: handleDeleteArchive,
    onLoadMore: () => fetchMoreHistory(),
    onRetry: () => refetchHistory(),
  };

  return (
    <div style={pageContainerStyle}>
      <WorkflowPageHeader
        title="产业链分析"
        description="浏览产业链知识库图谱（上/中/下游与代表公司），或输入关键词让 AI 生成深度产业链分析报告"
        icon={<ApartmentOutlined />}
        actions={isActiveRouteRun ? (
          <Button
            danger
            icon={<StopOutlined />}
            loading={isCancelling}
            disabled={isCancelling}
            onClick={() => void cancelAnalysis()}
          >
            {isCancelling ? "正在停止" : "停止产业研究"}
          </Button>
        ) : null}
      />

      <WorkflowWorkspace
        historyTitle="历史产业链"
        historyButtonLabel="历史产业链"
        historyVersion={`${activeName}:${displayedArchiveId}`}
        history={<HistoryPanel {...historyPanelProps} embedded />}
      >
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key === "atlas" ? "atlas" : "analysis")}
          style={{ marginBottom: 16 }}
          items={[
            {
              key: "atlas",
              label: "知识库图谱",
              children: <IndustryAtlas onAnalyze={handleAnalyzeFromAtlas} />,
            },
            {
              key: "analysis",
              label: "AI 分析",
              children: (
                <>
                  <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 20 }}>
                    <Search
                      placeholder="输入产业链名称，如：锂电池、AI芯片、光伏..."
                      enterButton={(
                        <span>
                          <SearchOutlined /> {displayedResult && inputValue.trim() === activeName ? "重新分析" : "开始分析"}
                        </span>
                      )}
                      size="large"
                      loading={isActiveRouteRun}
                      value={inputValue}
                      onChange={(event) => setInputValue(event.target.value)}
                      onSearch={handleAnalyze}
                      disabled={isActiveRouteRun}
                    />
                    <IndustryResearchScopeControls
                      value={researchScope}
                      disabled={isActiveRouteRun}
                      onChange={setResearchScope}
                    />
                  </div>

                  {(isActiveRouteRun || (runningName === activeName && (currentStage >= 0 || error || agentProcess.plan || agentProcess.toolCalls.length > 0))) && (
                    <WorkflowProgressPanel
                      current={currentStage}
                      status={error ? "error" : isActiveRouteRun ? "running" : "success"}
                      message={error || stageMessage}
                      items={INDUSTRY_CHAIN_STAGES.map((stage, index) => ({
                        title: stage.title,
                        icon: currentStage === index
                          ? <LoadingOutlined />
                          : currentStage > index
                            ? <CheckCircleOutlined />
                            : undefined,
                      }))}
                    >
                      <AgentProcessPanel
                        plan={agentProcess.plan}
                        status={agentProcess.status}
                        toolCalls={agentProcess.toolCalls}
                        isRunning={isActiveRouteRun && currentStage === 0}
                      />
                    </WorkflowProgressPanel>
                  )}

                  {displayedResult && (
                    <IndustryReport
                      result={displayedResult}
                      activeName={activeName}
                      archiveId={displayedArchiveId}
                      defaultReceiver={config?.feishu_default_receiver}
                      isPushing={isPushing}
                      pushResult={pushResult}
                      onPush={handlePush}
                    />
                  )}
                  {!displayedResult && !isActiveRouteRun && !error && (
                    <div style={{ ...cardStyle, padding: 60, textAlign: "center" }}>
                      <ApartmentOutlined style={{ fontSize: 48, color: colors.textMuted, marginBottom: 16 }} />
                      <div style={{ color: colors.textMuted, fontSize: 14 }}>输入产业关键词，开始 AI 产业链分析</div>
                    </div>
                  )}
                </>
              ),
            },
          ]}
        />
      </WorkflowWorkspace>
    </div>
  );
}
