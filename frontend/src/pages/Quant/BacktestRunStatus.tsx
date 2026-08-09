import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Space, Spin } from "antd";
import type { QuantBacktestRun } from "../../api/queries";

interface BacktestRunStatusProps {
  run?: QuantBacktestRun;
  isActionPending?: boolean;
  onCancel: (runId: string) => void;
  onRetry: (runId: string) => void;
}

export default function BacktestRunStatus({
  run,
  isActionPending = false,
  onCancel,
  onRetry,
}: BacktestRunStatusProps) {
  if (run?.status === "pending" || run?.status === "running") {
    return (
      <Alert
        className="quant-run-status"
        type="info"
        showIcon
        title={run.status === "pending" ? "回测正在等待执行" : "正在加载行情并计算回测"}
        description={<Space><Spin size="small" /><span>任务完成后页面会自动刷新。</span></Space>}
        action={(
          <Button aria-label="取消回测" size="small" loading={isActionPending} onClick={() => onCancel(run.id)}>
            取消
          </Button>
        )}
      />
    );
  }

  if (run?.status === "failed") {
    return (
      <Alert
        className="quant-run-status"
        type="error"
        showIcon
        title="回测执行失败"
        description={run.error || "未知错误"}
        action={(
          <Button
            aria-label="重试回测"
            size="small"
            icon={<ReloadOutlined />}
            loading={isActionPending}
            onClick={() => onRetry(run.id)}
          >
            重试
          </Button>
        )}
      />
    );
  }

  return null;
}
