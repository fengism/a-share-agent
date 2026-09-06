import { useEffect, useRef, useState } from "react";
import { Alert, Button, Space, Typography } from "antd";
import { CloudUploadOutlined } from "@ant-design/icons";
import { useAuthStore } from "../store/authStore";
import { useTriggerUpdate, useVersionCheck } from "../api/queryHooks/system";
import "./update-banner.css";

const { Text } = Typography;

type UpdatePhase = "idle" | "updating" | "done";

export default function UpdateBanner() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = Boolean(user?.is_admin);
  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const pollMs = phase === "updating" ? 5_000 : 10 * 60_000;
  const { data: version } = useVersionCheck({ pollMs });
  const trigger = useTriggerUpdate();
  const currentAtTrigger = useRef<string | null>(null);

  // 更新触发后轮询版本号，变化即说明新容器已就绪，刷新页面加载新前端。
  useEffect(() => {
    if (phase !== "updating" || !version) return;
    if (
      currentAtTrigger.current &&
      version.current_version !== currentAtTrigger.current
    ) {
      setPhase("done");
      window.location.reload();
    }
  }, [phase, version]);

  if (!version?.update_available || phase === "done") return null;

  const handleUpdate = () => {
    setError(null);
    currentAtTrigger.current = version.current_version;
    trigger.mutate(undefined, {
      onSuccess: () => setPhase("updating"),
      onError: (e) => setError(e instanceof Error ? e.message : String(e)),
    });
  };

  return (
    <div className="update-banner" role="status">
      <Alert
        type="warning"
        banner
        showIcon
        title={
          <Space size="middle" wrap>
            <span>
              发现新版本{" "}
              <Text code>{version.latest_version?.slice(0, 7)}</Text>
              <span className="update-banner-current">
                （当前 {version.current_version.slice(0, 7)}）
              </span>
            </span>
            {isAdmin ? (
              <Button
                size="small"
                type="primary"
                icon={<CloudUploadOutlined />}
                loading={phase === "updating" || trigger.isPending}
                onClick={handleUpdate}
              >
                {phase === "updating" ? "正在更新…" : "立即更新"}
              </Button>
            ) : (
              <Text type="secondary">请联系管理员更新</Text>
            )}
            {phase === "updating" && (
              <Text type="secondary">
                正在拉取新镜像并重启服务，完成后页面将自动刷新
              </Text>
            )}
            {error && <Text type="danger">{error}</Text>}
          </Space>
        }
      />
    </div>
  );
}
