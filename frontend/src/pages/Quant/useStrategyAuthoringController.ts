import { useEffect, useMemo, useState } from "react";
import { message } from "antd";
import {
  useBacktestQuantStrategyDraft,
  useGenerateQuantStrategyDraft,
  usePublishQuantStrategyDraft,
  useQuantStrategyDrafts,
  useQuantStrategyRegistryStatus,
  useUpdateQuantStrategyDraft,
  useValidateQuantStrategyDraft,
  type QuantBacktestRun,
  type QuantStrategyDefinitionInput,
  type QuantStrategyDraft,
} from "../../api/queries";
import { parseDraftStockCodes, type DraftBacktestValues } from "./strategyAuthoring";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

export function useStrategyAuthoringController(
  onBacktestCreated: (run: QuantBacktestRun) => void,
) {
  const draftsQuery = useQuantStrategyDrafts();
  const registryQuery = useQuantStrategyRegistryStatus();
  const generateDraft = useGenerateQuantStrategyDraft();
  const updateDraft = useUpdateQuantStrategyDraft();
  const validateDraft = useValidateQuantStrategyDraft();
  const backtestDraft = useBacktestQuantStrategyDraft();
  const publishDraft = usePublishQuantStrategyDraft();
  const [prompt, setPrompt] = useState("");
  const [selectedDraftId, setSelectedDraftId] = useState("");
  const [definitionText, setDefinitionText] = useState("");
  const [isDefinitionDirty, setIsDefinitionDirty] = useState(false);
  const drafts = useMemo(() => draftsQuery.data ?? [], [draftsQuery.data]);
  const selectedDraft = drafts.find((draft) => draft.id === selectedDraftId);

  useEffect(() => {
    if (!selectedDraftId && drafts[0]) setSelectedDraftId(drafts[0].id);
  }, [drafts, selectedDraftId]);

  useEffect(() => {
    if (!selectedDraft) return;
    setDefinitionText(JSON.stringify(selectedDraft.definition, null, 2));
    setIsDefinitionDirty(false);
  }, [selectedDraft]);

  const selectDraft = (draft: QuantStrategyDraft) => {
    setSelectedDraftId(draft.id);
    setDefinitionText(JSON.stringify(draft.definition, null, 2));
    setIsDefinitionDirty(false);
  };

  const generate = async () => {
    if (prompt.trim().length < 10) {
      message.warning("请至少用 10 个字符描述策略逻辑");
      return;
    }
    try {
      const draft = await generateDraft.mutateAsync(prompt.trim());
      selectDraft(draft);
      message.success("策略草稿已生成并完成初始校验");
    } catch (error) {
      message.error(`生成失败：${errorText(error)}`);
    }
  };

  const save = async () => {
    if (!selectedDraft) return;
    try {
      const definition = JSON.parse(definitionText) as QuantStrategyDefinitionInput;
      const draft = await updateDraft.mutateAsync({
        draftId: selectedDraft.id,
        expectedDefinitionHash: selectedDraft.definition_hash,
        definition,
      });
      selectDraft(draft);
      message.success("草稿定义已保存，请重新校验");
    } catch (error) {
      message.error(`保存失败：${errorText(error)}`);
    }
  };

  const validate = async () => {
    if (!selectedDraft) return;
    try {
      const draft = await validateDraft.mutateAsync(selectedDraft.id);
      selectDraft(draft);
      message.success("草稿校验通过");
    } catch (error) {
      message.error(`校验失败：${errorText(error)}`);
    }
  };

  const backtest = async (values: DraftBacktestValues) => {
    if (!selectedDraft) return;
    try {
      const run = await backtestDraft.mutateAsync({
        draftId: selectedDraft.id,
        request: {
          universe: { source: "custom", codes: parseDraftStockCodes(values.codes) },
          start_date: values.dateRange[0].format("YYYY-MM-DD"),
          end_date: values.dateRange[1].format("YYYY-MM-DD"),
          benchmark: values.benchmark.trim(),
          minimum_trade_count: values.minimumTradeCount,
          maximum_drawdown_pct: values.maximumDrawdownPct,
          minimum_sharpe_ratio: values.minimumSharpeRatio,
          minimum_holdout_trade_count: values.minimumHoldoutTradeCount,
          maximum_holdout_drawdown_pct: values.maximumHoldoutDrawdownPct,
          minimum_holdout_sharpe_ratio: values.minimumHoldoutSharpeRatio,
        },
      });
      onBacktestCreated(run);
      message.success("草稿回测已入队，完成后自动计算质量门禁");
    } catch (error) {
      message.error(`试跑失败：${errorText(error)}`);
    }
  };

  const publish = async () => {
    if (!selectedDraft) return;
    try {
      const draft = await publishDraft.mutateAsync({
        draftId: selectedDraft.id,
        expectedDefinitionHash: selectedDraft.definition_hash,
      });
      selectDraft(draft);
      message.success("策略已发布；重复提交会自动复用并完成状态对账");
    } catch (error) {
      message.error(`发布失败：${errorText(error)}`);
    }
  };

  const isDefinitionLocked = !selectedDraft || !["draft", "validated"].includes(selectedDraft.status);
  const isBusy = generateDraft.isPending || updateDraft.isPending || validateDraft.isPending;

  return {
    backtest,
    definitionText,
    drafts,
    isBacktesting: backtestDraft.isPending,
    isBusy,
    isDefinitionDirty,
    isDefinitionLocked,
    isDraftsLoading: draftsQuery.isLoading,
    isGenerating: generateDraft.isPending,
    isPublishing: publishDraft.isPending,
    isSaving: updateDraft.isPending,
    isValidating: validateDraft.isPending,
    prompt,
    publish,
    registry: registryQuery.data,
    save,
    selectedDraft,
    selectedDraftId,
    selectDraftId: setSelectedDraftId,
    setDefinitionText: (value: string) => {
      setDefinitionText(value);
      setIsDefinitionDirty(true);
    },
    setPrompt,
    generate,
    validate,
  };
}
