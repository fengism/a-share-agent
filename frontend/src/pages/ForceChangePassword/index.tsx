import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Button, Form, Input, Typography, Alert } from "antd";
import { LockOutlined, SafetyOutlined } from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import { changePasswordApi } from "../../api/auth";
import { useColors } from "../../styles/ui";
import AuthShell from "../../components/AuthShell";

const { Title, Text } = Typography;

/** Full-screen forced password change shown on first login for a seeded admin
 *  (or any account flagged must_change_password). The app is unreachable until
 *  a new password is set. */
export default function ForceChangePasswordPage() {
  const c = useColors();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const refreshUser = useAuthStore((s) => s.refreshUser);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return <Navigate to="/login" replace />;
  if (!user.must_change_password) return <Navigate to="/" replace />;

  const onFinish = async (values: { old_password: string; new_password: string }) => {
    setError(null);
    setLoading(true);
    try {
      await changePasswordApi({ old_password: values.old_password, new_password: values.new_password });
      await refreshUser(); // must_change_password is now false
      navigate("/", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "修改失败");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  return (
    <AuthShell>
      <div style={{ textAlign: "center", marginBottom: 24 }}>
        <div
          style={{
            width: 48, height: 48, borderRadius: 12, margin: "0 auto 12px",
            background: c.logoGradient, display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <SafetyOutlined style={{ color: "#fff", fontSize: 24 }} />
        </div>
        <Title level={3} style={{ margin: 0, color: c.textPrimary }}>请修改初始密码</Title>
        <Text style={{ color: c.textSecondary }}>
          {user.username}，首次登录需设置新密码后才能继续
        </Text>
      </div>

      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}

      <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
        <Form.Item
          name="old_password"
          label="当前密码（临时密码）"
          rules={[{ required: true, message: "请输入当前密码" }]}
        >
          <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
        </Form.Item>
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
        <Form.Item style={{ marginBottom: 8 }}>
          <Button type="primary" htmlType="submit" block loading={loading}>
            修改并继续
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: "center" }}>
        <Button type="link" onClick={handleLogout} style={{ color: c.textSecondary, fontSize: 13 }}>
          退出登录
        </Button>
      </div>
    </AuthShell>
  );
}
