import { useEffect, useRef, useState } from "react";
import { Alert } from "antd";
import { WifiOutlined, DisconnectOutlined } from "@ant-design/icons";
import { queryClient } from "../api/queryClient";

export interface NetworkStatusBannerProps {
  /** 仅在测试中注入初始状态，默认从 navigator.onLine 获取 */
  initialOnline?: boolean;
  /** 恢复联网后提示保留时间，单位毫秒，默认 3000ms */
  recoveredDisplayMs?: number;
  /** 联网恢复时的自定义回调，默认刷新所有 query */
  onReconnect?: () => void;
}

export default function NetworkStatusBanner({
  initialOnline,
  recoveredDisplayMs = 3000,
  onReconnect,
}: NetworkStatusBannerProps = {}) {
  const [isOnline, setIsOnline] = useState<boolean>(() => {
    if (initialOnline !== undefined) return initialOnline;
    return typeof navigator !== "undefined" && typeof navigator.onLine === "boolean"
      ? navigator.onLine
      : true;
  });
  const [showRestored, setShowRestored] = useState<boolean>(false);
  const hideTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      setShowRestored(true);

      if (onReconnect) {
        onReconnect();
      } else {
        void queryClient.invalidateQueries();
      }

      if (hideTimerRef.current !== null) {
        window.clearTimeout(hideTimerRef.current);
      }
      hideTimerRef.current = window.setTimeout(() => {
        setShowRestored(false);
        hideTimerRef.current = null;
      }, recoveredDisplayMs);
    };

    const handleOffline = () => {
      if (hideTimerRef.current !== null) {
        window.clearTimeout(hideTimerRef.current);
        hideTimerRef.current = null;
      }
      setShowRestored(false);
      setIsOnline(false);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (hideTimerRef.current !== null) {
        window.clearTimeout(hideTimerRef.current);
      }
    };
  }, [onReconnect, recoveredDisplayMs]);

  if (isOnline && !showRestored) {
    return null;
  }

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        width: "100%",
        zIndex: 1000,
      }}
    >
      {!isOnline ? (
        <Alert
          type="error"
          showIcon
          icon={<DisconnectOutlined />}
          title="网络连接已断开，数据已暂停自动刷新，请检查网络连接"
          banner
        />
      ) : (
        <Alert
          type="success"
          showIcon
          icon={<WifiOutlined />}
          title="网络已恢复连接，正在自动同步最新行情数据"
          banner
        />
      )}
    </div>
  );
}
