import React, { useState } from "react";
import { CheckOutlined, CopyOutlined } from "@ant-design/icons";
import { Button, Tooltip } from "antd";

interface CodeBlockProps extends React.HTMLAttributes<HTMLPreElement> {
  children?: React.ReactNode;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ children, ...props }) => {
  const [copied, setCopied] = useState(false);

  let language = "";
  let codeText = "";

  if (React.isValidElement(children)) {
    const childProps = children.props as { className?: string; children?: React.ReactNode };
    const match = /language-([a-zA-Z0-9_-]+)/.exec(childProps?.className || "");
    if (match) {
      language = match[1];
    }
    if (typeof childProps?.children === "string") {
      codeText = childProps.children;
    } else if (Array.isArray(childProps?.children)) {
      codeText = childProps.children.join("");
    }
  }

  if (!codeText && typeof children === "string") {
    codeText = children;
  }

  const handleCopy = async () => {
    if (!codeText) return;
    try {
      await navigator.clipboard.writeText(codeText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // ignore
    }
  };

  const isQuantPython =
    language.toLowerCase() === "python" &&
    /(strategy|backtest|dataframe|pandas|talib|kline|sma|ema|macd|handle_data|initialize|回测|策略)/i.test(codeText);

  return (
    <div
      className="chat-code-block"
      style={{
        margin: "12px 0",
        borderRadius: 8,
        border: "1px solid var(--c-border)",
        background: "var(--c-card-bg)",
        overflow: "hidden",
      }}
    >
      <div
        className="chat-code-block-header"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "6px 12px",
          background: "color-mix(in srgb, var(--c-page-bg) 60%, transparent)",
          borderBottom: "1px solid var(--c-border)",
          fontSize: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontFamily: "var(--c-font-mono)",
              fontWeight: 600,
              fontSize: 11,
              padding: "1px 6px",
              borderRadius: 4,
              background: "var(--c-border)",
              color: "var(--c-text-secondary)",
              textTransform: "uppercase",
            }}
          >
            {(language || "CODE").toUpperCase()}
          </span>
          {isQuantPython && (
            <span
              style={{
                fontSize: 11,
                color: "var(--c-primary)",
                fontWeight: 500,
              }}
            >
              量化策略片段
            </span>
          )}
        </div>
        <Tooltip title={copied ? "已复制代码" : "复制代码"}>
          <Button
            type="text"
            size="small"
            icon={copied ? <CheckOutlined style={{ color: "var(--c-up)" }} /> : <CopyOutlined />}
            onClick={handleCopy}
            aria-label="复制代码"
            style={{ height: 24, fontSize: 12, display: "flex", alignItems: "center" }}
          >
            {copied ? "已复制" : "复制"}
          </Button>
        </Tooltip>
      </div>
      <pre
        {...props}
        style={{
          margin: 0,
          padding: "var(--c-pad-card, 16px 18px)",
          overflowX: "auto",
          fontFamily: "var(--c-font-mono)",
          fontSize: 13,
          lineHeight: 1.5,
          background: "transparent",
        }}
      >
        {children}
      </pre>
    </div>
  );
};
