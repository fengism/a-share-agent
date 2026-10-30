import { useMemo, useState } from "react";
import { CheckOutlined, UndoOutlined } from "@ant-design/icons";
import { Badge, Button, Popconfirm, Popover } from "antd";
import { CARD_KEYS, type CardKey } from "./cardSpecs";
import { SETTINGS_CARD_LOCATIONS, SETTINGS_SECTION_LABELS } from "./settingsCardLocations";
import type { SettingsSectionKey } from "./settingsSections";
import type { SettingsCards } from "./useSettingsForm";

interface SettingsDirtySummaryProps {
  cards: SettingsCards;
  /** 跳转到某张卡片所在的分区（并滚动到对应分组） */
  onJumpToCard: (section: SettingsSectionKey, anchorId?: string) => void;
}

/**
 * 未保存变更汇总面板。
 *
 * 顶部只提示"有未保存变更"时，用户无法知道是哪几张卡；这里列出具体卡片，
 * 并提供"保存全部 / 全部撤销"，复用既有的按卡保存与还原逻辑。
 */
export default function SettingsDirtySummary({ cards, onJumpToCard }: SettingsDirtySummaryProps) {
  const [open, setOpen] = useState(false);

  const dirtyKeys = useMemo(
    () => CARD_KEYS.filter((key) => Boolean(cards.dirty[key])),
    [cards.dirty],
  );

  if (dirtyKeys.length === 0) return null;

  const saveAll = () => {
    for (const key of dirtyKeys) cards.save(key);
    setOpen(false);
  };

  const resetAll = () => {
    for (const key of dirtyKeys) cards.reset(key);
    setOpen(false);
  };

  const content = (
    <div className="settings-dirty-panel" data-testid="settings-dirty-panel">
      <p className="settings-dirty-panel__hint">
        以下 {dirtyKeys.length} 张配置卡片存在未保存的修改，点击可跳转到对应位置。
      </p>
      <ul className="settings-dirty-panel__list">
        {dirtyKeys.map((key: CardKey) => {
          const location = SETTINGS_CARD_LOCATIONS[key];
          return (
            <li key={key}>
              <button
                type="button"
                className="settings-dirty-panel__item"
                onClick={() => {
                  setOpen(false);
                  onJumpToCard(location.section, location.anchorId);
                }}
              >
                <span className="settings-dirty-panel__item-label">{location.label}</span>
                <span className="settings-dirty-panel__item-section">
                  {SETTINGS_SECTION_LABELS[location.section]}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="settings-dirty-panel__actions">
        <Button type="primary" size="small" icon={<CheckOutlined />} onClick={saveAll} loading={cards.isSaving}>
          保存全部
        </Button>
        <Popconfirm
          title={`撤销 ${dirtyKeys.length} 张卡片的修改？`}
          description="将还原为上次保存的配置值，当前未保存的输入将被清空。"
          okText="确认撤销"
          cancelText="继续编辑"
          onConfirm={resetAll}
        >
          <Button size="small" icon={<UndoOutlined />} disabled={cards.isSaving}>
            全部撤销
          </Button>
        </Popconfirm>
      </div>
    </div>
  );

  return (
    <Popover
      content={content}
      title="未保存的配置变更"
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="bottomRight"
    >
      <Badge count={dirtyKeys.length} size="small" offset={[-2, 2]}>
        <Button size="small" className="settings-dirty-trigger">
          未保存变更
        </Button>
      </Badge>
    </Popover>
  );
}
