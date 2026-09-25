import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Button, Form, Input, Result } from "antd";
import { LockOutlined } from "@ant-design/icons";
import { resetPasswordApi } from "../../api/auth";
import AuthHeader from "../../components/AuthHeader";
import AuthShell from "../../components/AuthShell";

/** Public page reached via an admin-issued reset link (/reset-password?token=…). */
export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const onFinish = async (values: { new_password: string }) => {
    setError(null);
    setLoading(true);
    try {
      await resetPasswordApi({ token, new_password: values.new_password });
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重置失败");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuthShell>
        <Result
          status="success"
          title="密码已重置"
          subTitle="请使用新密码登录。"
          extra={
            <Link to="/login">
              <Button type="primary">去登录</Button>
            </Link>
          }
        />
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <AuthHeader title="重置密码" description="设置新的登录密码" icon={<LockOutlined />} />

      {!token && (
        <Alert
          type="warning"
          showIcon
          title="链接无效：缺少重置令牌"
          description="请联系管理员生成一次性重置链接后再继续。"
          style={{ marginBottom: 16 }}
        />
      )}
      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}

      <Form className="auth-form" layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 8, max: 128, message: "密码长度至少 8 位" },
            { pattern: /^(?=.*[A-Za-z])(?=.*\d)/, message: "密码必须同时包含字母和数字" },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} autoComplete="new-password" disabled={!token} />
        </Form.Item>
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
          <Input.Password prefix={<LockOutlined />} autoComplete="new-password" disabled={!token} />
        </Form.Item>
        <Form.Item className="auth-form__submit">
          <Button type="primary" htmlType="submit" block loading={loading} disabled={!token}>
            重置密码
          </Button>
        </Form.Item>
      </Form>

      <div className="auth-footer">
        想起密码了？<Link to="/login">去登录</Link>
      </div>
    </AuthShell>
  );
}
