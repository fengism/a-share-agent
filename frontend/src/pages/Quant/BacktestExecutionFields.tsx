import { InfoCircleOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { AutoComplete, Button, Col, Collapse, DatePicker, Form, InputNumber, Row, Typography } from "antd";
import dayjs from "dayjs";
import BacktestAdvancedFields from "./BacktestAdvancedFields";
import { FormSectionHeader } from "./BacktestFormSections";
import { dateRangeValidationError, type QuantFormValues } from "./quantForm";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const BENCHMARK_OPTIONS = [
  { value: "000300", label: "000300 · 沪深300 (大盘蓝筹)" },
  { value: "000905", label: "000905 · 中证500 (中盘成长)" },
  { value: "000852", label: "000852 · 中证1000 (小盘创新)" },
  { value: "399006", label: "399006 · 创业板指 (高成长创新)" },
  { value: "000001", label: "000001 · 上证指数 (综合大盘)" },
];

export default function BacktestExecutionFields({ isSubmitting }: { isSubmitting: boolean }) {
  return (
    <section className="quant-form-section quant-form-section-last" aria-labelledby="quant-execution-title">
      <div id="quant-execution-title">
        <FormSectionHeader title="3. 执行设置" description="确定回测区间、比较基准和资金假设" />
      </div>
      <Row gutter={[14, 0]} align="bottom" className="quant-basic-execution-fields">
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
            <AutoComplete
              options={BENCHMARK_OPTIONS}
              filterOption={(inputValue, option) =>
                (option?.value?.toUpperCase().includes(inputValue.toUpperCase()) ?? false) ||
                (option?.label?.includes(inputValue) ?? false)
              }
              placeholder="000300"
            />
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
          label: <span className="quant-advanced-label">高级执行参数<small>交易成本 / 仓位管理 / 退出保护</small></span>,
          children: <BacktestAdvancedFields />,
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
