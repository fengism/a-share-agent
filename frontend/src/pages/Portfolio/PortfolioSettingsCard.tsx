import { useEffect } from "react";
import { SaveOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Card, Col, Form, InputNumber, Row, Typography, message } from "antd";
import { useUpdatePortfolioSettings } from "../../api/queries";
import { useColors, useStyles } from "../../styles/ui";
import type {
  PortfolioAccountSettings,
  PortfolioAccountSettingsUpdate,
} from "../../types/portfolio";
import { errorMessage } from "./portfolioFormatters";

const { Text } = Typography;

interface PortfolioSettingsCardProps {
  settings: PortfolioAccountSettings;
  isModal?: boolean;
  onSaved?: () => void;
}

export default function PortfolioSettingsCard({ settings, isModal = false, onSaved }: PortfolioSettingsCardProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [form] = Form.useForm<PortfolioAccountSettingsUpdate>();
  const updateMutation = useUpdatePortfolioSettings();

  useEffect(() => {
    form.setFieldsValue({
      initial_cash: settings.initial_cash ?? undefined,
      max_total_position_pct: settings.max_total_position_pct,
      max_single_stock_pct: settings.max_single_stock_pct,
      max_sector_pct: settings.max_sector_pct,
    });
  }, [
    form,
    settings.initial_cash,
    settings.max_total_position_pct,
    settings.max_single_stock_pct,
    settings.max_sector_pct,
  ]);

  const handleSave = async (values: PortfolioAccountSettingsUpdate) => {
    try {
      await updateMutation.mutateAsync({
        ...values,
        initial_cash: values.initial_cash ?? null,
      });
      message.success("仓位设置已保存");
      onSaved?.();
    } catch (mutationError) {
      message.error(`保存失败：${errorMessage(mutationError)}`);
    }
  };

  const formContent = (
    <>
      <Text style={{ color: colors.textMuted, display: "block", marginBottom: 16, fontSize: "var(--c-font-sm, 13px)" }}>
        初始资金用于计算现金、总资产和真实仓位；留空时仅展示证券持仓内部权重。
      </Text>
      <Form<PortfolioAccountSettingsUpdate>
        form={form}
        layout="vertical"
        initialValues={{
          initial_cash: settings.initial_cash ?? undefined,
          max_total_position_pct: settings.max_total_position_pct,
          max_single_stock_pct: settings.max_single_stock_pct,
          max_sector_pct: settings.max_sector_pct,
        }}
        onFinish={handleSave}
      >
        <Row gutter={[16, 0]} align="bottom">
          <Col xs={24} sm={12} lg={isModal ? 12 : 6}>
            <Form.Item name="initial_cash" label="初始资金">
              <InputNumber
                min={0}
                max={1_000_000_000_000}
                precision={2}
                prefix="¥"
                placeholder="留空表示未配置"
                style={{ width: "100%" }}
              />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6} lg={isModal ? 12 : 5}>
            <Form.Item
              name="max_total_position_pct"
              label="总仓位上限"
              rules={[{ required: true, message: "请输入总仓位上限" }]}
            >
              <InputNumber min={0.01} max={100} precision={2} suffix="%" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6} lg={isModal ? 12 : 5}>
            <Form.Item
              name="max_single_stock_pct"
              label="单股仓位上限"
              rules={[{ required: true, message: "请输入单股仓位上限" }]}
            >
              <InputNumber min={0.01} max={100} precision={2} suffix="%" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={12} sm={6} lg={isModal ? 12 : 5}>
            <Form.Item
              name="max_sector_pct"
              label="行业仓位上限"
              rules={[{ required: true, message: "请输入行业仓位上限" }]}
            >
              <InputNumber min={0.01} max={100} precision={2} suffix="%" style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={isModal ? 24 : 6} lg={isModal ? 24 : 3}>
            <Form.Item label={isModal ? undefined : " "} className="portfolio-settings-submit-item">
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                loading={updateMutation.isPending}
                block
                style={isModal ? { marginTop: 8 } : undefined}
              >
                保存设置
              </Button>
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </>
  );

  if (isModal) {
    return <div className="portfolio-settings-modal-content">{formContent}</div>;
  }

  return (
    <Card
      size="small"
      title={<span><SettingOutlined style={{ marginRight: 6 }} />账户与风控设置</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
    >
      {formContent}
    </Card>
  );
}
