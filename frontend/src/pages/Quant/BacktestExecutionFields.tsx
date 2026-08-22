import { InfoCircleOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { Button, Col, Collapse, DatePicker, Form, Input, InputNumber, Row, Typography } from "antd";
import dayjs from "dayjs";
import { FormSectionHeader } from "./BacktestFormSections";
import { dateRangeValidationError, type QuantFormValues } from "./quantForm";

const { Text } = Typography;
const { RangePicker } = DatePicker;

function AdvancedExecutionFields() {
  return (
    <Row gutter={[14, 0]} align="bottom" className="quant-advanced-execution-fields">
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="commissionBps"
          label="佣金（BP）"
          rules={[{ required: true, type: "number", min: 0, max: 100, message: "佣金需在 0-100 BP" }]}
        >
          <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="minimumCommission"
          label="最低佣金（元）"
          rules={[{ required: true, type: "number", min: 0, max: 1000, message: "最低佣金需在 0-1000 元" }]}
        >
          <InputNumber min={0} max={1000} step={1} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="stampDutyBps"
          label="印花税（BP）"
          rules={[{ required: true, type: "number", min: 0, max: 100, message: "印花税需在 0-100 BP" }]}
        >
          <InputNumber min={0} max={100} step={0.1} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="transferFeeBps"
          label="过户费（BP）"
          rules={[{ required: true, type: "number", min: 0, max: 100, message: "过户费需在 0-100 BP" }]}
        >
          <InputNumber min={0} max={100} step={0.01} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="lotSize"
          label="交易单位（股）"
          rules={[{ required: true, type: "number", min: 1, max: 10_000, message: "交易单位需在 1-10000 股" }]}
        >
          <InputNumber min={1} max={10_000} step={100} precision={0} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
      <Col xs={12} sm={8} md={4}>
        <Form.Item
          name="riskFreeRatePercent"
          label="无风险利率（%）"
          rules={[{ required: true, type: "number", min: -10, max: 50, message: "无风险利率需在 -10%-50%" }]}
        >
          <InputNumber min={-10} max={50} step={0.1} style={{ width: "100%" }} />
        </Form.Item>
      </Col>
    </Row>
  );
}

export default function BacktestExecutionFields({ isSubmitting }: { isSubmitting: boolean }) {
  return (
    <section className="quant-form-section quant-form-section-last" aria-labelledby="quant-execution-title">
      <div id="quant-execution-title">
        <FormSectionHeader title="3. 执行设置" description="确定回测区间、比较基准和资金假设" />
      </div>
      <Row gutter={[14, 0]} align="bottom">
        <Col xs={24} md={8}>
          <Form.Item
            name="dateRange"
            label="回测区间"
            rules={[{
              validator: async (_, value?: QuantFormValues["dateRange"]) => {
                const error = dateRangeValidationError(value);
                if (error) throw new Error(error);
              },
            }]}
          >
            <RangePicker maxDate={dayjs()} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Form.Item
            name="benchmark"
            label="基准指数"
            rules={[{
              validator: async (_, value?: string) => {
                if (!/^\d{6}$/.test(value?.trim() ?? "")) throw new Error("基准指数代码必须为 6 位数字");
              },
            }]}
          >
            <Input maxLength={8} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8} md={7}>
          <Form.Item name="initialCash" label="初始资金" rules={[{ required: true, message: "请输入初始资金" }]}>
            <InputNumber min={10_000} max={1_000_000_000} step={100_000} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
        <Col xs={12} sm={8} md={5}>
          <Form.Item name="slippageBps" label="滑点 BP" rules={[{ required: true, message: "请输入滑点" }]}>
            <InputNumber min={0} max={500} style={{ width: "100%" }} />
          </Form.Item>
        </Col>
      </Row>
      <Collapse
        ghost
        size="small"
        className="quant-advanced-execution"
        items={[{
          key: "advanced",
          label: "高级执行参数",
          children: <AdvancedExecutionFields />,
        }]}
      />
      <div className="quant-submit-bar">
        <div className="quant-execution-note">
          <InfoCircleOutlined />
          <span>
            <strong>执行规则</strong>
            <Text type="secondary">信号按 T 日收盘计算，T+1 开盘执行；1 BP = 0.01%。</Text>
          </span>
        </div>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          htmlType="submit"
          loading={isSubmitting}
          aria-label="开始回测"
        >
          开始回测
        </Button>
      </div>
    </section>
  );
}
