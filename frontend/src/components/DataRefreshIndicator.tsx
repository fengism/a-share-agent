import { LoadingOutlined } from "@ant-design/icons";

export default function DataRefreshIndicator({ active, label = "更新中" }: { active: boolean; label?: string }) {
  if (!active) return null;

  return (
    <span className="data-refresh-indicator" role="status" aria-live="polite">
      <LoadingOutlined spin />
      {label}
    </span>
  );
}
