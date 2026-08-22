import { Button, Col, DatePicker, Form, Input, InputNumber, Modal, Radio, Row, message } from "antd";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { useEffect } from "react";
import { usePreviewPortfolioTransactionUpdate, useUpdatePortfolioTransaction } from "../../api/queries";
import type { PortfolioTransaction, PortfolioTransactionCreate } from "../../types/portfolio";
import { errorMessage } from "./portfolioFormatters";
import TransactionPreviewAlert from "./TransactionPreviewAlert";

interface EditTransactionFormValues {
  stock_code: string;
  side: "buy" | "sell";
  trade_price: number;
  trade_time: Dayjs;
  shares: number;
  fee?: number;
  note?: string;
}

interface EditTransactionModalProps {
  transaction: PortfolioTransaction | null;
  onClose: () => void;
}

export default function EditTransactionModal({ transaction, onClose }: EditTransactionModalProps) {
  const [form] = Form.useForm<EditTransactionFormValues>();
  const updateMutation = useUpdatePortfolioTransaction();
  const previewMutation = usePreviewPortfolioTransactionUpdate();
  const resetPreview = previewMutation.reset;
  const side = Form.useWatch("side", form) ?? transaction?.side;

  useEffect(() => {
    if (!transaction) return;
    form.setFieldsValue({
      stock_code: transaction.stock_code,
      side: transaction.side,
      trade_price: transaction.trade_price,
      trade_time: dayjs(transaction.trade_time),
      shares: transaction.shares,
      fee: transaction.fee,
      note: transaction.note,
    });
    resetPreview();
  }, [form, resetPreview, transaction]);

  const buildTransaction = (values: EditTransactionFormValues): PortfolioTransactionCreate => ({
    stock_code: values.stock_code.trim(),
    side: values.side,
    trade_price: values.trade_price,
    trade_time: values.trade_time.format("YYYY-MM-DDTHH:mm:ss"),
    shares: values.shares,
    fee: values.fee ?? 0,
    note: values.note?.trim() ?? "",
  });

  const handlePreview = async () => {
    if (!transaction) return;
    let values: EditTransactionFormValues;
    try {
      values = await form.validateFields();
    } catch {
      return;
    }
    resetPreview();
    try {
      await previewMutation.mutateAsync({
        transactionId: transaction.id,
        transaction: buildTransaction(values),
      });
    } catch (mutationError) {
      message.error(`预演失败：${errorMessage(mutationError)}`);
    }
  };

  const handleSubmit = async (values: EditTransactionFormValues) => {
    if (!transaction) return;
    try {
      await updateMutation.mutateAsync({
        transactionId: transaction.id,
        transaction: buildTransaction(values),
      });
      message.success("交易流水已更新");
      resetPreview();
      onClose();
    } catch (mutationError) {
      message.error(`更新失败：${errorMessage(mutationError)}`);
    }
  };

  return (
    <Modal
      title={transaction ? `编辑交易流水 #${transaction.id}` : "编辑交易流水"}
      open={transaction !== null}
      onCancel={onClose}
      afterClose={() => form.resetFields()}
      destroyOnHidden
      width={720}
      footer={[
        <Button key="cancel" onClick={onClose}>取消</Button>,
        side === "sell" ? (
          <Button key="preview" loading={previewMutation.isPending} onClick={handlePreview}>
            预演修改
          </Button>
        ) : null,
        <Button key="submit" type="primary" loading={updateMutation.isPending} onClick={() => form.submit()}>
          保存修改
        </Button>,
      ]}
    >
      <Form<EditTransactionFormValues>
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        onValuesChange={resetPreview}
        style={{ marginTop: 20 }}
      >
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              name="stock_code"
              label="股票代码"
              rules={[{ required: true, message: "请输入股票代码" }]}
            >
              <Input maxLength={12} placeholder="例如 600519" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item name="side" label="方向" rules={[{ required: true }]}>
              <Radio.Group buttonStyle="solid" style={{ width: "100%" }}>
                <Radio.Button value="buy" style={{ width: "50%", textAlign: "center" }}>买入</Radio.Button>
                <Radio.Button value="sell" style={{ width: "50%", textAlign: "center" }}>卖出</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="trade_price"
              label="成交价"
              rules={[{ required: true, message: "请输入成交价" }]}
            >
              <InputNumber
                min={0.0001}
                max={1_000_000}
                precision={4}
                step={0.01}
                prefix="¥"
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item
              name="shares"
              label="股数"
              rules={[{ required: true, message: "请输入股数" }]}
            >
              <InputNumber min={1} max={1_000_000_000} precision={0} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8}>
            <Form.Item name="fee" label="手续费">
              <InputNumber min={0} max={1_000_000_000} precision={2} prefix="¥" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
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
          <Col xs={24} sm={12}>
            <Form.Item name="note" label="备注">
              <Input maxLength={500} placeholder="记录交易原因或其他说明" />
            </Form.Item>
          </Col>
        </Row>
        {side === "sell" && previewMutation.data ? (
          <TransactionPreviewAlert preview={previewMutation.data} title="修改预演结果" />
        ) : null}
      </Form>
    </Modal>
  );
}
