import { ExperimentOutlined } from "@ant-design/icons";
import { Button, Card, DatePicker, Form, Input, InputNumber, Space, Typography } from "antd";
import dayjs from "dayjs";
import { parseDraftStockCodes, type DraftBacktestValues } from "../strategyAuthoring";

const { RangePicker } = DatePicker;

interface StrategyDraftBacktestCardProps {
  isBacktesting: boolean;
  isDisabled: boolean;
  onBacktest: (values: DraftBacktestValues) => Promise<void>;
}

export default function StrategyDraftBacktestCard({
  isBacktesting,
  isDisabled,
  onBacktest,
}: StrategyDraftBacktestCardProps) {
  const [form] = Form.useForm<DraftBacktestValues>();

  return (
    <Card
      className="quant-authoring-card quant-authoring-backtest"
      title={<Space><ExperimentOutlined />草稿试跑与质量门禁</Space>}
    >
      <Form<DraftBacktestValues>
        form={form}
        layout="vertical"
        initialValues={{
          codes: "600519",
          dateRange: [dayjs().subtract(1, "year"), dayjs()],
          benchmark: "000300",
          minimumTradeCount: 1,
          maximumDrawdownPct: 80,
        }}
        onFinish={(values) => void onBacktest(values)}
      >
        <div className="quant-authoring-backtest-grid">
          <Form.Item
            name="codes"
            label="股票代码"
            rules={[{
              validator: async (_, value?: string) => {
                const codes = parseDraftStockCodes(value ?? "");
                if (!codes.length || codes.length > 10 || codes.some((code) => !/^\d{6}$/.test(code))) {
                  throw new Error("请输入 1-10 个六位股票代码");
                }
              },
            }]}
          >
            <Input placeholder="600519, 000858" />
          </Form.Item>
          <Form.Item name="dateRange" label="回测区间" rules={[{ required: true, message: "请选择回测区间" }]}>
            <RangePicker maxDate={dayjs()} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="benchmark" label="基准指数" rules={[{ pattern: /^\d{6}$/, message: "请输入六位指数代码" }]}>
            <Input maxLength={6} />
          </Form.Item>
          <Form.Item name="minimumTradeCount" label="最低交易次数">
            <InputNumber min={1} max={10_000} precision={0} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="maximumDrawdownPct" label="最大允许回撤（%）">
            <InputNumber min={0.01} max={80} step={1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="minimumSharpeRatio" label="整体最低夏普比率（可选）">
            <InputNumber min={-20} max={20} step={0.1} placeholder="不限制" style={{ width: "100%" }} />
          </Form.Item>
          <Typography.Text strong className="quant-authoring-gate-heading">
            后段样本门禁
          </Typography.Text>
          <Form.Item name="minimumHoldoutTradeCount" label="后段最低交易次数（可选）">
            <InputNumber min={0} max={10_000} precision={0} placeholder="不限制" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="maximumHoldoutDrawdownPct" label="后段最大允许回撤（可选，%）">
            <InputNumber min={0.01} max={80} step={1} placeholder="不限制" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="minimumHoldoutSharpeRatio" label="后段最低夏普比率（可选）">
            <InputNumber min={-20} max={20} step={0.1} placeholder="不限制" style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label=" ">
            <Button
              type="primary"
              htmlType="submit"
              icon={<ExperimentOutlined />}
              disabled={isDisabled}
              loading={isBacktesting}
              block
            >
              使用当前快照试跑
            </Button>
          </Form.Item>
        </div>
      </Form>
    </Card>
  );
}
