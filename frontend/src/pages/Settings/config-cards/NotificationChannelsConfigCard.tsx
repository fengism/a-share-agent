import { useState } from "react";
import {
  BellOutlined,
  CheckCircleOutlined,
  ClearOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  SendOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Divider,
  Input,
  Popconfirm,
  Row,
  Space,
  Switch,
  Tag,
  Typography,
  message as antMessage,
} from "antd";
import {
  type NotificationChannelDetail,
  type NotificationHistoryItem,
  type TestWebhookRequest,
  type TestWebhookResponse,
  useClearNotificationHistory,
  useNotificationHistory,
  useTestWebhookNotification,
} from "../../../api/queryHooks/push";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

const { Text } = Typography;

export default function NotificationChannelsConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  stretch,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const testMutation = useTestWebhookNotification();
  const clearHistoryMutation = useClearNotificationHistory();
  const { data: historyItems, refetch: refetchHistory } = useNotificationHistory(15);
  const [testingChannel, setTestingChannel] = useState<string | null>(null);

  const handleTest = async (channel: "feishu" | "dingtalk" | "wecom" | "wxpusher") => {
    setTestingChannel(channel);
    try {
      let req: TestWebhookRequest = { channel };
      if (channel === "feishu") {
        req = {
          channel,
          webhook_url: form.feishu_webhook_url,
          secret: form.feishu_webhook_secret,
        };
      } else if (channel === "dingtalk") {
        req = {
          channel,
          webhook_url: form.dingtalk_webhook_url,
          secret: form.dingtalk_webhook_secret,
        };
      } else if (channel === "wecom") {
        req = { channel, webhook_url: form.wecom_webhook_url };
      } else if (channel === "wxpusher") {
        req = {
          channel,
          webhook_url: form.wxpusher_app_token,
          uids: form.wxpusher_uids,
        };
      }

      const res = (await testMutation.mutateAsync(req)) as TestWebhookResponse;
      if (res.success) {
        antMessage.success(`${channel} 测试成功：${res.message}`);
      } else {
        antMessage.error(`${channel} 测试失败：${res.message}`);
      }
      refetchHistory();
    } catch (err: unknown) {
      antMessage.error(`网络测试异常: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setTestingChannel(null);
    }
  };

  const handleClearHistory = async () => {
    try {
      await clearHistoryMutation.mutateAsync();
      antMessage.success("推送审计历史记录已清空");
      refetchHistory();
    } catch (err: unknown) {
      antMessage.error(`清空失败: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  return (
    <SettingsCard
      title="自动推送与通知通道"
      icon={<BellOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存通知配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <Alert
            type="info"
            showIcon
            message="交易日自动化收盘推送"
            description="交易日 15:30 收盘后，系统可自动将 AI 每日深度复盘报告与全市场题材潜力雷达并发投递到您配置的飞书、钉钉、企微群或个人微信。"
            style={{ marginBottom: 8 }}
          />
        </Col>

        {/* 自动化总开关与业务项 */}
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>启用自动定时推送</div>
          <Switch
            checked={form.push_auto_enabled ?? false}
            onChange={(value) => onChange({ push_auto_enabled: value })}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>自动推送每日收盘复盘</div>
          <Switch
            disabled={!form.push_auto_enabled}
            checked={form.push_daily_review_auto ?? true}
            onChange={(value) => onChange({ push_daily_review_auto: value })}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>自动推送题材与潜力雷达</div>
          <Switch
            disabled={!form.push_auto_enabled}
            checked={form.push_potential_auto ?? true}
            onChange={(value) => onChange({ push_potential_auto: value })}
          />
        </Col>

        <Col span={24}>
          <Divider style={{ margin: "8px 0" }} />
        </Col>

        {/* 1. 飞书自定义群机器人 */}
        <Col span={24}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Space>
              <Text strong>🐦 飞书群自定义机器人 (Interactive Card)</Text>
              <Switch
                size="small"
                checkedChildren="开启"
                unCheckedChildren="暂停"
                checked={form.push_feishu_enabled ?? true}
                onChange={(value) => onChange({ push_feishu_enabled: value })}
              />
            </Space>
            <Button
              size="small"
              icon={<SendOutlined />}
              loading={testingChannel === "feishu"}
              onClick={() => handleTest("feishu")}
            >
              测试连通性
            </Button>
          </div>
        </Col>
        <Col span={24} sm={14}>
          <div style={fieldLabelStyle}>飞书 Webhook 地址</div>
          <Input
            value={form.feishu_webhook_url || ""}
            onChange={(e) => onChange({ feishu_webhook_url: e.target.value })}
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
          />
        </Col>
        <Col span={24} sm={10}>
          <div style={fieldLabelStyle}>安全签名 Secret（可选）</div>
          <Input.Password
            value={form.feishu_webhook_secret || ""}
            onChange={(e) => onChange({ feishu_webhook_secret: e.target.value })}
            placeholder="若群机器人开启了签名校验请填写"
          />
        </Col>

        <Col span={24}>
          <Divider style={{ margin: "8px 0" }} />
        </Col>

        {/* 2. 钉钉群自定义机器人 */}
        <Col span={24}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Space>
              <Text strong>🔔 钉钉群自定义机器人 (Markdown)</Text>
              <Switch
                size="small"
                checkedChildren="开启"
                unCheckedChildren="暂停"
                checked={form.push_dingtalk_enabled ?? true}
                onChange={(value) => onChange({ push_dingtalk_enabled: value })}
              />
            </Space>
            <Button
              size="small"
              icon={<SendOutlined />}
              loading={testingChannel === "dingtalk"}
              onClick={() => handleTest("dingtalk")}
            >
              测试连通性
            </Button>
          </div>
        </Col>
        <Col span={24} sm={14}>
          <div style={fieldLabelStyle}>钉钉 Webhook 地址</div>
          <Input
            value={form.dingtalk_webhook_url || ""}
            onChange={(e) => onChange({ dingtalk_webhook_url: e.target.value })}
            placeholder="https://oapi.dingtalk.com/robot/send?access_token=..."
          />
        </Col>
        <Col span={24} sm={10}>
          <div style={fieldLabelStyle}>安全签名 Secret（可选）</div>
          <Input.Password
            value={form.dingtalk_webhook_secret || ""}
            onChange={(e) => onChange({ dingtalk_webhook_secret: e.target.value })}
            placeholder="SEC 开头的加签密钥（若开启加签）"
          />
        </Col>

        <Col span={24}>
          <Divider style={{ margin: "8px 0" }} />
        </Col>

        {/* 3. 企业微信群机器人 */}
        <Col span={24}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Space>
              <Text strong>💬 企业微信群机器人 (Markdown)</Text>
              <Switch
                size="small"
                checkedChildren="开启"
                unCheckedChildren="暂停"
                checked={form.push_wecom_enabled ?? true}
                onChange={(value) => onChange({ push_wecom_enabled: value })}
              />
            </Space>
            <Button
              size="small"
              icon={<SendOutlined />}
              loading={testingChannel === "wecom"}
              onClick={() => handleTest("wecom")}
            >
              测试连通性
            </Button>
          </div>
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>企业微信 Webhook 地址</div>
          <Input
            value={form.wecom_webhook_url || ""}
            onChange={(e) => onChange({ wecom_webhook_url: e.target.value })}
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
          />
        </Col>

        <Col span={24}>
          <Divider style={{ margin: "8px 0" }} />
        </Col>

        {/* 4. 微信个人服务号 (WxPusher) */}
        <Col span={24}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Space>
              <Text strong>📲 微信服务号直达 (WxPusher)</Text>
              <Switch
                size="small"
                checkedChildren="开启"
                unCheckedChildren="暂停"
                checked={form.push_wxpusher_enabled ?? true}
                onChange={(value) => onChange({ push_wxpusher_enabled: value })}
              />
            </Space>
            <Button
              size="small"
              icon={<SendOutlined />}
              loading={testingChannel === "wxpusher"}
              onClick={() => handleTest("wxpusher")}
            >
              测试连通性
            </Button>
          </div>
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>WxPusher App Token</div>
          <Input.Password
            value={form.wxpusher_app_token || ""}
            onChange={(e) => onChange({ wxpusher_app_token: e.target.value })}
            placeholder="AT_xxx"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>接收人 UID 列表（逗号分隔）</div>
          <Input
            value={form.wxpusher_uids || ""}
            onChange={(e) => onChange({ wxpusher_uids: e.target.value })}
            placeholder="UID_xxx, UID_yyy"
          />
        </Col>

        {/* 5. 最近投递记录折叠面板 */}
        {historyItems && historyItems.length > 0 && (
          <Col span={24}>
            <Collapse
              ghost
              items={[
                {
                  key: "history",
                  label: (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", paddingRight: 8 }}>
                      <Space>
                        <HistoryOutlined />
                        <span>查看最近通知投递审计记录 ({historyItems.length})</span>
                      </Space>
                      <Popconfirm
                        title="确定清空投递审计历史吗？"
                        okText="清空"
                        cancelText="取消"
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          handleClearHistory();
                        }}
                      >
                        <Button
                          size="small"
                          type="text"
                          danger
                          icon={<ClearOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        >
                          清空历史
                        </Button>
                      </Popconfirm>
                    </div>
                  ),
                  children: (
                    <div style={{ maxHeight: 240, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
                      {historyItems.map((item: NotificationHistoryItem) => (
                        <Card size="small" key={item.id} style={{ background: "rgba(0,0,0,0.02)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <Space>
                              <Text strong>{item.title}</Text>
                              <Tag color={item.severity === "warning" ? "orange" : item.severity === "alert" ? "red" : "blue"}>
                                {item.category}
                              </Tag>
                            </Space>
                            <Space style={{ fontSize: 12, color: "gray" }}>
                              <ClockCircleOutlined />
                              <span>{item.timestamp}</span>
                            </Space>
                          </div>
                          <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
                            {Object.entries(item.channels).map(([ch, info]: [string, NotificationChannelDetail]) => (
                              <Tag
                                key={ch}
                                icon={info.success ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                                color={info.success ? "success" : "error"}
                              >
                                {info.name || ch}: {info.success ? `${info.elapsed_ms}ms` : info.message}
                              </Tag>
                            ))}
                          </div>
                        </Card>
                      ))}
                    </div>
                  ),
                },
              ]}
            />
          </Col>
        )}
      </Row>
    </SettingsCard>
  );
}
