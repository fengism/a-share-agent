import { useState } from "react";
import { Button, Card, Col, Form, Input, message, Row } from "antd";
import { LockOutlined, SafetyOutlined } from "@ant-design/icons";
import { changePasswordApi } from "../api/auth";
import { useStyles, useColors } from "../styles/ui";

/** Account-security card: change the login password (verifies the old one and,
 *  on success, the backend revokes the user's other sessions). */
export default function ChangePasswordCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const c = useColors();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: { old_password: string; new_password: string }) => {
    setLoading(true);
    try {
      await changePasswordApi({
        old_password: values.old_password,
        new_password: values.new_password,
      });
      message.success("密码已修改，其它设备的登录已失效");
      form.resetFields();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "修改失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title={<span><SafetyOutlined style={{ marginRight: 8 }} />账号安全</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: c.textMuted, marginBottom: 12 }}>
        修改登录密码。修改成功后，除当前设备外的其它会话将被强制退出。
      </div>
      <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false}>
        <Row gutter={[16, 0]}>
          <Col xs={24} md={8}>
            <Form.Item
              name="old_password"
              label="当前密码"
              rules={[{ required: true, message: "请输入当前密码" }]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="new_password"
              label="新密码"
              rules={[
                { required: true, message: "请输入新密码" },
                { min: 6, max: 128, message: "密码长度 6–128" },
              ]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
            </Form.Item>
          </Col>
          <Col xs={24} md={8}>
            <Form.Item
              name="confirm"
              label="确认新密码"
              dependencies={["new_password"]}
              rules={[
                { required: true, message: "请再次输入新密码" },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue("new_password") === value) return Promise.resolve();
                    return Promise.reject(new Error("两次输入的新密码不一致"));
                  },
                }),
              ]}
            >
              <Input.Password prefix={<LockOutlined />} autoComplete="new-password" />
            </Form.Item>
          </Col>
        </Row>
        <Button type="primary" htmlType="submit" loading={loading}>
          修改密码
        </Button>
      </Form>
    </Card>
  );
}
