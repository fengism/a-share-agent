import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApartmentOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { Button, Tabs, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useNavigate, useParams } from "react-router-dom";
import {
  useConfig,
  useDeleteIndustryChainArchive,
  useIndustryChainArchive,
  useIndustryChainLatest,
  useIndustryChainAtlasCatalog,
  useInfiniteIndustryChainHistory,
} from "../../api/queries";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainHistoryItem, IndustryChainResearchScope } from "../../types/stock";
import HistoryPanel from "./HistoryPanel";
import IndustryAtlas from "./IndustryAtlas";
import IndustryReport, { type IndustryPushResult } from "./IndustryReport";
import IndustryWorkflowProgress from "./IndustryWorkflowProgress";
import { useIndustryChainWorkflowController } from "../../hooks/useIndustryChainWorkflowController";
import IndustrySearchPanel from "./IndustrySearchPanel";
import { useIndustryArchiveAutoLoader } from "./useIndustryArchiveAutoLoader";
import {
  DEFAULT_INDUSTRY_SCOPE,
  industryScopeRequest,
  validateIndustryScope,
} from "./industryScope";

// 图谱目录较重（卡片网格 + 管理操作）；分析期间 SSE 事件频繁更新，
// memo + 稳定的 onAnalyze 引用可避免图谱子树随进度事件重渲染
const MemoizedIndustryAtlas = memo(IndustryAtlas);

const FALLBACK_HOT_INDUSTRIES = [
  { name: "人形机器人", icon: "🤖" },
  { name: "低空经济", icon: "✈️" },
  { name: "CPO光模块", icon: "🔌" },
  { name: "固态电池", icon: "🔋" },
  { name: "半导体设备", icon: "💾" },
  { name: "算力租赁", icon: "⚡" },
  { name: "创新药", icon: "💊" },
  { name: "商业航天", icon: "🛰️" },
  { name: "智能座舱", icon: "🚗" },
];

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
  const { data: atlasCatalog } = useIndustryChainAtlasCatalog();
  const hotIndustries = useMemo(() => {
    const iconByName = new Map(FALLBACK_HOT_INDUSTRIES.map((item) => [item.name, item.icon]));
    const names = [
      ...history.map((item) => item.name),
      ...(atlasCatalog?.chains ?? []).map((item) => item.name),
      ...FALLBACK_HOT_INDUSTRIES.map((item) => item.name),
    ];
    const uniqueNames = [...new Set(names.map((name) => name.trim()).filter(Boolean))];
    return uniqueNames.slice(0, 9).map((name) => ({
      name,
      icon: iconByName.get(name) ?? "◈",
    }));
  }, [atlasCatalog?.chains, history]);
  const archiveMutation = useIndustryChainArchive();
  const deleteArchiveMutation = useDeleteIndustryChainArchive();

  const {
    name: runningName,
    status: workflowStatus,
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
    onSuccess: useCallback(() => message.success("产业链分析完成"), []),
    onError: useCallback((runError: Error) => message.error(runError.message), []),
    onCancelled: useCallback((cancelResult: "cancelled" | "detached" | "completed") => message.info(
      cancelResult === "cancelled"
        ? "已停止产业研究"
        : cancelResult === "completed"
          ? "任务已完成，正在刷新产业研究"
          : "已停止等待，后台共享任务仍在运行",
    ), []),
  });
  const { data: latestArchive, isLoading: isLatestLoading } = useIndustryChainLatest(activeName);
  const latestArchiveId = latestArchive?.archive_id ?? "";
  const displayedResult = result && runningName === activeName ? result : null;
  const displayedArchiveId = displayedResult ? archiveId : "";
  const isActiveRouteRun = isAnalyzing && runningName === activeName;
  const isCurrentRouteStopped = runningName === activeName
    && (workflowStatus === "cancelled" || workflowStatus === "detached");

  // URL 直达 /industry-chain/:name 时自动加载最新存档；同一存档只请求一次，
  // 避免 mutation 状态更新触发页面重渲染后形成重复请求循环。
  useIndustryArchiveAutoLoader({
    activeName,
    latestArchiveId,
    isLatestLoading,
    isAnalyzing,
    hasDisplayedResult: Boolean(displayedResult),
    hasCurrentRouteError: Boolean(error && runningName === activeName),
    hasCurrentRouteStopped: isCurrentRouteStopped,
    loadArchive: archiveMutation.mutateAsync,
    loadResult,
  });

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

    const started = runAnalysis(name, industryScopeRequest(researchScope), {
      force: Boolean(displayedResult && runningName === name),
    });
    if (!started) {
      // 已有任务在运行时 runAnalysis 会拒绝启动；此前静默返回导致用户点按钮无任何反馈
      message.warning(`「${runningName}」的产业链分析正在进行中，请等待完成后再发起新分析`);
      return;
    }
    navigate(`/industry-chain/${encodeURIComponent(name)}`, { replace: true });
    setPushResult(null);
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
              children: <MemoizedIndustryAtlas onAnalyze={handleAnalyzeFromAtlas} />,
            },
            {
              key: "analysis",
              label: "AI 分析",
              children: (
                <>
                  <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 20 }}>
                    <IndustrySearchPanel
                      value={inputValue}
                      activeName={activeName}
                      hasDisplayedResult={Boolean(displayedResult)}
                      disabled={isActiveRouteRun}
                      loading={isActiveRouteRun}
                      hotIndustries={hotIndustries}
                      scope={researchScope}
                      onValueChange={setInputValue}
                      onSearch={handleAnalyze}
                      onScopeChange={setResearchScope}
                    />
                  </div>

                  {(isActiveRouteRun || isCurrentRouteStopped || (runningName === activeName && (currentStage >= 0 || error || agentProcess.plan || agentProcess.toolCalls.length > 0 || agentProcess.rounds.length > 0))) && (
                    <IndustryWorkflowProgress
                      currentStage={currentStage}
                      status={workflowStatus}
                      message={error || stageMessage}
                      agentProcess={agentProcess}
                    />
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
                  {!displayedResult && !isActiveRouteRun && !isCurrentRouteStopped && !error && !isLatestLoading && (
                    <div style={{ ...cardStyle, padding: 60, textAlign: "center" }}>
                      <ApartmentOutlined style={{ fontSize: 48, color: colors.textMuted, marginBottom: 16 }} />
                      <div style={{ color: colors.textMuted, fontSize: "var(--c-font-base)" }}>输入产业关键词，开始 AI 产业链分析</div>
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
