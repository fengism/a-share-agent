import { Button, Col, Form, Input, InputNumber, Popconfirm, Row, Select, Typography } from "antd";
import {
  movingAverageValidationError,
  rsiValidationError,
  stockCodesValidationError,
  type QuantFormValues,
  type StrategyOption,
} from "./quantForm";
import StrategyPresetPicker from "./StrategyPresetPicker";

const { Text } = Typography;

interface SavedStrategyToolbarProps {
  selectedId?: number;
  options: Array<{ value: number; label: string }>;
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  onSelect: (strategyId?: number) => void;
  onSave: () => void;
  onDelete: () => void;
  onReset: () => void;
}

export function SavedStrategyToolbar({
  selectedId,
  options,
  isLoading,
  isSaving,
  isDeleting,
  onSelect,
  onSave,
  onDelete,
  onReset,
}: SavedStrategyToolbarProps) {
  const selectedName = options.find((option) => option.value === selectedId)?.label;
  return (
    <div className="quant-saved-toolbar">
      <Select
        aria-label="已保存策略"
        value={selectedId}
        placeholder="加载已保存策略"
        allowClear
        loading={isLoading}
        options={options}
        onChange={(value) => onSelect(value ?? undefined)}
        className="quant-saved-select"
      />
      <div className="quant-saved-actions">
        <Button aria-label="恢复默认参数" onClick={onReset}>恢复默认</Button>
        <Button loading={isSaving} onClick={onSave}>保存当前策略</Button>
        <Popconfirm
          title={`删除已保存策略“${selectedName ?? ""}”？`}
          description="删除后无法恢复"
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          disabled={selectedId == null}
          onConfirm={onDelete}
        >
          <Button aria-label="删除已保存策略" danger disabled={selectedId == null} loading={isDeleting}>
            删除已保存策略
          </Button>
        </Popconfirm>
      </div>
    </div>
  );
}

export function FormSectionHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="quant-form-section-header">
      <Text strong>{title}</Text>
      <Text type="secondary">{description}</Text>
    </div>
  );
}

export function UniverseFields({ source }: { source: QuantFormValues["source"] }) {
  return (
    <section className="quant-form-section" aria-labelledby="quant-universe-title">
      <div id="quant-universe-title">
        <FormSectionHeader title="1. 回测范围" description="命名任务并确定参与回测的股票池" />
      </div>
      <Row gutter={[14, 0]} align="bottom">
        <Col xs={24} md={7}>
          <Form.Item name="name" label="回测名称" rules={[{ required: true, whitespace: true, message: "请输入回测名称" }]}>
            <Input maxLength={80} placeholder="例如：消费龙头双均线" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={8} md={5}>
          <Form.Item name="source" label="股票池">
            <Select options={[
              { value: "custom", label: "自定义股票" },
              { value: "portfolio", label: "当前持仓" },
            ]} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={16} md={12}>
          <Form.Item
            name="codes"
            label="股票代码"
            rules={[{
              validator: async (_, value?: string) => {
                const error = stockCodesValidationError(source, value);
                if (error) throw new Error(error);
              },
            }]}
            extra={source === "portfolio" ? "运行时读取当前持仓股票，最多 10 只" : "支持空格或逗号分隔，最多 10 只"}
          >
            <Input disabled={source === "portfolio"} placeholder="600519, 000001" />
          </Form.Item>
        </Col>
      </Row>
    </section>
  );
}

export function StrategyFields({
  strategyType,
  strategyOptions,
  onStrategyChange,
}: {
  strategyType: QuantFormValues["strategyType"];
  strategyOptions: StrategyOption[];
  onStrategyChange: (strategyType: QuantFormValues["strategyType"]) => void;
}) {
  return (
    <section className="quant-form-section" aria-labelledby="quant-strategy-title">
      <div id="quant-strategy-title">
        <FormSectionHeader title="2. 策略参数" description="选择交易逻辑并调整该策略的核心周期" />
      </div>
      <Form.Item name="strategyType" hidden>
        <Input />
      </Form.Item>
      <StrategyPresetPicker value={strategyType} options={strategyOptions} onChange={onStrategyChange} />
      <Row gutter={[14, 0]} align="bottom">
        {strategyType === "ma_cross" ? (
          <>
            <Col xs={12} sm={6} md={4}>
              <Form.Item name="fastPeriod" label="短均线" rules={[{ required: true, message: "请输入短均线周期" }]}>
                <InputNumber min={2} max={120} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={12} sm={6} md={4}>
              <Form.Item
                name="slowPeriod"
                label="长均线"
                dependencies={["fastPeriod"]}
                rules={[
                  { required: true, message: "请输入长均线周期" },
                  ({ getFieldValue }) => ({
                    validator: async (_, value?: number) => {
                      const error = movingAverageValidationError(getFieldValue("fastPeriod"), value);
                      if (error) throw new Error(error);
                    },
                  }),
                ]}
              >
                <InputNumber min={3} max={250} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </>
        ) : null}
        {strategyType === "momentum_breakout" ? (
          <Col xs={12} sm={6} md={4}>
            <Form.Item name="lookbackPeriod" label="突破周期" rules={[{ required: true, message: "请输入突破周期" }]}>
              <InputNumber min={2} max={250} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
        ) : null}
        {strategyType === "rsi_reversion" ? (
          <>
            <Col xs={8} sm={6} md={4}>
              <Form.Item name="rsiPeriod" label="RSI 周期" rules={[{ required: true, message: "请输入 RSI 周期" }]}>
                <InputNumber min={2} max={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={8} sm={6} md={4}>
              <Form.Item name="buyThreshold" label="买入阈值" rules={[{ required: true, message: "请输入买入阈值" }]}>
                <InputNumber min={0} max={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
            <Col xs={8} sm={6} md={4}>
              <Form.Item
                name="sellThreshold"
                label="卖出阈值"
                dependencies={["buyThreshold"]}
                rules={[
                  { required: true, message: "请输入卖出阈值" },
                  ({ getFieldValue }) => ({
                    validator: async (_, value?: number) => {
                      const error = rsiValidationError(getFieldValue("buyThreshold"), value);
                      if (error) throw new Error(error);
                    },
                  }),
                ]}
              >
                <InputNumber min={0} max={100} style={{ width: "100%" }} />
              </Form.Item>
            </Col>
          </>
        ) : null}
      </Row>
    </section>
  );
}
