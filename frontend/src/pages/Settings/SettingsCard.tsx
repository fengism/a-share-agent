import type { ReactNode } from "react";
import { SaveOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Card, Divider, Popconfirm } from "antd";
import { useColors, useStyles } from "../../styles/ui";
import type { ConfigUpdate } from "../../types/settings";
import "./settings.css";

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
  /** 危险操作区（重置、删除等），与主保存按钮视觉隔离 */
  dangerZone?: ReactNode;
}

/**
 * 设置页统一卡片外壳。
 *
 * 所有配置卡共用同一套标题栏、状态徽标与底部动作区，避免各卡片各自为政
 * 导致字号、间距与按钮位置不一致。
 */
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
  dangerZone,
}: SettingsCardProps) {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();

  return (
    <Card
      className="settings-card"
      data-dirty={isDirty ? "true" : undefined}
      title={
        <span className="settings-card__head">
          <span className="settings-card__icon">{icon}</span>
          <span className="settings-card__title">{title}</span>
          {isDirty && (
            <span className="settings-card__status" role="status" title="存在未保存的修改">
              未保存
            </span>
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
      <div className="settings-card__footer">
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
          <span className="settings-card__dirty-hint">已更改（未保存）</span>
        )}
      </div>
      {dangerZone && <div className="settings-card__danger">{dangerZone}</div>}
    </Card>
  );
}
