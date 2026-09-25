import type { ReactNode } from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Button, Card, Divider } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { ConfigUpdate } from "../../types/settings";

export interface ConfigCardProps {
  form: ConfigUpdate;
  onChange: (patch: ConfigUpdate) => void;
  onSave: () => void;
  isSaving: boolean;
  stretch?: boolean;
}

interface SettingsCardProps {
  title: string;
  icon: ReactNode;
  saveLabel: string;
  onSave: () => void;
  isSaving: boolean;
  children: ReactNode;
  stretch?: boolean;
}

export function SettingsCard({ title, icon, saveLabel, onSave, isSaving, children, stretch = false }: SettingsCardProps) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card
      title={<span>{icon}{title}</span>}
      style={{
        ...cardStyle,
        marginBottom: 16,
        ...(stretch ? { display: "flex", flexDirection: "column", flex: 1, minWidth: 0 } : {}),
      }}
      styles={{
        body: {
          ...sectionCardBodyStyle,
          ...(stretch ? { display: "flex", flexDirection: "column", flex: 1 } : {}),
        },
      }}
    >
      {stretch ? <div style={{ flex: 1 }}>{children}</div> : children}
      <Divider style={{ borderColor: colors.border, margin: "16px 0" }} />
      <Button
        type="primary"
        icon={<SaveOutlined />}
        onClick={onSave}
        loading={isSaving}
        style={stretch ? { alignSelf: "flex-start" } : undefined}
      >
        {saveLabel}
      </Button>
    </Card>
  );
}
