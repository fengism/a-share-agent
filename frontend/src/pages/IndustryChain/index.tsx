import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  LoadingOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { Button, Col, Drawer, Input, message, Row, Spin, Steps, Typography } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useNavigate, useParams } from "react-router-dom";
import {
  useConfig,
  useDeleteIndustryChainArchive,
  useIndustryChainArchive,
  useInfiniteIndustryChainHistory,
  useIndustryChainLatest,
  usePush,
} from "../../api/queries";
import { streamIndustryChain, type IndustryChainProgress } from "../../api/sse";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainHistoryItem, IndustryChainResult } from "../../types/stock";
import HistoryPanel from "./HistoryPanel";
import IndustryReport, { type IndustryPushResult } from "./IndustryReport";
import {
  applyIndustryAgentEvent,
  createIndustryAgentProcessState,
} from "./agentProcess";

const { Paragraph, Title } = Typography;
const { Search } = Input;

const STAGE_MAP: Record<string, number> = {
  "Agent 动态调研": 0,
  "证据覆盖校验": 1,
  "AI 生成分析报告": 2,
};

export default function IndustryChain() {
  const colors = useColors();
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle, cardStyle } = useStyles();
  const { name: urlName } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeName = urlName ? decodeURIComponent(urlName) : "";
  const isCompactLayout = useMediaQuery("(max-width: 991px)");

  const [inputValue, setInputValue] = useState(activeName);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState(-1);
  const [stageMessage, setStageMessage] = useState("");
  const [result, setResult] = useState<IndustryChainResult | null>(null);
  const [archiveId, setArchiveId] = useState("");
  const [error, setError] = useState("");
  const [historyFilter, setHistoryFilter] = useState(activeName);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [pushResult, setPushResult] = useState<IndustryPushResult | null>(null);
  const [agentProcess, setAgentProcess] = useState(createIndustryAgentProcessState);
  const cancelStreamRef = useRef<(() => void) | null>(null);

  const { data: config } = useConfig();
  const pushMutation = usePush();
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
  const { data: latest, refetch: refetchLatest } = useIndustryChainLatest(activeName);

  useEffect(() => () => {
    cancelStreamRef.current?.();
    cancelStreamRef.current = null;
  }, []);

  useEffect(() => {
    setInputValue(activeName);
    setHistoryFilter(activeName);
  }, [activeName]);

  useEffect(() => {
    if (latest?.archive_id && !archiveId && result) {
      setArchiveId(latest.archive_id);
    }
  }, [archiveId, latest, result]);

  const handleAnalyze = useCallback((value: string) => {
    const name = value.trim();
    if (!name) return;

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
        setCurrentStage(STAGE_MAP[event.stage] ?? 0);
        setStageMessage(event.message || "");
      } else if (event.type === "stage_completed" && event.stage) {
        setStageMessage(event.message || "完成");
      } else if (event.type === "agent_event" && event.agent_event) {
        setAgentProcess((current) => applyIndustryAgentEvent(current, event.agent_event!));
      } else if (event.type === "complete" && event.result) {
        refetchHistory();
      }
    });
    cancelStreamRef.current = cancel;

    promise
      .then((data) => {
        setResult(data);
        setCurrentStage(3);
        setStageMessage("分析完成");
        setIsAnalyzing(false);
        refetchHistory();
        refetchLatest();
      })
      .catch((streamError: Error) => {
        setError(streamError.message || "分析失败");
        setIsAnalyzing(false);
        message.error(streamError.message || "分析失败");
      })
      .finally(() => {
        cancelStreamRef.current = null;
      });
  }, [navigate, refetchHistory, refetchLatest]);

  const handleLoadArchive = useCallback(async (item: IndustryChainHistoryItem) => {
    try {
      const data = await archiveMutation.mutateAsync({ name: item.name, archiveId: item.archive_id });
      setResult(data);
      setArchiveId(item.archive_id);
      setError("");
      setPushResult(null);
      setAgentProcess(createIndustryAgentProcessState());
      navigate(`/industry-chain/${encodeURIComponent(item.name)}`, { replace: true });
      setIsHistoryOpen(false);
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

    try {
      const response = await pushMutation.mutateAsync({
        target,
        type: "industry_chain",
        industry_name: activeName,
        archive_id: archiveId,
        feishu_receiver: target === "feishu" ? feishuReceiver.trim() : "",
      });
      setPushResult({ url: response.url, message: response.message, target });
      message.success(response.message || `已推送到 ${target}`);
    } catch (pushError) {
      const detail = pushError as { response?: { data?: { detail?: string } }; message?: string };
      message.error(detail.response?.data?.detail || detail.message || "推送失败");
    }
  }, [activeName, archiveId, pushMutation, result]);

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
      <div
        style={{
          ...pageHeaderStyle,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <div>
          <Title level={3} style={pageTitleStyle}>
            <ApartmentOutlined style={{ marginRight: 8 }} />
            产业链分析
          </Title>
          <Paragraph style={pageDescriptionStyle}>输入产业关键词，AI 自动搜索数据并生成完整产业链分析报告</Paragraph>
        </div>
        {isCompactLayout && (
          <Button icon={<HistoryOutlined />} onClick={() => setIsHistoryOpen(true)}>
            历史产业链
          </Button>
        )}
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={18}>
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
          </div>

          {(isAnalyzing || agentProcess.plan || agentProcess.toolCalls.length > 0) && (
            <div style={{ ...cardStyle, padding: "20px 24px", marginBottom: 20 }}>
              <Steps
                current={currentStage}
                items={[
                  {
                    title: "数据采集",
                    icon: currentStage === 0 ? <LoadingOutlined /> : currentStage > 0 ? <CheckCircleOutlined /> : undefined,
                  },
                  {
                    title: "数据整理",
                    icon: currentStage === 1 ? <LoadingOutlined /> : currentStage > 1 ? <CheckCircleOutlined /> : undefined,
                  },
                  { title: "AI 分析", icon: currentStage === 2 ? <LoadingOutlined /> : undefined },
                ]}
              />
              {stageMessage && (
                <div style={{ marginTop: 12, color: colors.textSecondary, fontSize: 13 }}>
                  {isAnalyzing
                    ? <Spin size="small" style={{ marginRight: 8 }} />
                    : <CheckCircleOutlined style={{ marginRight: 8 }} />}
                  {stageMessage}
                </div>
              )}
              <AgentProcessPanel
                plan={agentProcess.plan}
                status={agentProcess.status}
                toolCalls={agentProcess.toolCalls}
                isRunning={isAnalyzing && currentStage === 0}
              />
            </div>
          )}

          {error && !isAnalyzing && (
            <div style={{ ...cardStyle, padding: 40, marginBottom: 20, textAlign: "center" }}>
              <CloseCircleOutlined style={{ fontSize: 40, color: colors.up, marginBottom: 12 }} />
              <div style={{ color: colors.up }}>{error}</div>
            </div>
          )}

          {result && (
            <IndustryReport
              result={result}
              activeName={activeName}
              archiveId={archiveId}
              defaultReceiver={config?.feishu_default_receiver}
              isPushing={pushMutation.isPending}
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
        </Col>
        {!isCompactLayout && (
          <Col lg={6}>
            <div style={{ position: "sticky", top: 24 }}>
              <HistoryPanel {...historyPanelProps} />
            </div>
          </Col>
        )}
      </Row>

      <Drawer
        title="历史产业链"
        placement="right"
        open={isCompactLayout && isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        width="min(420px, 100vw)"
        styles={{ body: { padding: 16 } }}
      >
        <HistoryPanel {...historyPanelProps} embedded />
      </Drawer>
    </div>
  );
}
