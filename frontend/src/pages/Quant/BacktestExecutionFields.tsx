import { InfoCircleOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { AutoComplete, Button, Col, Collapse, DatePicker, Form, InputNumber, Row, Tag, Typography } from "antd";
import dayjs, { type Dayjs } from "dayjs";
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

const DATE_RANGE_PRESETS: Array<{ label: string; value: [Dayjs, Dayjs] }> = [
  { label: "近1年", value: [dayjs().subtract(1, "year"), dayjs()] },
  { label: "近3年", value: [dayjs().subtract(3, "year"), dayjs()] },
  { label: "今年(YTD)", value: [dayjs().startOf("year"), dayjs()] },
  { label: "近5年", value: [dayjs().subtract(5, "year"), dayjs()] },
];

const QUICK_BENCHMARKS = [
  { label: "沪深300", code: "000300" },
  { label: "中证500", code: "000905" },
  { label: "中证1000", code: "000852" },
  { label: "创业板指", code: "399006" },
  { label: "上证指数", code: "000001" },
];

export default function BacktestExecutionFields({ isSubmitting }: { isSubmitting: boolean }) {
  const form = Form.useFormInstance<QuantFormValues>();

  const handleSelectDatePreset = (range: [Dayjs, Dayjs]) => {
    form.setFieldValue("dateRange", range);
  };

  const handleSelectBenchmark = (code: string) => {
    form.setFieldValue("benchmark", code);
  };

  return (
    <section className="quant-form-section quant-form-section-last" aria-labelledby="quant-execution-title">
      <div id="quant-execution-title">
        <FormSectionHeader title="3. 执行设置" description="确定回测区间、比较基准和资金假设" />
      </div>
      <Row gutter={[14, 0]} align="top" className="quant-basic-execution-fields">
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
            extra={(
              <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "4px" }}>
                {DATE_RANGE_PRESETS.map((p) => (
                  <Tag
                    key={p.label}
                    style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                    onClick={() => handleSelectDatePreset(p.value)}
                  >
                    {p.label}
                  </Tag>
                ))}
              </div>
            )}
          >
            <RangePicker presets={DATE_RANGE_PRESETS} maxDate={dayjs()} style={{ width: "100%" }} />
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
            extra={(
              <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginTop: "4px" }}>
                {QUICK_BENCHMARKS.map((b) => (
                  <Tag
                    key={b.code}
                    style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                    onClick={() => handleSelectBenchmark(b.code)}
                  >
                    {b.label}
                  </Tag>
                ))}
              </div>
            )}
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
