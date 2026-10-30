import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import {
  DEFAULT_SETTINGS_SECTION,
  isSettingsSectionKey,
  type SettingsSectionKey,
} from "./settingsSections";

interface SettingsSectionUrlSyncProps {
  section: SettingsSectionKey;
  onChange: (section: SettingsSectionKey) => void;
}

/**
 * 把当前分区同步到 `?section=`，并从 URL 还原分区。
 *
 * 只在 Router 上下文内挂载（由调用方用 `useInRouterContext` 判定），
 * 这样设置页在无 Router 的独立渲染场景下依旧可用。
 */
export default function SettingsSectionUrlSync({ section, onChange }: SettingsSectionUrlSyncProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const restoredRef = useRef(false);

  // 首次挂载：从 URL 还原分区（刷新、分享链接、后退场景）
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const raw = searchParams.get("section");
    if (!isSettingsSectionKey(raw) || raw === section) return;
    onChange(raw);
    // 仅在首次挂载时执行一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 分区变化：写回 URL，默认分区不写入以保持链接干净
  useEffect(() => {
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (section === DEFAULT_SETTINGS_SECTION) next.delete("section");
        else next.set("section", section);
        return next;
      },
      { replace: true },
    );
  }, [section, setSearchParams]);

  return null;
}
