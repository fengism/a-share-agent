import { useEffect, useState, type ReactNode } from "react";
import { HistoryOutlined } from "@ant-design/icons";
import { Button, Card, Col, Drawer, Row } from "antd";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStyles } from "../../styles/ui";

interface WorkflowWorkspaceProps {
  children: ReactNode;
  history: ReactNode;
  historyTitle: string;
  historyButtonLabel?: string;
  historyVersion?: string;
}

export default function WorkflowWorkspace({
  children,
  history,
  historyTitle,
  historyButtonLabel = "查看历史",
  historyVersion,
}: WorkflowWorkspaceProps) {
  const { cardStyle } = useStyles();
  const isCompact = useMediaQuery("(max-width: 991px)");
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    setHistoryOpen(false);
  }, [historyVersion]);

  useEffect(() => {
    if (!isCompact) setHistoryOpen(false);
  }, [isCompact]);

  return (
    <>
      {isCompact ? (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
          <Button
            icon={<HistoryOutlined />}
            aria-label={historyButtonLabel}
            onClick={() => setHistoryOpen(true)}
          >
            {historyButtonLabel}
          </Button>
        </div>
      ) : null}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={18} style={{ minWidth: 0 }}>{children}</Col>
        {!isCompact ? (
          <Col lg={6}>
            <div style={{ position: "sticky", top: 24 }}>
              <Card
                title={historyTitle}
                style={cardStyle}
                styles={{ body: { maxHeight: "calc(100vh - 180px)", overflowY: "auto" } }}
              >
                {history}
              </Card>
            </div>
          </Col>
        ) : null}
      </Row>
      <Drawer
        title={historyTitle}
        placement="right"
        open={isCompact && historyOpen}
        onClose={() => setHistoryOpen(false)}
        size="min(420px, 100vw)"
        styles={{ body: { padding: 16 } }}
      >
        {history}
      </Drawer>
    </>
  );
}
