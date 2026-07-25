import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Button, Form, Input, Typography, Alert, Tag } from "antd";
import { UserOutlined, LockOutlined, KeyOutlined, LineChartOutlined } from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import { needsSetupApi } from "../../api/auth";
import { useColors } from "../../styles/ui";
import AuthShell from "../../components/AuthShell";

const { Title, Text } = Typography;

export default function RegisterPage() {
  const c = useColors();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const register = useAuthStore((s) => s.register);

  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);
  const [checking, setChecking] = useState(true);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Determine whether this is first-time setup (no users yet → first account is
  // admin, no invite needed). On failure, surface a clear error + retry rather
  // than silently assuming "invite required" — that fallback would block a
  // legitimate first-admin registration whenever the check merely hiccups.
  const loadNeedsSetup = useCallback(async () => {
    setChecking(true);
    setSetupError(null);
    try {
      const r = await needsSetupApi();
      setNeedsSetup(r.needs_setup);
    } catch (e) {
      setNeedsSetup(null);
      setSetupError(e instanceof Error ? e.message : "无法确认初始化状态，请稍后重试");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    loadNeedsSetup();
  }, [loadNeedsSetup]);

  if (user) return <Navigate to="/" replace />;

  // needs-setup 无法确定：明确报错 + 重试，绝不静默回退成“需要邀请码”。
  if (setupError) {
    return (
      <AuthShell>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <div
            style={{
              width: 48, height: 48, borderRadius: 12, margin: "0 auto 12px",
              background: c.logoGradient, display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            <LineChartOutlined style={{ color: "#fff", fontSize: 24 }} />
          </div>
          <Title level={3} style={{ margin: 0, color: c.textPrimary }}>注册</Title>
        </div>
        <Alert
          type="error"
          showIcon
          title="无法确认初始化状态"
          description={setupError}
          style={{ marginBottom: 16 }}
        />
        <Button type="primary" block onClick={loadNeedsSetup} loading={checking}>
          重试
        </Button>
        <div style={{ textAlign: "center", color: c.textSecondary, fontSize: 13, marginTop: 16 }}>
          已有账号？<Link to="/login">去登录</Link>
        </div>
      </AuthShell>
    );
  }

  const onFinish = async (values: {
    username: string;
    password: string;
    confirm: string;
    invite_code?: string;
  }) => {
    setError(null);
    setLoading(true);
    try {
      await register(values.username.trim(), values.password, values.invite_code?.trim());
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "注册失败");
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
          注册
        </Title>
        {needsSetup === true ? (
          <Tag color="gold" style={{ marginTop: 8 }}>
            首位注册用户将成为管理员
          </Tag>
        ) : needsSetup === false ? (
          <Text style={{ color: c.textSecondary }}>需要管理员提供的邀请码</Text>
        ) : (
          <Text style={{ color: c.textSecondary }}>正在检测初始化状态…</Text>
        )}
      </div>

      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}

      <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
        <Form.Item
          name="username"
          label="用户名"
          rules={[
            { required: true, message: "请输入用户名" },
            { min: 3, max: 32, message: "用户名长度 3–32" },
          ]}
        >
          <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
        </Form.Item>
        <Form.Item
          name="password"
          label="密码"
          rules={[
            { required: true, message: "请输入密码" },
            { min: 6, max: 128, message: "密码长度 6–128" },
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="密码" autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          name="confirm"
          label="确认密码"
          dependencies={["password"]}
          rules={[
            { required: true, message: "请再次输入密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("password") === value) return Promise.resolve();
                return Promise.reject(new Error("两次输入的密码不一致"));
              },
            }),
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="确认密码" autoComplete="new-password" />
        </Form.Item>

        {needsSetup === false && (
          <Form.Item
            name="invite_code"
            label="邀请码"
            rules={[{ required: true, message: "请输入邀请码" }]}
          >
            <Input prefix={<KeyOutlined />} placeholder="管理员提供的邀请码" />
          </Form.Item>
        )}

        <Form.Item style={{ marginBottom: 8 }}>
          <Button type="primary" htmlType="submit" block loading={loading} disabled={checking || needsSetup === null}>
            {needsSetup ? "创建管理员账号" : "注册"}
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: "center", color: c.textSecondary, fontSize: 13 }}>
        已有账号？<Link to="/login">去登录</Link>
      </div>
    </AuthShell>
  );
}
