import { useEffect, useRef, useState } from "react";
import { Alert, Button, Space, Typography } from "antd";
import { CloudUploadOutlined, SearchOutlined } from "@ant-design/icons";
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
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  // 仅在更新触发后轮询（检测新容器版本就绪），平时完全手动检查。
  const pollMs = phase === "updating" ? 5_000 : false;
  const { data: version, refetch, isFetching } = useVersionCheck({ pollMs });
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

  const handleCheck = () => {
    setError(null);
    setLastCheckedAt(Date.now());
    void refetch();
  };

  if (version?.update_available && phase !== "done") {
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

  // 闲置态：纤细的检查更新入口，不自动请求版本接口。
  return (
    <div className="update-banner update-banner-idle">
      <Space size="small" wrap>
        {version && (
          <Text type="secondary" className="update-banner-current">
            当前版本 {version.current_version.slice(0, 7)}
          </Text>
        )}
        <Button
          size="small"
          type="text"
          icon={<SearchOutlined />}
          loading={isFetching}
          onClick={handleCheck}
        >
          检查更新
        </Button>
        {lastCheckedAt !== null && version && !version.update_available && (
          <Text type="secondary" className="update-banner-current">
            已是最新版本
          </Text>
        )}
        {error && <Text type="danger">{error}</Text>}
      </Space>
    </div>
  );
}
