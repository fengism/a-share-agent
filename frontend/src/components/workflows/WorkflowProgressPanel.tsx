import type { ReactNode } from "react";
import { StopOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, WarningOutlined } from "@ant-design/icons";
import { Card, Spin, Steps, Typography, type StepsProps } from "antd";
import { useStyles } from "../../styles/ui";

const { Text } = Typography;

export type WorkflowProgressStatus = "idle" | "running" | "success" | "warning" | "error" | "cancelled" | "detached";

interface WorkflowProgressPanelProps {
  current: number;
  items: StepsProps["items"];
  status: WorkflowProgressStatus;
  message?: string;
  children?: ReactNode;
}

export default function WorkflowProgressPanel({
  current,
  items,
  status,
  message,
  children,
}: WorkflowProgressPanelProps) {
  const { cardStyle } = useStyles();
  const messageIcon = status === "running"
    ? <Spin size="small" />
    : status === "error"
      ? <CloseCircleOutlined />
      : status === "success"
        ? <CheckCircleOutlined />
        : status === "warning"
          ? <WarningOutlined />
          : <StopOutlined />;

  return (
    <Card size="small" style={{ ...cardStyle, marginBottom: 20 }} styles={{ body: { padding: "20px 24px" } }}>
      <Steps current={current} items={items} size="small" status={status === "error" ? "error" : status === "cancelled" || status === "detached" || status === "idle" ? "wait" : undefined} />
      {message ? (
        <div
          role={status === "error" ? "alert" : "status"}
          aria-live={status === "error" ? "assertive" : "polite"}
          style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}
        >
          {messageIcon}
          <Text type={status === "error" ? "danger" : status === "warning" ? "warning" : "secondary"}>{message}</Text>
        </div>
      ) : null}
      {children}
      {!message && status === "running" && items?.length === 1 ? (
        <div style={{ marginTop: 12 }}><LoadingOutlined spin /> <Text type="secondary">执行中</Text></div>
      ) : null}
    </Card>
  );
}
