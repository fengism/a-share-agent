import { DeleteOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Input, Popconfirm, Select, Space, message } from "antd";
import { useEffect, useState } from "react";
import { useAuthStore } from "../../store/authStore";
import type { ScreenerUrlState } from "../../features/screener/screenerUrlState";
import {
  deleteSavedFilter,
  loadSavedFilters,
  saveFilter,
  type SavedScreenerFilter,
} from "../../features/screener/savedFilters";

interface SavedFilterToolbarProps {
  state: ScreenerUrlState;
  onApply: (state: ScreenerUrlState) => void;
}

export default function SavedFilterToolbar({ state, onApply }: SavedFilterToolbarProps) {
  const userId = useAuthStore((store) => store.user?.id);
  const [name, setName] = useState("");
  const [selectedId, setSelectedId] = useState<string>();
  const [savedFilters, setSavedFilters] = useState<SavedScreenerFilter[]>([]);

  useEffect(() => {
    setSavedFilters(userId == null ? [] : loadSavedFilters(window.localStorage, userId));
    setSelectedId(undefined);
  }, [userId]);

  const handleSave = () => {
    if (userId == null) return;
    const normalizedName = name.trim();
    if (!normalizedName) {
      message.warning("请填写筛选方案名称");
      return;
    }
    const next = saveFilter(window.localStorage, userId, normalizedName, {
      ...state,
      filters: { ...state.filters, page: 1 },
    });
    const saved = next.find((filter) => filter.name === normalizedName);
    setSavedFilters(next);
    setSelectedId(saved?.id);
    setName("");
    message.success("筛选方案已保存");
  };

  const handleSelect = (filterId: string) => {
    setSelectedId(filterId);
    const selected = savedFilters.find((filter) => filter.id === filterId);
    if (selected) onApply(selected.state);
  };

  const handleDelete = () => {
    if (userId == null || !selectedId) return;
    setSavedFilters(deleteSavedFilter(window.localStorage, userId, selectedId));
    setSelectedId(undefined);
    message.success("筛选方案已删除");
  };

  return (
    <Space size={8} wrap style={{ marginBottom: 14 }}>
      <Select
        aria-label="已保存筛选方案"
        value={selectedId}
        onChange={handleSelect}
        options={savedFilters.map((filter) => ({ value: filter.id, label: filter.name }))}
        placeholder="选择已保存方案"
        notFoundContent="暂无已保存方案"
        style={{ width: 180 }}
        allowClear
        onClear={() => setSelectedId(undefined)}
      />
      <Input
        aria-label="筛选方案名称"
        value={name}
        onChange={(event) => setName(event.target.value)}
        onPressEnter={handleSave}
        placeholder="当前条件命名"
        maxLength={30}
        style={{ width: 160 }}
      />
      <Button icon={<SaveOutlined />} onClick={handleSave}>保存条件</Button>
      <Popconfirm
        title="删除这个筛选方案？"
        onConfirm={handleDelete}
        disabled={!selectedId}
        okText="删除"
        cancelText="取消"
      >
        <Button danger icon={<DeleteOutlined />} disabled={!selectedId}>删除方案</Button>
      </Popconfirm>
    </Space>
  );
}
