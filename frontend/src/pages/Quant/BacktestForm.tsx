import { useEffect, useMemo, useState } from "react";
import { ExperimentOutlined } from "@ant-design/icons";
import { Card, Form, message } from "antd";
import {
  useCreateQuantBacktest,
  useDeleteQuantStrategy,
  useQuantStrategyPresets,
  useSavedQuantStrategies,
  useSaveQuantStrategy,
  type QuantBacktestRun,
} from "../../api/queries";
import { useStyles } from "../../styles/ui";
import {
  SavedStrategyToolbar,
  StrategyFields,
  UniverseFields,
} from "./BacktestFormSections";
import BacktestExecutionFields from "./BacktestExecutionFields";
import {
  INITIAL_VALUES,
  buildBacktestRequest,
  parseStockCodes,
  strategyConfig,
  strategyFormValues,
  strategyOptions as createStrategyOptions,
  type QuantFormValues,
} from "./quantForm";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

interface BacktestFormProps {
  onCreated: (run: QuantBacktestRun) => void;
  initialCodes?: string[];
}

export default function BacktestForm({ onCreated, initialCodes = [] }: BacktestFormProps) {
  const { cardStyle } = useStyles();
  const [form] = Form.useForm<QuantFormValues>();
  const source = Form.useWatch("source", form) ?? INITIAL_VALUES.source;
  const strategyType = Form.useWatch("strategyType", form) ?? INITIAL_VALUES.strategyType;
  const [savedStrategyId, setSavedStrategyId] = useState<number>();
  const [liveStrategyParameters, setLiveStrategyParameters] = useState(INITIAL_VALUES.strategyParameters);
  const presets = useQuantStrategyPresets();
  const savedStrategies = useSavedQuantStrategies();
  const saveStrategy = useSaveQuantStrategy();
  const deleteStrategy = useDeleteQuantStrategy();
  const createRun = useCreateQuantBacktest();
  const strategyOptions = useMemo(() => createStrategyOptions(presets.data), [presets.data]);
  const initialCodesValue = initialCodes.join(", ");

  useEffect(() => {
    if (!initialCodesValue) return;
    form.setFieldsValue({
      source: "custom",
      codes: initialCodesValue,
      name: `双均线趋势 · ${initialCodes.length}只股票回测`,
    });
  }, [form, initialCodes.length, initialCodesValue]);

  const submit = async () => {
    const values = form.getFieldsValue(true) as QuantFormValues;
    try {
      const run = await createRun.mutateAsync(buildBacktestRequest(values));
      message.success("回测任务已提交");
      onCreated(run);
    } catch (error) {
      message.error(`提交失败：${errorText(error)}`);
    }
  };

  const applySavedStrategy = (strategyId: number) => {
    const saved = savedStrategies.data?.find((strategy) => strategy.id === strategyId);
    if (!saved) return;
    setSavedStrategyId(strategyId);
    setLiveStrategyParameters(saved.config.parameters ?? {});
    form.setFieldValue("strategyParameters", {});
    form.setFieldsValue({ name: saved.name, ...strategyFormValues(saved.config) });
  };

  const applyStrategyPreset = (nextStrategyType: QuantFormValues["strategyType"]) => {
    const selected = strategyOptions.find((option) => option.value === nextStrategyType);
    if (!selected) return;
    const currentName = form.getFieldValue("name")?.trim();
    const generatedName = strategyOptions.some((option) => (
      currentName === `${option.label}回测`
      || (currentName?.startsWith(`${option.label} · `) && currentName.endsWith("回测"))
    ));
    const shouldUpdateName = !currentName
      || currentName === INITIAL_VALUES.name
      || currentName === "双均线回测"
      || /^\d+ 只股票组合回测$/.test(currentName)
      || generatedName;
    const selectedSource = form.getFieldValue("source") ?? INITIAL_VALUES.source;
    const selectedCodes = parseStockCodes(form.getFieldValue("codes") ?? INITIAL_VALUES.codes);
    const scopeLabel = selectedSource === "portfolio"
      ? "当前持仓"
      : selectedCodes.length === 1
        ? selectedCodes[0]
        : `${selectedCodes.length || 1}只股票`;
    const nextName = shouldUpdateName ? `${selected.label} · ${scopeLabel}回测` : undefined;
    setSavedStrategyId(undefined);
    setLiveStrategyParameters(selected.config.parameters ?? {});
    form.setFieldValue("strategyParameters", {});
    form.setFieldsValue({
      ...strategyFormValues(selected.config),
      ...(nextName ? { name: nextName } : {}),
    });
  };

  const saveCurrentStrategy = async () => {
    const values = form.getFieldsValue(true) as QuantFormValues;
    if (!values.name?.trim()) {
      message.warning("请先填写回测名称");
      return;
    }
    try {
      const saved = await saveStrategy.mutateAsync({ name: values.name.trim(), config: strategyConfig(values) });
      setSavedStrategyId(saved.id);
      message.success("策略已保存");
    } catch (error) {
      message.error(`保存失败：${errorText(error)}`);
    }
  };

  const deleteCurrentStrategy = async () => {
    if (savedStrategyId == null) return;
    try {
      await deleteStrategy.mutateAsync(savedStrategyId);
      setSavedStrategyId(undefined);
      message.success("策略已删除");
    } catch (error) {
      message.error(`删除失败：${errorText(error)}`);
    }
  };

  const resetForm = () => {
    form.resetFields();
    setSavedStrategyId(undefined);
    setLiveStrategyParameters(INITIAL_VALUES.strategyParameters);
  };

  return (
    <Card
      size="small"
      title={(
        <div className="quant-card-heading">
          <span className="quant-card-heading-icon"><ExperimentOutlined /></span>
          <span>
            <strong>策略与回测参数</strong>
            <small>按步骤完成股票池、策略和执行条件配置</small>
          </span>
        </div>
      )}
      style={cardStyle}
      className="quant-form-card"
    >
      <Form
        className="quant-form"
        form={form}
        layout="vertical"
        initialValues={INITIAL_VALUES}
        onFinish={submit}
        onValuesChange={(_, values: QuantFormValues) => {
          setLiveStrategyParameters(values.strategyParameters ?? {});
        }}
      >
        <SavedStrategyToolbar
          selectedId={savedStrategyId}
          options={savedStrategies.data?.map((strategy) => ({ value: strategy.id, label: strategy.name })) ?? []}
          isLoading={savedStrategies.isLoading}
          isSaving={saveStrategy.isPending}
          isDeleting={deleteStrategy.isPending}
          onSelect={(strategyId) => strategyId == null ? setSavedStrategyId(undefined) : applySavedStrategy(strategyId)}
          onSave={saveCurrentStrategy}
          onDelete={deleteCurrentStrategy}
          onReset={resetForm}
        />
        <UniverseFields source={source} />
        <StrategyFields
          strategyType={strategyType}
          strategyOptions={strategyOptions}
          parameterValues={liveStrategyParameters}
          onStrategyChange={applyStrategyPreset}
        />
        <BacktestExecutionFields isSubmitting={createRun.isPending} />
      </Form>
    </Card>
  );
}
