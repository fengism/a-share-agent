import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, Form, Input } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import AuthHeader from "../../components/AuthHeader";
import AuthShell from "../../components/AuthShell";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const login = useAuthStore((s) => s.login);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from || "/";

  if (user) return <Navigate to={from} replace />;

  const onFinish = async (values: { username: string; password: string }) => {
    setError(null);
    setLoading(true);
    try {
      await login(values.username.trim(), values.password);
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "登录失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell>
      <AuthHeader title="欢迎回来" description="登录智能投研平台，继续你的市场研判" />

      {error && (
        <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />
      )}

      <Form className="auth-form" layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
        <Form.Item
          name="username"
          label="用户名"
          rules={[{ required: true, message: "请输入用户名" }]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" autoFocus />
        </Form.Item>
        <div className="auth-field-label-row">
          <label htmlFor="login-password">密码</label>
          <Link to="/reset-password">忘记密码？</Link>
        </div>
        <Form.Item
          name="password"
          className="auth-form-item--paired"
          rules={[{ required: true, message: "请输入密码" }]}
        >
          <Input.Password
            id="login-password"
            prefix={<LockOutlined />}
            placeholder="密码"
            autoComplete="current-password"
          />
        </Form.Item>
        <Form.Item className="auth-form__submit">
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form.Item>
      </Form>

      <div className="auth-footer">
        还没有账号？<Link to="/register">去注册</Link>
      </div>
    </AuthShell>
  );
}
