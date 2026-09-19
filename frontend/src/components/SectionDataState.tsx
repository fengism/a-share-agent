import type { ReactNode } from "react";
import { Empty, Skeleton } from "antd";
import QueryErrorState from "./QueryErrorState";

interface SectionDataStateProps {
  children: ReactNode;
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => unknown;
  isEmpty?: boolean;
  emptyText?: ReactNode;
  errorTitle?: string;
  skeletonRows?: number;
  minHeight?: number;
}

export default function SectionDataState({
  children,
  isLoading = false,
  error,
  onRetry,
  isEmpty = false,
  emptyText = "暂无数据",
  errorTitle = "数据加载失败",
  skeletonRows = 4,
  minHeight = 160,
}: SectionDataStateProps) {
  if (isLoading) {
    return (
      <div aria-label="数据加载中" style={{ minHeight, padding: 16 }}>
        <Skeleton active paragraph={{ rows: skeletonRows }} />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight }}>
        <QueryErrorState error={error} onRetry={onRetry} title={errorTitle} compact />
      </div>
    );
  }

  if (isEmpty) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={emptyText}
        style={{
          minHeight,
          padding: "24px 0",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
        }}
      />
    );
  }

  return <>{children}</>;
}
