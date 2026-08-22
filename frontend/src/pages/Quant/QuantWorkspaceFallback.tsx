import { Skeleton } from "antd";

export default function QuantWorkspaceFallback({ label }: { label: string }) {
  return (
    <div className="quant-workspace-fallback" aria-label={label}>
      <Skeleton active paragraph={{ rows: 8 }} />
    </div>
  );
}
