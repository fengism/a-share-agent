import type { ReactNode } from "react";
import { SaveOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Card, Divider, Popconfirm } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { ConfigUpdate } from "../../types/settings";

export interface ConfigCardProps {
  form: ConfigUpdate;
  onChange: (patch: ConfigUpdate) => void;
  onSave: () => void;
  isSaving: boolean;
  stretch?: boolean;
  isDirty?: boolean;
  onReset?: () => void;
}

interface SettingsCardProps {
  title: string;
  icon: ReactNode;
  saveLabel: string;
  onSave: () => void;
  isSaving: boolean;
  children: ReactNode;
  stretch?: boolean;
  isDirty?: boolean;
  onReset?: () => void;
}

export function SettingsCard({
  title,
  icon,
  saveLabel,
  onSave,
  isSaving,
  children,
  stretch = false,
  isDirty = false,
  onReset,
}: SettingsCardProps) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card
      title={
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          {icon}
          <span>{title}</span>
          {isDirty && (
            <span
              style={{
                display: "inline-block",
                width: 7,
                height: 7,
                borderRadius: "50%",
                backgroundColor: "var(--c-warning, #faad14)",
                marginLeft: 4,
              }}
              title="存在未保存的修改"
            />
          )}
        </span>
      }
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
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          onClick={onSave}
          loading={isSaving}
          style={stretch ? { alignSelf: "flex-start" } : undefined}
        >
          {saveLabel}
        </Button>
        {isDirty && onReset && (
          <Popconfirm
            title="撤销此卡片的修改？"
            description="将还原为上次保存的值，当前未保存的输入将被清空。"
            onConfirm={onReset}
            okText="确认撤销"
            cancelText="继续编辑"
          >
            <Button
              size="middle"
              icon={<UndoOutlined />}
              disabled={isSaving}
            >
              撤销更改
            </Button>
          </Popconfirm>
        )}
        {isDirty && (
          <span style={{ fontSize: "var(--c-font-xs, 12px)", color: "var(--c-warning, #faad14)" }}>
            已更改（未保存）
          </span>
        )}
      </div>
    </Card>
  );
}
