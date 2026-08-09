import { useState } from "react";
import { Card, Form, Input, Button, Select, message, Typography } from "antd";
import { KeyOutlined, CopyOutlined } from "@ant-design/icons";
import { adminResetLinkApi } from "../api/auth";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { useStyles, useColors } from "../styles/ui";

const { Text } = Typography;

/** Admin-only: generate a one-time password-reset link for a user (no email). */
export default function AdminResetCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ url: string; username: string; expires_at: string } | null>(null);

  const onFinish = async (values: { username: string; expires_in_hours: number }) => {
    setLoading(true);
    try {
      const r = await adminResetLinkApi({
        username: values.username.trim(),
        expires_in_hours: values.expires_in_hours,
      });
      const url = `${window.location.origin}/reset-password?token=${encodeURIComponent(r.token)}`;
      setResult({ url, username: r.username, expires_at: r.expires_at });
    } catch (e) {
      message.error(e instanceof Error ? e.message : "生成失败");
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.url);
      message.success("链接已复制");
    } catch {
      message.warning("复制失败，请手动选择复制");
    }
  };

  return (
    <Card
      title={<span><KeyOutlined style={{ marginRight: 8 }} />用户密码重置</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: 12, color: c.textMuted, marginBottom: 12 }}>
        为忘记密码的用户生成一次性重置链接（不经邮件）。链接仅显示一次，请复制后线下发给该用户；用户打开后自行设置新密码，其现有会话会全部失效。
      </div>
      <Form
        form={form}
        layout={isNarrow ? "vertical" : "inline"}
        onFinish={onFinish}
        initialValues={{ expires_in_hours: 24 }}
        style={{ rowGap: 8, flexWrap: "wrap" }}
      >
        <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
          <Input placeholder="用户名" style={{ width: isNarrow ? "100%" : 180 }} />
        </Form.Item>
        <Form.Item name="expires_in_hours">
          <Select
            style={{ width: isNarrow ? "100%" : 140 }}
            options={[
              { value: 1, label: "1 小时后过期" },
              { value: 24, label: "24 小时后过期" },
              { value: 72, label: "3 天后过期" },
              { value: 168, label: "7 天后过期" },
            ]}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block={isNarrow}>
            生成重置链接
          </Button>
        </Form.Item>
      </Form>

      {result && (
        <div
          style={{
            marginTop: 12, padding: "10px 12px", background: c.elevatedBg,
            border: `1px solid ${c.border}`, borderRadius: 8,
          }}
        >
          <div style={{ fontSize: 12, color: c.textSecondary, marginBottom: 6 }}>
            已为 <Text strong>{result.username}</Text> 生成链接（{result.expires_at} 前有效），仅显示一次：
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: isNarrow ? "stretch" : "center", flexDirection: isNarrow ? "column" : "row" }}>
            <code style={{ flex: 1, fontFamily: "monospace", fontSize: 12, color: c.textPrimary, wordBreak: "break-all" }}>
              {result.url}
            </code>
            <Button size="small" icon={<CopyOutlined />} onClick={copy} style={{ alignSelf: isNarrow ? "flex-end" : undefined }}>复制</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
