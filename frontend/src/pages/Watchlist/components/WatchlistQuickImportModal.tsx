import React, { useState } from "react";
import { Checkbox, Modal, Tabs, Tag, message } from "antd";
import { ImportOutlined } from "@ant-design/icons";

interface QuickPresetStock {
  code: string;
  name: string;
  industry: string;
  market?: "cn" | "hk";
}

const PRESET_GROUPS: Record<string, { label: string; stocks: QuickPresetStock[] }> = {
  core300: {
    label: "核心资产龙头",
    stocks: [
      { code: "600519", name: "贵州茅台", industry: "白酒" },
      { code: "300750", name: "宁德时代", industry: "新能源" },
      { code: "601318", name: "中国平安", industry: "保险" },
      { code: "600036", name: "招商银行", industry: "银行" },
      { code: "002594", name: "比亚迪", industry: "汽车" },
      { code: "688981", name: "中芯国际", industry: "半导体" },
      { code: "600900", name: "长江电力", industry: "电力" },
      { code: "601899", name: "紫金矿业", industry: "有色" },
      { code: "300308", name: "中际旭创", industry: "算力光模块" },
      { code: "000333", name: "美的集团", industry: "家电" },
    ],
  },
  growth: {
    label: "科技前沿",
    stocks: [
      { code: "002230", name: "科大讯飞", industry: "人工智能" },
      { code: "002475", name: "立讯精密", industry: "消费电子" },
      { code: "688256", name: "寒武纪", industry: "AI算力" },
      { code: "600588", name: "用友网络", industry: "软件服务" },
      { code: "000977", name: "浪潮信息", industry: "服务器" },
      { code: "603501", name: "韦尔股份", industry: "半导体" },
    ],
  },
  dividend: {
    label: "高股息红利",
    stocks: [
      { code: "601088", name: "中国神华", industry: "煤炭" },
      { code: "601225", name: "陕西煤业", industry: "煤炭" },
      { code: "601398", name: "工商银行", industry: "银行" },
      { code: "601288", name: "农业银行", industry: "银行" },
      { code: "600028", name: "中国石化", industry: "石油石化" },
      { code: "601006", name: "大秦铁路", industry: "铁路运输" },
    ],
  },
  hk: {
    label: "港股核心互联",
    stocks: [
      { code: "00700", name: "腾讯控股", industry: "互联网", market: "hk" },
      { code: "03690", name: "美团-W", industry: "本地生活", market: "hk" },
      { code: "09988", name: "阿里巴巴-W", industry: "电商云服务", market: "hk" },
      { code: "01810", name: "小米集团-W", industry: "手机汽车", market: "hk" },
    ],
  },
};

interface WatchlistQuickImportModalProps {
  open: boolean;
  onClose: () => void;
  existingCodes: string[];
  onImport: (stocks: QuickPresetStock[]) => Promise<void>;
}

export const WatchlistQuickImportModal: React.FC<WatchlistQuickImportModalProps> = ({
  open,
  onClose,
  existingCodes,
  onImport,
}) => {
  const [activeTab, setActiveTab] = useState("core300");
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const currentStocks = PRESET_GROUPS[activeTab]?.stocks ?? [];
  const existingSet = new Set(existingCodes);

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const addable = currentStocks.filter((s) => !existingSet.has(s.code)).map((s) => s.code);
      setSelectedCodes((prev) => Array.from(new Set([...prev, ...addable])));
    } else {
      const currentCodeSet = new Set(currentStocks.map((s) => s.code));
      setSelectedCodes((prev) => prev.filter((code) => !currentCodeSet.has(code)));
    }
  };

  const handleToggleCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  const handleConfirmImport = async () => {
    if (!selectedCodes.length) {
      message.warning("请至少选择一只股票");
      return;
    }

    const allPresetStocks = Object.values(PRESET_GROUPS).flatMap((g) => g.stocks);
    const toImport = allPresetStocks.filter((s) => selectedCodes.includes(s.code));

    try {
      setLoading(true);
      await onImport(toImport);
      message.success(`已成功导入 ${toImport.length} 只股票至自选`);
      setSelectedCodes([]);
      onClose();
    } catch {
      message.error("导入自选失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ImportOutlined style={{ color: "var(--c-primary)" }} />
          <span>快速加自选 · 预设主题股票池</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      onOk={handleConfirmImport}
      okText={`一键导入选中 (${selectedCodes.length})`}
      okButtonProps={{ disabled: selectedCodes.length === 0, loading }}
      width={560}
    >
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={Object.entries(PRESET_GROUPS).map(([key, group]) => ({
          key,
          label: group.label,
          children: (
            <div style={{ marginTop: 8 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 10,
                  fontSize: 12,
                }}
              >
                <span style={{ color: "var(--c-text-muted)" }}>
                  共 {group.stocks.length} 只标的，已在自选中的标的自动禁用
                </span>
                <button
                  type="button"
                  onClick={() => handleSelectAll(true)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "var(--c-primary)",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  本组全选
                </button>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "8px 12px",
                  maxHeight: 280,
                  overflowY: "auto",
                  padding: "4px 0",
                }}
              >
                {group.stocks.map((stock) => {
                  const isExisting = existingSet.has(stock.code);
                  const isChecked = selectedCodes.includes(stock.code);

                  return (
                    <div
                      key={stock.code}
                      onClick={() => !isExisting && handleToggleCode(stock.code)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "6px 10px",
                        borderRadius: 6,
                        border: isChecked ? "1px solid var(--c-primary)" : "1px solid var(--c-border)",
                        background: isChecked
                          ? "color-mix(in srgb, var(--c-primary) 8%, transparent)"
                          : "var(--c-card-bg)",
                        opacity: isExisting ? 0.45 : 1,
                        cursor: isExisting ? "not-allowed" : "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <Checkbox checked={isChecked || isExisting} disabled={isExisting} />
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13, color: "var(--c-text-primary)" }}>
                            {stock.name}
                          </div>
                          <div
                            style={{
                              fontSize: 11,
                              fontFamily: "var(--c-font-mono)",
                              color: "var(--c-text-muted)",
                            }}
                          >
                            {stock.code} {stock.market === "hk" && "· 港股"}
                          </div>
                        </div>
                      </div>
                      <Tag style={{ margin: 0, fontSize: 11 }}>{stock.industry}</Tag>
                    </div>
                  );
                })}
              </div>
            </div>
          ),
        }))}
      />
    </Modal>
  );
};
