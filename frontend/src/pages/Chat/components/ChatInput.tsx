import { useCallback, useMemo, useState, type KeyboardEvent } from "react";
import {
  CodeOutlined,
  CompassOutlined,
  FilterOutlined,
  FireOutlined,
  FundOutlined,
  LineChartOutlined,
  SendOutlined,
  StockOutlined,
} from "@ant-design/icons";
import { Button, Dropdown, Input, Tooltip, type MenuProps } from "antd";
import { useStockSearch } from "../../../api/queryHooks/stock";
import { useColors, useTokens } from "../../../styles/ui";
import "./chat-input.css";

interface ChatInputProps {
  value: string;
  isStreaming: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
}

interface SlashCommand {
  key: string;
  command: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  template: string;
}

const SLASH_COMMANDS: SlashCommand[] = [
  {
    key: "kline",
    command: "/kline",
    icon: <LineChartOutlined />,
    label: "技术与形态诊断",
    description: "分析标的多周期走势、均线及量价突破形态",
    template: "分析贵州茅台(600519)近期技术形态、均线系统与关键支撑压力位",
  },
  {
    key: "compare",
    command: "/compare",
    icon: <FundOutlined />,
    label: "双股深度对比",
    description: "从基本面、估值、盈利能力与机构评级横向PK",
    template: "深度对比宁德时代(300750)与比亚迪(002594)的估值、毛利率与核心壁垒",
  },
  {
    key: "f10",
    command: "/f10",
    icon: <CodeOutlined />,
    label: "财务三张表体检",
    description: "企业现金流充沛度、资产负债率与商誉减值排雷",
    template: "体检五粮液(000858)的财务三张表健康度、现金流与应收账款周转",
  },
  {
    key: "screener",
    command: "/screener",
    icon: <FilterOutlined />,
    label: "量化多因子选股",
    description: "自然语言条件选股（如低估值、高股息、破净资产）",
    template: "帮我找市盈率PE<20、股息率>3%且近三年净利润正增长的优质标的",
  },
  {
    key: "dragon",
    command: "/dragon",
    icon: <FireOutlined />,
    label: "龙虎榜与游资席位",
    description: "洞察机构与知名游资席位抢筹及博弈热点",
    template: "分析今日龙虎榜机构净买入金额靠前的标的及游资合力方向",
  },
  {
    key: "review",
    command: "/review",
    icon: <CompassOutlined />,
    label: "大盘全景复盘",
    description: "指数涨跌、成交量能、连板天梯与主线轮动复盘",
    template: "总结今日A股收盘复盘，分析盘面主线题材、量能变化与后市策略",
  },
];

function getSessionPromptSuggestions(): string[] {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < 9 * 60 + 30) {
    return ["早盘集合竞价异动板块", "今日主线题材与风向标", "北向资金近期增持标的"];
  }
  if (minutes < 15 * 60) {
    return ["盘中主力净流入前三行业", "当前涨停连板天梯与龙头股", "分析当前市场量能与情绪"];
  }
  return ["今日 A 股收盘复盘与主线总结", "龙虎榜机构与知名游资买入标的", "挖掘高股息低估值潜力股"];
}

