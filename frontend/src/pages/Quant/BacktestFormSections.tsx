import {
  DeleteOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SaveOutlined,
  SearchOutlined,
  SettingOutlined,
  StarOutlined,
} from "@ant-design/icons";
import {
  AutoComplete,
  Button,
  Col,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { useWatchlist } from "../../api/queries";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import {
  getStockName,
  parseStockCodes,
  registerStockInfo,
  resolveStockNameOrCode,
  splitInputSearch,
  stockCodesValidationError,
  strategyConstraintDependencies,
  strategyConstraintValidationError,
  type QuantFormValues,
  type StrategyOption,
} from "./quantForm";
import StrategyPresetPicker from "./StrategyPresetPicker";

const { Text } = Typography;

interface SavedStrategyToolbarProps {
  selectedId?: number;
  options: Array<{ value: number; label: string }>;
  isLoading: boolean;
  isSaving: boolean;
  isDeleting: boolean;
  onSelect: (strategyId?: number) => void;
  onSave: () => void;
  onDelete: () => void;
  onReset: () => void;
}

export function SavedStrategyToolbar({
  selectedId,
  options,
  isLoading,
  isSaving,
  isDeleting,
  onSelect,
  onSave,
  onDelete,
  onReset,
}: SavedStrategyToolbarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const selectedName = options.find((option) => option.value === selectedId)?.label;
  return (
    <div className="quant-saved-manager">
      <Button
        type="text"
        icon={<SettingOutlined />}
        aria-expanded={isExpanded}
        onClick={() => setIsExpanded((current) => !current)}
      >
        策略配置管理{selectedName ? ` · ${selectedName}` : ""}
      </Button>
      {isExpanded ? <div className="quant-saved-toolbar">
      <div className="quant-saved-toolbar-heading">
        <HistoryOutlined />
        <span><strong>策略模板</strong><small>加载或保存常用参数组合</small></span>
      </div>
      <div className="quant-saved-toolbar-controls">
        <Select
          aria-label="已保存策略"
          value={selectedId}
          placeholder="加载已保存策略"
          allowClear
          loading={isLoading}
          options={options}
          onChange={(value) => onSelect(value ?? undefined)}
          className="quant-saved-select"
        />
        <div className="quant-saved-actions">
          <Button icon={<ReloadOutlined />} aria-label="恢复默认参数" onClick={onReset}>恢复默认</Button>
          <Button icon={<SaveOutlined />} loading={isSaving} onClick={onSave}>保存策略</Button>
          <Popconfirm
            title={`删除已保存策略“${selectedName ?? ""}”？`}
            description="删除后无法恢复"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            disabled={selectedId == null}
            onConfirm={onDelete}
          >
            <Button icon={<DeleteOutlined />} aria-label="删除已保存策略" danger disabled={selectedId == null} loading={isDeleting}>
              删除
            </Button>
          </Popconfirm>
        </div>
      </div>
      </div> : null}
    </div>
  );
}

export function FormSectionHeader({ title, description }: { title: string; description: string }) {
  const step = title.split(".", 1)[0].padStart(2, "0");
  return (
    <div className="quant-form-section-header">
      <span className="quant-form-step" aria-hidden="true">{step}</span>
      <span className="quant-form-section-copy">
        <Text strong>{title}</Text>
        <Text type="secondary">{description}</Text>
      </span>
    </div>
  );
}

const QUICK_STOCK_PRESETS = [
  { label: "贵州茅台", code: "600519" },
  { label: "宁德时代", code: "300750" },
  { label: "招商银行", code: "600036" },
  { label: "中国平安", code: "601318" },
  { label: "中芯国际", code: "688981" },
  { label: "长江电力", code: "600900" },
];

const THEMATIC_UNIVERSE_PRESETS = [
  {
    name: "沪深300白马",
    desc: "贵州茅台 / 宁德时代 / 中国平安 / 招商银行 / 比亚迪 / 长江电力 / 美的集团 / 紫金矿业",
    codes: "600519, 300750, 601318, 600036, 002594, 600900, 000333, 601899",
    color: "blue",
  },
  {
    name: "AI算力科技",
    desc: "中际旭创 / 新易盛 / 工业富联 / 澜起科技 / 中微公司 / 寒武纪",
    codes: "300308, 300502, 601138, 688008, 688012, 688256",
    color: "purple",
  },
  {
    name: "红利低波高股息",
    desc: "中国神华 / 陕西煤业 / 中国移动 / 工商银行 / 大秦铁路 / 中国石化",
    codes: "601088, 601225, 600941, 601398, 601006, 600028",
    color: "gold",
  },
  {
    name: "高端制造出海",
    desc: "比亚迪 / 汇川技术 / 阳光电源 / 三一重工 / 福耀玻璃",
    codes: "002594, 300124, 300274, 600031, 600660",
    color: "cyan",
  },
  {
    name: "医药医疗创新",
    desc: "恒瑞医药 / 药明康德 / 百济神州 / 迈瑞医疗 / 片仔癀",
    codes: "600276, 603259, 688235, 300760, 600436",
    color: "green",
  },
  {
    name: "半导体芯片",
    desc: "中芯国际 / 北方华创 / 中微公司 / 海光信息 / 韦尔股份 / 澜起科技",
    codes: "688981, 002371, 688012, 688041, 603501, 688008",
    color: "volcano",
  },
  {
    name: "新能源锂电",
    desc: "宁德时代 / 比亚迪 / 亿纬锂能 / 阳光电源 / 天齐锂业 / 赣锋锂业",
    codes: "300750, 002594, 300014, 300274, 002466, 002460",
    color: "lime",
  },
  {
    name: "白酒消费",
    desc: "贵州茅台 / 五粮液 / 泸州老窖 / 山西汾酒 / 伊利股份 / 海天味业",
    codes: "600519, 000858, 000568, 600809, 600887, 603288",
    color: "magenta",
  },
  {
    name: "高换手量价活跃",
    desc: "宗申动力 / 胜宏科技 / 润和软件 / 常山北明 / 软通动力 / 中科曙光",
    codes: "001696, 300476, 300339, 000158, 301236, 603019",
    color: "volcano",
  },
  {
    name: "财报绩优成长",
    desc: "立讯精密 / 中际旭创 / 传音控股 / 沪电股份 / 恒立液压 / 拓普集团",
    codes: "002475, 300308, 688036, 002463, 601100, 601689",
    color: "cyan",
  },
];

export function UniverseFields({ source }: { source: QuantFormValues["source"] }) {
  const form = Form.useFormInstance<QuantFormValues>();
  const formCodes = Form.useWatch("codes", form) ?? "";
  const stockSearch = useStockSearchController({ debounceMs: 200 });
  const watchlist = useWatchlist();
  const watchlistItems = watchlist.data?.items ?? [];

  const handleImportWatchlist = () => {
    if (watchlistItems.length === 0) {
      message.info("自选股列表为空，可在自选页面添加关注标的");
      return;
    }
    const codesToImport = watchlistItems.slice(0, 30);
    codesToImport.forEach((item) => {
      registerStockInfo(item.stock_code, item.stock_name);
    });
    const codesStr = codesToImport.map((i) => i.stock_code).join(", ");
    form.setFieldsValue({
      source: "custom",
      codes: codesStr,
    });
    message.success(`已成功导入 ${codesToImport.length} 只自选股`);
  };

  useEffect(() => {
    stockSearch.currentResults.forEach((item) => {
      registerStockInfo(item.code, item.name);
    });
  }, [stockSearch.currentResults]);

  const parsedCodes = useMemo(() => parseStockCodes(formCodes), [formCodes]);

  const handleQuickCode = (code: string) => {
    const current = (form.getFieldValue("codes") || "").trim();
    if (!current) {
      form.setFieldValue("codes", code);
      return;
    }
    const list = parseStockCodes(current);
    if (!list.includes(code) && list.length < 30) {
      form.setFieldValue("codes", `${current}, ${code}`);
    }
  };

  const handleRemoveCode = (codeToRemove: string) => {
    const current = form.getFieldValue("codes") || "";
    const list = parseStockCodes(current).filter((c) => c !== codeToRemove);
    form.setFieldValue("codes", list.join(", "));
  };

  const handleThematicPreset = (codes: string) => {
    form.setFieldsValue({
      source: "custom",
      codes,
    });
  };

  const { searchTerm: activeSearchTerm } = useMemo(
    () => splitInputSearch(formCodes),
    [formCodes],
  );

  const handleInputChange = (val: string) => {
    form.setFieldValue("codes", val);
    const { searchTerm } = splitInputSearch(val);
    stockSearch.setInputValue(searchTerm);
  };

  const handleSelectOption = (selectedCode: string) => {
    const current = (form.getFieldValue("codes") || "").trim();
    const { prefix } = splitInputSearch(current);
    let nextCodes: string;
    if (prefix) {
      const existingList = parseStockCodes(prefix);
      if (!existingList.includes(selectedCode)) {
        existingList.push(selectedCode);
      }
      nextCodes = existingList.join(", ");
    } else {
      nextCodes = selectedCode;
    }
    form.setFieldValue("codes", nextCodes);
    stockSearch.setInputValue("");
  };

  const handleBlurOrNormalize = () => {
    const current = (form.getFieldValue("codes") || "").trim();
    if (!current) return;
    const tokens = current.split(/[,\s，]+/).map((s: string) => s.trim()).filter(Boolean);
    if (tokens.length === 0) return;
    const resolved = tokens.map((token: string) => {
      const code = resolveStockNameOrCode(token);
      if (code) return code;
      if (
        stockSearch.currentResults.length > 0 &&
        (stockSearch.currentResults[0].name === token || stockSearch.currentResults[0].code === token)
      ) {
        return stockSearch.currentResults[0].code;
      }
      return token;
    });
    const unique = Array.from(new Set(resolved));
    const nextValue = unique.join(", ");
    if (nextValue !== current) {
      form.setFieldValue("codes", nextValue);
    }
  };

  const searchOptions = useMemo(() => {
    if (!activeSearchTerm && !stockSearch.inputValue) return [];
    return stockSearch.currentResults.map((item) => {
      const isHk = item.market === "hk" || /^\d{5}$/.test(item.code);
      return {
        value: item.code,
        label: (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              {isHk ? (
                <Tag color="blue" style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                  港股
                </Tag>
              ) : (
                <Tag color="cyan" style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                  A股
                </Tag>
              )}
              <strong style={{ fontFamily: "monospace" }}>{item.code}</strong>
              <span>{item.name}</span>
            </span>
            {typeof item.price === "number" && (
              <span style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-xs)" }}>
                {isHk ? "HK$" : "¥"}{item.price.toFixed(2)}
              </span>
            )}
          </div>
        ),
      };
    });
  }, [activeSearchTerm, stockSearch.currentResults, stockSearch.inputValue]);

  return (
    <section className="quant-form-section" aria-labelledby="quant-universe-title">
      <div id="quant-universe-title">
        <FormSectionHeader title="1. 回测范围" description="命名任务并确定参与回测的股票池" />
      </div>
      <Row gutter={[14, 0]} align="top">
        <Col xs={24} md={7}>
          <Form.Item name="name" label="回测名称" rules={[{ required: true, whitespace: true, message: "请输入回测名称" }]}>
            <Input maxLength={80} placeholder="例如：消费龙头双均线" />
          </Form.Item>
        </Col>
        <Col xs={24} sm={8} md={5}>
          <Form.Item name="source" label="股票池">
            <Select options={[
              { value: "custom", label: "自定义股票" },
              { value: "portfolio", label: "当前持仓" },
            ]} />
          </Form.Item>
        </Col>
        <Col xs={24} sm={16} md={12}>
          <Form.Item
            name="codes"
            label="股票代码"
            rules={[{
              validator: async (_, value?: string) => {
                const error = stockCodesValidationError(source, value);
                if (error) throw new Error(error);
              },
            }]}
            extra={source === "portfolio" ? "运行时读取当前持仓股票，最多 10 只" : "支持代码或名称搜索关联，逗号/空格分隔，最多 30 只"}
          >
            <AutoComplete
              disabled={source === "portfolio"}
              options={searchOptions}
              onSelect={handleSelectOption}
              onChange={handleInputChange}
              filterOption={false}
              style={{ width: "100%" }}
            >
              <Input
                aria-label="股票代码"
                disabled={source === "portfolio"}
                placeholder="600519, 000001"
                prefix={<SearchOutlined style={{ color: "var(--c-text-muted)" }} />}
                allowClear
                onBlur={handleBlurOrNormalize}
                onPressEnter={handleBlurOrNormalize}
              />
            </AutoComplete>
          </Form.Item>
          {source === "custom" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "-10px", marginBottom: "14px" }}>
              {parsedCodes.length > 0 && parsedCodes[0] && (
                <div className="quant-selected-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                  <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
                    已选股票 ({parsedCodes.length}/30):
                  </span>
                  {parsedCodes.map((code) => {
                    const name = getStockName(code);
                    return (
                      <Tag
                        key={code}
                        closable
                        onClose={(e) => {
                          e.preventDefault();
                          handleRemoveCode(code);
                        }}
                        color="blue"
                        style={{
                          fontSize: "var(--c-font-xs)",
                          marginInlineEnd: 0,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <strong>{code}</strong>
                        {name ? <span style={{ opacity: 0.85 }}>{name}</span> : null}
                      </Tag>
                    );
                  })}
                </div>
              )}
              <div className="quant-quick-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>快速导入:</span>
                <Button
                  size="small"
                  type="dashed"
                  icon={<StarOutlined />}
                  onClick={handleImportWatchlist}
                  style={{ fontSize: "var(--c-font-xs)", height: "24px", lineHeight: "22px", padding: "0 8px" }}
                >
                  导入自选股 ({watchlistItems.length})
                </Button>
              </div>
              <div className="quant-quick-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>精选主题池:</span>
                {THEMATIC_UNIVERSE_PRESETS.map((preset) => (
                  <Tooltip key={preset.name} title={preset.desc}>
                    <Tag
                      color={preset.color}
                      style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                      onClick={() => handleThematicPreset(preset.codes)}
                    >
                      {preset.name}
                    </Tag>
                  </Tooltip>
                ))}
              </div>
              <div className="quant-quick-stocks" style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>快捷加单股:</span>
                {QUICK_STOCK_PRESETS.map((preset) => (
                  <Tag
                    key={preset.code}
                    style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0 }}
                    onClick={() => handleQuickCode(preset.code)}
                  >
                    {preset.label}
                  </Tag>
                ))}
                <Tag
                  style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0, opacity: 0.7 }}
                  onClick={() => form.setFieldValue("codes", "")}
                >
                  清空
                </Tag>
              </div>
            </div>
          ) : null}
        </Col>
      </Row>
    </section>
  );
}

