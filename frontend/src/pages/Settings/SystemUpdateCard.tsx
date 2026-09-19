import { useEffect, useState } from "react";
import { Alert, Button, Card, Tag, Typography } from "antd";
import {
  CheckCircleOutlined,
  CloudSyncOutlined,
  CloudUploadOutlined,
  ExclamationCircleOutlined,
  SearchOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { useAuthStore } from "../../store/authStore";
import {
  useTriggerUpdate,
  useUpdateStatus,
  useVersionCheck,
} from "../../api/queryHooks/system";
import { useColors, useStyles } from "../../styles/ui";

const { Text } = Typography;

type UpdatePhase = "idle" | "updating" | "failed" | "done";
const UPDATE_TIMEOUT_MS = 10 * 60_000;

function formatVersion(version: string): string {
  return /^[0-9a-f]{8,}$/i.test(version) ? version.slice(0, 7) : version;
}

export default function SystemUpdateCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const c = useColors();
  const user = useAuthStore((s) => s.user);
  const isAdmin = Boolean(user?.is_admin);

  const [phase, setPhase] = useState<UpdatePhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);

  const pollMs = phase === "updating" ? 5_000 : false;
  const { data: version, refetch, isFetching } = useVersionCheck({ pollMs: false });
  const { data: updateStatus } = useUpdateStatus({
    enabled: phase === "updating",
    pollMs,
  });
  const trigger = useTriggerUpdate();
  const isDevelopmentVersion = version?.current_version === "dev";

  // updater 确认两个服务健康后刷新页面
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
    try {
      const result = await refetch();
      if (result.error) throw result.error;
      const now = new Date();
      setLastCheckedAt(`${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`);
    } catch (checkError) {
      const messageText = checkError instanceof Error ? checkError.message : String(checkError);
      setError(`检查更新失败：${messageText}`);
    }
  };

  const handleUpdate = () => {
    setError(null);
    trigger.mutate(undefined, {
      onSuccess: () => setPhase("updating"),
      onError: (e) => setError(e instanceof Error ? e.message : String(e)),
    });
  };

  return (
    <Card
      title={<span><CloudSyncOutlined style={{ marginRight: 8 }} />系统版本与更新</span>}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: "var(--c-font-sm)", color: c.textMuted, marginBottom: 16 }}>
        查看当前系统运行版本，并在发布新版本时在线升级镜像与服务。
      </div>

      <div style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
          <Text strong>当前版本：</Text>
          {version && (!isDevelopmentVersion || isAdmin) ? (
            <Tag color={isDevelopmentVersion ? "orange" : "blue"} style={{ fontFamily: "var(--c-font-mono)", fontSize: "var(--c-font-sm)" }}>
              {isDevelopmentVersion ? "开发环境 (dev)" : formatVersion(version.current_version)}
            </Tag>
          ) : (
            <Text type="secondary">{version ? "已连接" : "点击「检查更新」获取"}</Text>
          )}

          <Button
            icon={<SearchOutlined />}
            loading={isFetching}
            onClick={() => void handleCheck()}
          >
            检查更新
          </Button>

          {lastCheckedAt && (
            <Text type="secondary" style={{ fontSize: "var(--c-font-xs)" }}>
              上次检查于 {lastCheckedAt}
            </Text>
          )}
        </div>

        {version && !version.update_available && lastCheckedAt && (
          <Alert
            type="success"
            showIcon
            icon={<CheckCircleOutlined />}
            message={isDevelopmentVersion ? "开发环境不支持在线更新" : "当前已是最新版本，无需更新。"}
          />
        )}

        {version?.update_available && phase !== "done" && (
          <Alert
            type="warning"
            showIcon
            icon={<ExclamationCircleOutlined />}
            message={
              <div style={{ display: "grid", gap: 8 }}>
                <div>
                  <strong>发现新版本：</strong>
                  <Text code style={{ marginInline: 6 }}>
                    {version.latest_version ? formatVersion(version.latest_version) : "最新版"}
                  </Text>
                  <span>（当前版本：{formatVersion(version.current_version)}）</span>
                </div>
                {isAdmin ? (
                  <div>
                    <Button
                      type="primary"
                      icon={<CloudUploadOutlined />}
                      loading={phase === "updating" || trigger.isPending}
                      onClick={handleUpdate}
                    >
                      {phase === "updating" ? "正在更新镜像并重启服务…" : "立即在线更新"}
                    </Button>
                    <Text type="secondary" style={{ display: "block", marginTop: 6, fontSize: "var(--c-font-xs)" }}>
                      更新将自动拉取新容器镜像并重启，服务就绪后页面将自动刷新；若失败将自动尝试回滚旧版本。
                    </Text>
                  </div>
                ) : (
                  <Text type="secondary">当前账号为非管理员，如需更新请联系系统管理员操作。</Text>
                )}
              </div>
            }
          />
        )}

        {phase === "updating" && (
          <Alert
            type="info"
            showIcon
            icon={<SyncOutlined spin />}
            message="正在执行系统更新，拉取新容器镜像并重新编排服务，请耐心等待（完成后将自动刷新页面）..."
          />
        )}

        {error && (
          <Alert
            type="error"
            showIcon
            closable
            onClose={() => setError(null)}
            message={error}
          />
        )}
      </div>
    </Card>
  );
}