export function ChatInput({
  value,
  isStreaming,
  onChange,
  onSend,
  onStop,
}: ChatInputProps) {
  const c = useColors();
  const t = useTokens();
  const suggestions = getSessionPromptSuggestions();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  // 提取输入中以 $ 开头的搜索词
  const stockMatch = value.match(/\$([A-Za-z0-9\u4e00-\u9fa5]{1,8})$/);
  const stockQuery = stockMatch ? stockMatch[1] : "";
  const { data: searchResults } = useStockSearch(stockQuery);
  const matchedStocks = useMemo(() => {
    if (!stockQuery || !searchResults) return [];
    return searchResults.slice(0, 5);
  }, [stockQuery, searchResults]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  const handleSelectCommand = useCallback((cmd: SlashCommand) => {
    onChange(cmd.template);
    setDropdownOpen(false);
  }, [onChange]);

  const handleSelectStock = (stock: { code: string; name: string }) => {
    if (!stockMatch) return;
    const prefix = value.slice(0, stockMatch.index);
    const nextValue = `${prefix}${stock.name}(${stock.code}) `;
    onChange(nextValue);
  };

  const commandMenuItems: MenuProps["items"] = useMemo(() => {
    return SLASH_COMMANDS.map((cmd) => ({
      key: cmd.key,
      icon: <span className="chat-input__icon">{cmd.icon}</span>,
      label: (
        <div className="chat-input__cmd-row">
          <div className="chat-input__cmd-head">
            <span className="chat-input__cmd-name">
              {cmd.command}
            </span>
            <span className="chat-input__cmd-label">{cmd.label}</span>
          </div>
          <span className="chat-input__cmd-desc">{cmd.description}</span>
        </div>
      ),
      onClick: () => handleSelectCommand(cmd),
    }));
  }, [handleSelectCommand]);

  const handleTextChange = (newVal: string) => {
    onChange(newVal);
    // 当输入以 / 开头且很短时，自动展开指令下拉
    if (newVal === "/" || newVal === "、") {
      setDropdownOpen(true);
    } else if (!newVal.startsWith("/")) {
      setDropdownOpen(false);
    }
  };

  return (
    <div className="chat-input__root">
      {!isStreaming && !value && (
        <div className="chat-input__quick-row">
          <span className="chat-input__hint">💡 快捷探索：</span>
          {suggestions.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onChange(prompt)}
              className="chat-input__quick-chip"
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = c.primary;
                e.currentTarget.style.color = c.primary;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = c.border;
                e.currentTarget.style.color = c.textSecondary;
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      <div className="chat-input__row">
        {/* $ 股票联想菜单 */}
        {matchedStocks.length > 0 && (
          <div className="chat-input__dropdown">
            <div className="chat-input__picker-head">
              <StockOutlined className="chat-input__icon" />
              <span>选择股票插入 (输入 $ 触发)</span>
            </div>
            <div className="chat-input__picker-list">
              {matchedStocks.map((stock) => (
                <button
                  key={stock.code}
                  type="button"
                  onClick={() => handleSelectStock(stock)}
                  className="chat-input__picker-item"
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = c.hoverBg;
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <span className="chat-input__picker-name">{stock.name}</span>
                  <span className="chat-input__picker-code">
                    {stock.code}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <Dropdown
          menu={{ items: commandMenuItems }}
          trigger={["click"]}
          open={dropdownOpen}
          onOpenChange={setDropdownOpen}
          placement="topLeft"
        >
          <Tooltip title="快捷投研指令 (/kline, /compare, /f10...)">
            <Button
              type="dashed"
              style={{
                height: 40,
                borderRadius: t.radius.lg,
                borderColor: dropdownOpen ? c.primary : c.border,
                color: dropdownOpen ? c.primary : c.textSecondary,
                fontFamily: "monospace",
                fontWeight: 600,
              }}
              onClick={() => setDropdownOpen((open) => !open)}
              disabled={isStreaming}
            >
              / 指令
            </Button>
          </Tooltip>
        </Dropdown>

        <div className="chat-input__field">
          <Input.TextArea
            value={value}
            onChange={(event) => handleTextChange(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入问题、'/' 唤起指令或 '$' 联想股票，如：$茅台、/kline 贵州茅台..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isStreaming}
            className="chat-input__input"
          />
        </div>

        {isStreaming ? (
          <Button
            onClick={onStop}
            danger
            className="chat-input__action"
          >
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            disabled={!value.trim()}
            className="chat-input__action"
          >
            发送
          </Button>
        )}
      </div>

      <div className="chat-input__footer">
        <span className="chat-input__hint">
          支持 <strong>/</strong> 呼出投研指令 · 支持 <strong>$</strong> 联想股票代码
        </span>
        <span className="chat-input__hint">
          Enter 发送 / Shift + Enter 换行
        </span>
      </div>
    </div>
  );
}
