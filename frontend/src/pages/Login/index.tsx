import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button, Form, Input, Typography, Alert } from "antd";
import { UserOutlined, LockOutlined, LineChartOutlined } from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import { useColors } from "../../styles/ui";
import AuthShell from "../../components/AuthShell";

const { Title, Text } = Typography;

export default function LoginPage() {
  const c = useColors();
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
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 12,
            margin: "0 auto 12px",
            background: c.logoGradient,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <LineChartOutlined style={{ color: "#fff", fontSize: 24 }} />
        </div>
        <Title level={3} style={{ margin: 0, color: c.textPrimary }}>
          登录
        </Title>
        <Text style={{ color: c.textSecondary }}>A股智能分析系统</Text>
      </div>

      {error && (
        <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />
      )}

      <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
        <Form.Item
          name="username"
          label="用户名"
          rules={[{ required: true, message: "请输入用户名" }]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
        </Form.Item>
        <Form.Item
          name="password"
          label="密码"
          rules={[{ required: true, message: "请输入密码" }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="密码" autoComplete="current-password" />
        </Form.Item>
        <Form.Item style={{ marginBottom: 8 }}>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: "center", color: c.textSecondary, fontSize: 13 }}>
        还没有账号？<Link to="/register">去注册</Link>
      </div>
    </AuthShell>
  );
}
