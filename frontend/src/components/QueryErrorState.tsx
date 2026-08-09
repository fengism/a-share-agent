import { Alert, Button } from "antd";

interface QueryErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
  compact?: boolean;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "请求失败，请稍后重试";
}

export default function QueryErrorState({
  error,
  onRetry,
  title = "数据加载失败",
  compact = false,
}: QueryErrorStateProps) {
  return (
    <div style={{ padding: compact ? 12 : 24 }}>
      <Alert
        type="error"
        showIcon
        title={title}
        description={getErrorMessage(error)}
        action={onRetry ? (
          <Button size="small" onClick={onRetry}>
            重试
          </Button>
        ) : undefined}
      />
    </div>
  );
}
