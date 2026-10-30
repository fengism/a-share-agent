import type { ReactNode } from "react";
import "./settings.css";

export interface MobileRecordField<T> {
  label: string;
  render: (item: T) => ReactNode;
  /** 主字段：置于卡片头部，与次要字段分开排版 */
  primary?: boolean;
  /** 占满整行（长文本、操作区） */
  fullWidth?: boolean;
}

interface SettingsMobileRecordListProps<T> {
  items: T[];
  rowKey: (item: T) => string | number;
  fields: MobileRecordField<T>[];
  ariaLabel: string;
  /** 卡片头部右侧附加信息（如状态徽标） */
  trailing?: (item: T) => ReactNode;
  /** 卡片底部操作区 */
  actions?: (item: T) => ReactNode;
}

/**
 * 窄屏记录卡片流。
 *
 * 用户管理、安全审计、登录历史这类宽表在手机上需要横向滚动才能看全，
 * 窄屏改为"主字段 + 键值行 + 操作区"的卡片流，信息与表格一一对应。
 */
export default function SettingsMobileRecordList<T>({
  items,
  rowKey,
  fields,
  ariaLabel,
  trailing,
  actions,
}: SettingsMobileRecordListProps<T>) {
  const primaryFields = fields.filter((field) => field.primary);
  const detailFields = fields.filter((field) => !field.primary);

  return (
    <ul className="settings-record-list" aria-label={ariaLabel}>
      {items.map((item) => (
        <li key={rowKey(item)} className="settings-record-card">
          <div className="settings-record-card__head">
            <div className="settings-record-card__primary">
              {primaryFields.map((field) => (
                <span key={field.label} className="settings-record-card__primary-value">
                  {field.render(item)}
                </span>
              ))}
            </div>
            {trailing ? <div className="settings-record-card__trailing">{trailing(item)}</div> : null}
          </div>

          <dl className="settings-record-card__details">
            {detailFields.map((field) => (
              <div
                key={field.label}
                className={
                  field.fullWidth
                    ? "settings-record-card__row settings-record-card__row--full"
                    : "settings-record-card__row"
                }
              >
                <dt>{field.label}</dt>
                <dd>{field.render(item)}</dd>
              </div>
            ))}
          </dl>

          {actions ? <div className="settings-record-card__actions">{actions(item)}</div> : null}
        </li>
      ))}
    </ul>
  );
}
