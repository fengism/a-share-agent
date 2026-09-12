import { useEffect, useState } from "react";
import { Alert, Button, Space, Typography } from "antd";
import { CloudUploadOutlined, SearchOutlined } from "@ant-design/icons";
import { useAuthStore } from "../store/authStore";
import {
  useTriggerUpdate,
  useUpdateStatus,
  useVersionCheck,
} from "../api/queryHooks/system";
import "./update-banner.css";

const { Text } = Typography;

type UpdatePhase = "idle" | "updating" | "failed" | "done";

const UPDATE_TIMEOUT_MS = 10 * 60_000;

function formatVersion(version: string): string {
  return /^[0-9a-f]{8,}$/i.test(version) ? version.slice(0, 7) : version;
}

export default function UpdateBanner() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = Boolean(user?.is_admin);
  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<number | null>(null);
  // 仅在更新触发后轮询 updater 状态，版本检查保持手动触发。
  const pollMs = phase === "updating" ? 5_000 : false;
  const { data: version, refetch, isFetching } = useVersionCheck();
  const { data: updateStatus } = useUpdateStatus({
    enabled: phase === "updating",
    pollMs,
  });
  const trigger = useTriggerUpdate();
  const isDevelopmentVersion = version?.current_version === "dev";

  // updater 确认两个服务健康后刷新页面。
  useEffect(() => {
    if (phase !== "updating") return;
    if (updateStatus?.status === "failed") {
      setError(updateStatus.message || "更新失败，请检查 updater 日志后重试");
      setPhase("failed");
      return;
    }
    if (updateStatus?.status === "failed_rolled_back") {
      setError(updateStatus.message || "更新失败，已自动恢复旧版本");
      setPhase("failed");
      return;
    }
    if (updateStatus?.status === "failed_rollback_failed") {
      setError(updateStatus.message || "更新及自动回滚均失败，请立即人工恢复");
      setPhase("failed");
      return;
    }
    if (updateStatus?.status === "succeeded") {
      setPhase("done");
      window.location.reload();
    }
  }, [phase, updateStatus]);

  useEffect(() => {
    if (phase !== "updating") return undefined;
    const timeout = window.setTimeout(() => {
      setError("更新等待超时，请检查 updater 日志后重试");
      setPhase("failed");
    }, UPDATE_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [phase]);

  const handleCheck = async () => {
    setError(null);
    setLastCheckedAt(null);
    try {
      const result = await refetch();
      if (result.error) throw result.error;
      setLastCheckedAt(Date.now());
    } catch (checkError) {
      const message = checkError instanceof Error ? checkError.message : String(checkError);
      setError(`检查更新失败：${message}`);
    }
  };

  if (version?.update_available && phase !== "done") {
    const handleUpdate = () => {
      setError(null);
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
                <Text code>{version.latest_version ? formatVersion(version.latest_version) : null}</Text>
                <span className="update-banner-current">
                  （当前 {formatVersion(version.current_version)}）
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
        {version && (!isDevelopmentVersion || isAdmin) && (
          <Text type="secondary" className="update-banner-current">
            {isDevelopmentVersion ? "开发环境" : `当前版本 ${formatVersion(version.current_version)}`}
          </Text>
        )}
        <Button
          size="small"
          type="text"
          icon={<SearchOutlined />}
          loading={isFetching}
          onClick={() => void handleCheck()}
        >
          检查更新
        </Button>
        {lastCheckedAt !== null && version && !version.update_available && (
          <Text type="secondary" className="update-banner-current">
            {isDevelopmentVersion
              ? (isAdmin ? "开发环境不支持在线更新" : "版本信息不可用")
              : "已是最新版本"}
          </Text>
        )}
        {error && <Text type="danger">{error}</Text>}
      </Space>
    </div>
  );
}