export function StrategyFields({
  strategyType,
  strategyOptions,
  parameterValues,
  onStrategyChange,
}: {
  strategyType: QuantFormValues["strategyType"];
  strategyOptions: StrategyOption[];
  parameterValues: QuantFormValues["strategyParameters"];
  onStrategyChange: (strategyType: QuantFormValues["strategyType"]) => void;
}) {
  const form = Form.useFormInstance<QuantFormValues>();
  const selectedStrategy = strategyOptions.find((option) => option.value === strategyType);
  return (
    <section className="quant-form-section" aria-labelledby="quant-strategy-title">
      <div id="quant-strategy-title">
        <FormSectionHeader title="2. 策略参数" description="选择交易逻辑并调整该策略的核心周期" />
      </div>
      <Form.Item name="strategyType" hidden>
        <Input />
      </Form.Item>
      <Form.Item name="strategyVersion" hidden>
        <Input />
      </Form.Item>
      <StrategyPresetPicker
        value={strategyType}
        options={strategyOptions}
        parameterValues={parameterValues}
        onChange={onStrategyChange}
      />
      <Row gutter={[14, 0]} align="bottom">
        {selectedStrategy?.parameters.map((parameter) => (
          <Col xs={12} sm={8} md={6} key={parameter.key}>
            <Form.Item
              name={["strategyParameters", parameter.key]}
              label={parameter.label}
              extra={parameter.description || undefined}
              valuePropName={parameter.type === "boolean" ? "checked" : "value"}
              dependencies={strategyConstraintDependencies(parameter.key, selectedStrategy.constraints)}
              rules={[
                { required: true, message: `请输入${parameter.label}` },
                {
                  validator: async () => {
                    const error = strategyConstraintValidationError(
                      parameter.key,
                      selectedStrategy.constraints,
                      form.getFieldValue("strategyParameters") ?? {},
                    );
                    if (error) throw new Error(error);
                  },
                },
              ]}
            >
              {parameter.choices?.length ? (
                <Select options={parameter.choices.map((value) => ({ value, label: String(value) }))} />
              ) : parameter.type === "boolean" ? (
                <Switch />
              ) : parameter.type === "integer" || parameter.type === "number" ? (
                <InputNumber
                  min={parameter.minimum ?? undefined}
                  max={parameter.maximum ?? undefined}
                  step={parameter.step ?? (parameter.type === "integer" ? 1 : undefined)}
                  precision={parameter.type === "integer" ? 0 : undefined}
                  style={{ width: "100%" }}
                />
              ) : (
                <Input maxLength={120} />
              )}
            </Form.Item>
          </Col>
        ))}
      </Row>
    </section>
  );
}
