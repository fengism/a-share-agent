import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Alert, Button, Form, Input } from "antd";
import { LockOutlined, SafetyOutlined } from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import { changePasswordApi } from "../../api/auth";
import AuthHeader from "../../components/AuthHeader";
import AuthShell from "../../components/AuthShell";

/** Full-screen forced password change shown on first login for a seeded admin
 *  (or any account flagged must_change_password). The app is unreachable until
 *  a new password is set. */
export default function ForceChangePasswordPage() {
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
      <AuthHeader
        title="请修改初始密码"
        description={`${user.username}，首次登录需设置新密码后才能继续`}
        icon={<SafetyOutlined />}
      />

      {error && <Alert type="error" showIcon title={error} style={{ marginBottom: 16 }} />}

      <Form className="auth-form" layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
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
            { min: 8, max: 128, message: "密码长度至少 8 位" },
            { pattern: /^(?=.*[A-Za-z])(?=.*\d)/, message: "密码必须同时包含字母和数字" },
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
        <Form.Item className="auth-form__submit">
          <Button type="primary" htmlType="submit" block loading={loading}>
            修改并继续
          </Button>
        </Form.Item>
      </Form>

      <div className="auth-footer">
        <Button type="link" onClick={handleLogout}>
          退出登录
        </Button>
      </div>
    </AuthShell>
  );
}
