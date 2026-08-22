import { useMemo } from "react";
import {
  AutoComplete,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  message,
} from "antd";
import { EyeOutlined, SearchOutlined, SwapOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { useCreatePortfolioTransaction, usePreviewPortfolioTransaction } from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useColors, useStyles } from "../../styles/ui";
import type { PortfolioStockSummary, PortfolioTransactionCreate } from "../../types/portfolio";
import { errorMessage, formatInteger, formatPrice } from "./portfolioFormatters";
import TransactionPreviewAlert from "./TransactionPreviewAlert";

interface TransactionFormValues {
  side: "buy" | "sell";
  sell_stock_code?: string;
  trade_price: number;
  trade_time: Dayjs;
  shares: number;
  fee?: number;
  note?: string;
}

interface TransactionEntryCardProps {
  stocks: PortfolioStockSummary[];
}

export default function TransactionEntryCard({ stocks }: TransactionEntryCardProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [form] = Form.useForm<TransactionFormValues>();
  const side = Form.useWatch("side", form) ?? "buy";
  const sellStockCode = Form.useWatch("sell_stock_code", form);
  const {
    inputValue,
    normalizedInput,
    currentResults,
    isPending: isSearchPending,
    isError: isSearchError,
    error: searchError,
    retry: retrySearch,
    setInputValue,
    clear: clearSearch,
    resolveCode,
  } = useStockSearchController();
  const createMutation = useCreatePortfolioTransaction();
  const previewMutation = usePreviewPortfolioTransaction();

  const searchOptions = useMemo(() => currentResults.map((item) => ({
    value: item.code,
    label: (
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <span>{item.name} ({item.code})</span>
        <span style={{ color: colors.textSecondary }}>
          {item.price == null ? "" : formatPrice(item.price)}
        </span>
      </div>
    ),
  })), [colors.textSecondary, currentResults]);

  const sellOptions = useMemo(() => stocks.map((stock) => ({
    value: stock.stock_code,
    label: `${stock.stock_name} (${stock.stock_code}) · 可卖 ${formatInteger(stock.total_shares)} 股`,
  })), [stocks]);
  const selectedHolding = stocks.find((stock) => stock.stock_code === sellStockCode);

  const buildTransaction = (values: TransactionFormValues): PortfolioTransactionCreate | null => {
    const stockCode = values.side === "buy" ? resolveCode() : values.sell_stock_code;
    if (!stockCode) {
      message.warning(values.side === "buy" ? "请选择搜索结果中的股票，或输入 6 位股票代码" : "请选择持仓股票");
      return null;
    }
    return {
      stock_code: stockCode,
      side: values.side,
      trade_price: values.trade_price,
      trade_time: values.trade_time.format("YYYY-MM-DDTHH:mm:ss"),
      shares: values.shares,
      fee: values.fee ?? 0,
      note: values.note?.trim() ?? "",
    };
  };

  const handlePreview = async () => {
    let values: TransactionFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    const transaction = buildTransaction(values);
    if (!transaction || transaction.side !== "sell") return;
    previewMutation.reset();
    try {
      await previewMutation.mutateAsync(transaction);
    } catch (mutationError) {
      message.error(`预演失败：${errorMessage(mutationError)}`);
    }
  };

  const handleSubmit = async (values: TransactionFormValues) => {
    const transaction = buildTransaction(values);
    if (!transaction) return;
    if (values.side === "sell" && selectedHolding && values.shares > selectedHolding.total_shares) {
      message.warning(`最多可卖 ${formatInteger(selectedHolding.total_shares)} 股`);
      return;
    }

    try {
      await createMutation.mutateAsync(transaction);
      message.success(values.side === "buy" ? "买入流水已记录" : "卖出流水已记录");
      clearSearch();
      previewMutation.reset();
      form.setFieldsValue({
        sell_stock_code: undefined,
        trade_price: undefined,
        trade_time: dayjs(),
        shares: undefined,
        fee: 0,
        note: "",
      });
    } catch (mutationError) {
      message.error(`记录失败：${errorMessage(mutationError)}`);
    }
  };

  return (
    <Card
      title="记录交易流水"
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: { padding: isMobile ? "16px 14px 4px" : "18px 20px 4px" } }}
    >
      <Form<TransactionFormValues>
        form={form}
        layout="vertical"
        initialValues={{ side: "buy", trade_time: dayjs(), fee: 0 }}
        onFinish={handleSubmit}
        onValuesChange={() => previewMutation.reset()}
      >
        <Row gutter={[16, 0]} align="bottom">
          <Col xs={24} sm={8} md={4}>
            <Form.Item name="side" label="方向">
              <Radio.Group buttonStyle="solid" style={{ width: "100%" }}>
                <Radio.Button value="buy" style={{ width: "50%", textAlign: "center" }}>买入</Radio.Button>
                <Radio.Button value="sell" style={{ width: "50%", textAlign: "center" }}>卖出</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </Col>
          <Col xs={24} sm={16} md={7}>
            {side === "buy" ? (
              <Form.Item label="股票" required>
                <AutoComplete
                  value={inputValue}
                  options={searchOptions}
                  onChange={setInputValue}
                  onSelect={(value) => setInputValue(value)}
                  filterOption={false}
                  notFoundContent={
                    isSearchPending
                      ? "搜索中..."
                      : isSearchError
                        ? <QueryErrorState error={searchError} onRetry={() => retrySearch()} title="搜索失败" compact />
                        : normalizedInput ? "未找到匹配股票" : null
                  }
                >
                  <Input prefix={<SearchOutlined />} placeholder="输入股票代码或名称" allowClear />
                </AutoComplete>
              </Form.Item>
            ) : (
              <Form.Item
                name="sell_stock_code"
                label="持仓股票"
                rules={[{ required: true, message: "请选择持仓股票" }]}
              >
                <Select
                  options={sellOptions}
                  placeholder={stocks.length ? "选择要卖出的股票" : "当前没有可卖持仓"}
                  disabled={!stocks.length}
                  showSearch
                  optionFilterProp="label"
                />
              </Form.Item>
            )}
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Form.Item
              name="trade_price"
              label={side === "buy" ? "买入价" : "卖出价"}
              rules={[{ required: true, message: "请输入成交价" }]}
            >
              <InputNumber
                min={0.0001}
                max={1_000_000}
                precision={4}
                step={0.01}
                prefix="¥"
                placeholder="0.00"
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Form.Item
              name="shares"
              label={side === "sell" && selectedHolding ? `股数（最多 ${formatInteger(selectedHolding.total_shares)}）` : "股数"}
              rules={[{ required: true, message: "请输入股数" }]}
            >
              <InputNumber
                min={1}
                max={side === "sell" ? selectedHolding?.total_shares : 1_000_000_000}
                precision={0}
                step={1}
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={12} sm={8} md={5}>
            <Form.Item
              name="trade_time"
              label="成交时间"
              rules={[
                { required: true, message: "请选择成交时间" },
                {
                  validator: async (_, value: Dayjs | undefined) => {
                    if (value?.isAfter(dayjs())) throw new Error("成交时间不能晚于当前时间");
                  },
                },
              ]}
            >
              <DatePicker
                showTime={{ format: "HH:mm" }}
                format="YYYY-MM-DD HH:mm"
                maxDate={dayjs()}
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={12} sm={8} md={4}>
            <Form.Item name="fee" label="手续费（可选）">
              <InputNumber min={0} max={1_000_000_000} precision={2} prefix="¥" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={16} md={15}>
            <Form.Item name="note" label="备注（可选）">
              <Input maxLength={500} placeholder="记录交易原因或其他说明" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8} md={5}>
            <Form.Item label={isMobile ? undefined : " "}>
              <Space.Compact block>
                {side === "sell" ? (
                  <Button
                    icon={<EyeOutlined />}
                    loading={previewMutation.isPending}
                    disabled={!stocks.length}
                    onClick={handlePreview}
                    style={{ width: "50%" }}
                  >
                    预演卖出
                  </Button>
                ) : null}
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<SwapOutlined />}
                  loading={createMutation.isPending}
                  disabled={side === "sell" && !stocks.length}
                  style={{ width: side === "sell" ? "50%" : "100%" }}
                >
                  记录{side === "buy" ? "买入" : "卖出"}
                </Button>
              </Space.Compact>
            </Form.Item>
          </Col>
        </Row>
        {side === "sell" && previewMutation.data ? (
          <div style={{ marginBottom: 16 }}>
            <TransactionPreviewAlert preview={previewMutation.data} title="卖出预演结果" />
          </div>
        ) : null}
      </Form>
    </Card>
  );
}
