import { useMemo, useState } from "react";
import { ExperimentOutlined } from "@ant-design/icons";
import { Card, Form, Space, message } from "antd";
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
  strategyConfig,
  strategyFormValues,
  strategyOptions as createStrategyOptions,
  type QuantFormValues,
} from "./quantForm";

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

export default function BacktestForm({ onCreated }: { onCreated: (run: QuantBacktestRun) => void }) {
  const { cardStyle } = useStyles();
  const [form] = Form.useForm<QuantFormValues>();
  const source = Form.useWatch("source", form) ?? INITIAL_VALUES.source;
  const strategyType = Form.useWatch("strategyType", form) ?? INITIAL_VALUES.strategyType;
  const [savedStrategyId, setSavedStrategyId] = useState<number>();
  const presets = useQuantStrategyPresets();
  const savedStrategies = useSavedQuantStrategies();
  const saveStrategy = useSaveQuantStrategy();
  const deleteStrategy = useDeleteQuantStrategy();
  const createRun = useCreateQuantBacktest();
  const strategyOptions = useMemo(() => createStrategyOptions(presets.data), [presets.data]);

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
    form.setFieldsValue({ name: saved.name, ...strategyFormValues(saved.config) });
  };

  const applyStrategyPreset = (nextStrategyType: QuantFormValues["strategyType"]) => {
    const selected = strategyOptions.find((option) => option.value === nextStrategyType);
    if (!selected) return;
    setSavedStrategyId(undefined);
    form.setFieldsValue(strategyFormValues(selected.config));
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
  };

  return (
    <Card
      size="small"
      title={<Space><ExperimentOutlined /><span>策略与回测参数</span></Space>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: { padding: "16px 18px" } }}
    >
      <Form form={form} layout="vertical" initialValues={INITIAL_VALUES} onFinish={submit}>
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
          onStrategyChange={applyStrategyPreset}
        />
        <BacktestExecutionFields isSubmitting={createRun.isPending} />
      </Form>
    </Card>
  );
}
