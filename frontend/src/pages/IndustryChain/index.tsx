import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Input, Tabs, message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useNavigate, useParams } from "react-router-dom";
import {
  useConfig,
  useDeleteIndustryChainArchive,
  useIndustryChainArchive,
  useInfiniteIndustryChainHistory,
} from "../../api/queries";
import { streamIndustryChain, type IndustryChainProgress } from "../../api/sse";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowProgressPanel from "../../components/workflows/WorkflowProgressPanel";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainHistoryItem, IndustryChainResearchScope, IndustryChainResult } from "../../types/stock";
import HistoryPanel from "./HistoryPanel";
import IndustryAtlas from "./IndustryAtlas";
import IndustryReport, { type IndustryPushResult } from "./IndustryReport";
import {
  applyIndustryAgentEvent,
  createIndustryAgentProcessState,
} from "./agentProcess";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "./industryWorkflow";
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
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState(-1);
  const [stageMessage, setStageMessage] = useState("");
  const [result, setResult] = useState<IndustryChainResult | null>(null);
  const [archiveId, setArchiveId] = useState("");
  const [error, setError] = useState("");
  const [historyFilter, setHistoryFilter] = useState(activeName);
  const [pushResult, setPushResult] = useState<IndustryPushResult | null>(null);
  const [agentProcess, setAgentProcess] = useState(createIndustryAgentProcessState);
  const [researchScope, setResearchScope] = useState<IndustryChainResearchScope>(DEFAULT_INDUSTRY_SCOPE);
  const cancelStreamRef = useRef<(() => void) | null>(null);

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
  const archiveMutation = useIndustryChainArchive();
  const deleteArchiveMutation = useDeleteIndustryChainArchive();

  useEffect(() => () => {
    cancelStreamRef.current?.();
    cancelStreamRef.current = null;
  }, []);

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
    cancelStreamRef.current?.();
    setIsAnalyzing(true);
    setCurrentStage(-1);
    setStageMessage("");
    setResult(null);
    setArchiveId("");
    setError("");
    setPushResult(null);
    setAgentProcess(createIndustryAgentProcessState());

    const { promise, cancel } = streamIndustryChain(name, (event: IndustryChainProgress) => {
      if (event.type === "stage_started" && event.stage) {
        const nextStage = industryStageIndex(event.stage);
        if (nextStage >= 0) setCurrentStage(nextStage);
        setStageMessage(event.message || "");
      } else if (event.type === "stage_completed" && event.stage) {
        setStageMessage(event.message || "完成");
      } else if (event.type === "agent_event" && event.agent_event) {
        setAgentProcess((current) => applyIndustryAgentEvent(current, event.agent_event!));
      } else if (event.type === "complete" && event.result) {
        refetchHistory();
      }
    }, industryScopeRequest(researchScope));
    cancelStreamRef.current = cancel;

    promise
      .then((data) => {
        setResult(data);
        setArchiveId(data.archive_id || "");
        setCurrentStage(INDUSTRY_CHAIN_STAGES.length);
        setStageMessage(data.archive_status === "failed" ? "分析完成，但存档失败" : "分析完成");
        setIsAnalyzing(false);
        refetchHistory();
        void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(name) });
      })
      .catch((streamError: Error) => {
        setError(streamError.message || "分析失败");
        setIsAnalyzing(false);
        message.error(streamError.message || "分析失败");
      })
      .finally(() => {
        cancelStreamRef.current = null;
      });
  }, [navigate, queryClient, refetchHistory, researchScope]);

  const handleLoadArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      const data = await archiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      setActiveTab("analysis");
      setResult(data);
      setArchiveId(item.archive_id);
      setCurrentStage(-1);
      setStageMessage("");
      setError("");
      setPushResult(null);
      setAgentProcess(createIndustryAgentProcessState());
      navigate(`/industry-chain/${encodeURIComponent(item.name)}`, { replace: true });
    } catch (loadError) {
      message.error(loadError instanceof Error ? loadError.message : "加载历史存档失败");
    }
  }, [archiveMutation, navigate]);

  const handleDeleteArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      await deleteArchiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      if (item.name === activeName && item.archive_id === archiveId) {
        setResult(null);
        setArchiveId("");
        setPushResult(null);
        setError("");
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainHistoryRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(item.name) }),
      ]);
      message.success("产业链记录已删除");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除产业链记录失败");
    }
  }, [activeName, archiveId, deleteArchiveMutation, queryClient]);

  const handlePush = useCallback(async (target: "feishu" | "notion", feishuReceiver = "") => {
    if (!result || !activeName) {
      message.warning("请先完成一次产业链分析");
      return;
    }
    if (!archiveId) {
      message.warning("当前报告未关联存档，无法推送");
      return;
    }

    const response = await push({
      target,
      type: "industry_chain",
      industry_name: activeName,
      archive_id: archiveId,
      feishu_receiver: target === "feishu" ? feishuReceiver.trim() : "",
    });
    if (response) {
      setPushResult({ url: response.url, message: response.message, target });
    }
  }, [activeName, archiveId, push, result]);

  const handleAnalyzeFromAtlas = useCallback((name: string) => {
    setActiveTab("analysis");
    handleAnalyze(name);
  }, [handleAnalyze]);

  const historyPanelProps = {
    history,
    filter: historyFilter,
    activeName,
    archiveId,
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
      />

      <WorkflowWorkspace
        historyTitle="历史产业链"
        historyButtonLabel="历史产业链"
        historyVersion={archiveId}
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
                      enterButton={<span><SearchOutlined /> 开始分析</span>}
                      size="large"
                      loading={isAnalyzing}
                      value={inputValue}
                      onChange={(event) => setInputValue(event.target.value)}
                      onSearch={handleAnalyze}
                      disabled={isAnalyzing}
                    />
                    <IndustryResearchScopeControls
                      value={researchScope}
                      disabled={isAnalyzing}
                      onChange={setResearchScope}
                    />
                  </div>

                  {(isAnalyzing || currentStage >= 0 || error || agentProcess.plan || agentProcess.toolCalls.length > 0) && (
                    <WorkflowProgressPanel
                      current={currentStage}
                      status={error ? "error" : isAnalyzing ? "running" : "success"}
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
                        isRunning={isAnalyzing && currentStage === 0}
                      />
                    </WorkflowProgressPanel>
                  )}

                  {result && (
                    <IndustryReport
                      result={result}
                      activeName={activeName}
                      archiveId={archiveId}
                      defaultReceiver={config?.feishu_default_receiver}
                      isPushing={isPushing}
                      pushResult={pushResult}
                      onPush={handlePush}
                    />
                  )}
                  {!result && !isAnalyzing && !error && (
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
