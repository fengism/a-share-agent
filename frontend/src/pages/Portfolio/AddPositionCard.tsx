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
  Row,
  message,
} from "antd";
import { PlusOutlined, SearchOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { useAddPortfolioPosition } from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useColors, useStyles } from "../../styles/ui";
import { errorMessage, formatPrice } from "./portfolioFormatters";

interface PositionFormValues {
  buy_price: number;
  buy_time: Dayjs;
  shares: number;
}

export default function AddPositionCard() {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [form] = Form.useForm<PositionFormValues>();
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
  const addMutation = useAddPortfolioPosition();

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

  const handleAdd = async (values: PositionFormValues) => {
    const stockCode = resolveCode();
    if (!stockCode) {
      message.warning("请选择搜索结果中的股票，或输入 6 位股票代码");
      return;
    }

    try {
      await addMutation.mutateAsync({
        stock_code: stockCode,
        buy_price: values.buy_price,
        buy_time: values.buy_time.format("YYYY-MM-DDTHH:mm:ss"),
        shares: values.shares,
      });
      message.success("买入记录已添加");
      clearSearch();
      form.setFieldsValue({ buy_price: undefined, buy_time: dayjs(), shares: 100 });
    } catch (mutationError) {
      message.error(`添加失败：${errorMessage(mutationError)}`);
    }
  };

  return (
    <Card
      title="新增买入记录"
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: { padding: isMobile ? "16px 14px 4px" : "18px 20px 4px" } }}
    >
      <Form<PositionFormValues>
        form={form}
        layout="vertical"
        initialValues={{ buy_time: dayjs(), shares: 100 }}
        onFinish={handleAdd}
      >
        <Row gutter={[16, 0]} align="bottom">
          <Col xs={24} md={8}>
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
                <Input
                  prefix={<SearchOutlined />}
                  placeholder="输入股票代码或名称"
                  allowClear
                />
              </AutoComplete>
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={4}>
            <Form.Item
              name="buy_price"
              label="买入价"
              rules={[{ required: true, message: "请输入买入价" }]}
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
          <Col xs={24} sm={12} md={5}>
            <Form.Item
              name="buy_time"
              label="买入时间"
              rules={[
                { required: true, message: "请选择买入时间" },
                {
                  validator: async (_, value: Dayjs | undefined) => {
                    if (value?.isAfter(dayjs())) throw new Error("买入时间不能晚于当前时间");
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
          <Col xs={24} sm={12} md={4}>
            <Form.Item
              name="shares"
              label="股数"
              rules={[{ required: true, message: "请输入股数" }]}
            >
              <InputNumber
                min={1}
                max={1_000_000_000}
                precision={0}
                step={100}
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={3}>
            <Form.Item label={isMobile ? undefined : " "}>
              <Button
                type="primary"
                htmlType="submit"
                icon={<PlusOutlined />}
                loading={addMutation.isPending}
                style={{ width: "100%" }}
              >
                添加
              </Button>
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}
