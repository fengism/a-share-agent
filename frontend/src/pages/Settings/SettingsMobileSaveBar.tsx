import { CheckOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Popconfirm } from "antd";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { CARD_KEYS } from "./cardSpecs";
import "./settings.css";
import type { SettingsCards } from "./useSettingsForm";

interface SettingsMobileSaveBarProps {
  cards: SettingsCards;
  onResetAll: () => void;
}

/**
 * 移动端吸底保存栏。
 *
 * 设置卡片在手机上往往超过一屏，主保存按钮位于卡片底部；
 * 吸底栏把"有多少项未保存 / 保存全部 / 全部撤销"固定在大拇指热区。
 */
export default function SettingsMobileSaveBar({ cards, onResetAll }: SettingsMobileSaveBarProps) {
  const isNarrow = useMediaQuery("(max-width: 767px)");
  const dirtyKeys = CARD_KEYS.filter((key) => Boolean(cards.dirty[key]));

  if (!isNarrow || dirtyKeys.length === 0) return null;

  const saveAll = () => {
    for (const key of dirtyKeys) cards.save(key);
  };

  return (
    <>
      <div className="settings-save-bar-spacer" aria-hidden="true" />
      <div className="settings-save-bar" role="region" aria-label="未保存的配置变更">
        <span className="settings-save-bar__count">{dirtyKeys.length} 项未保存</span>
        <div className="settings-save-bar__actions">
          <Popconfirm
            title={`撤销 ${dirtyKeys.length} 张卡片的修改？`}
            description="将还原为上次保存的配置值，当前未保存的输入将被清空。"
            okText="确认撤销"
            cancelText="继续编辑"
            onConfirm={onResetAll}
          >
            <Button size="middle" icon={<UndoOutlined />} disabled={cards.isSaving}>
              撤销
            </Button>
          </Popconfirm>
          <Button
            type="primary"
            size="middle"
            icon={<CheckOutlined />}
            onClick={saveAll}
            loading={cards.isSaving}
          >
            保存全部
          </Button>
        </div>
      </div>
    </>
  );
}
