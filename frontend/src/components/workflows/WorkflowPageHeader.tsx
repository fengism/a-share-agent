import type { ReactNode } from "react";
import { Typography } from "antd";
import { useStyles } from "../../styles/ui";

const { Paragraph, Title } = Typography;

interface WorkflowPageHeaderProps {
  title: ReactNode;
  description: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
}

export default function WorkflowPageHeader({
  title,
  description,
  icon,
  actions,
}: WorkflowPageHeaderProps) {
  const { pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();

  return (
    <div
      style={{
        ...pageHeaderStyle,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: 16,
        flexWrap: "wrap",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>
            {icon ? <span style={{ marginRight: 8 }}>{icon}</span> : null}
            {title}
          </Title>
        </div>
        <Paragraph style={{ ...pageDescriptionStyle, marginBottom: 0 }}>{description}</Paragraph>
      </div>
      {actions ? <div style={{ maxWidth: "100%" }}>{actions}</div> : null}
    </div>
  );
}
