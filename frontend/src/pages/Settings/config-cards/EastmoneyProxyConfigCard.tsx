import { useMemo } from "react";
import { GlobalOutlined, WifiOutlined } from "@ant-design/icons";
import { Alert, Button, Col, Divider, Input, InputNumber, Row, Segmented, Typography } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";
import type { OutboundProxyType, ProxyTestResponse } from "../../../types/settings";

const PROXY_TYPE_OPTIONS: { value: OutboundProxyType; label: string }[] = [
  { value: "none", label: "直连（不使用代理）" },
  { value: "http", label: "HTTP 代理" },
  { value: "socks5", label: "SOCKS5 代理" },
];

const PLACEHOLDER: Record<OutboundProxyType, string> = {
  none: "未启用代理",
  http: "http://用户名:密码@代理地址:端口",
  socks5: "socks5h://用户名:密码@代理地址:端口",
};

/** 提交前的前端校验，避免把明显非法的地址写进全局配置。 */
function validateProxyUrl(url: string, proxyType: OutboundProxyType): string | null {
  const value = url.trim();
  if (!value) return "启用代理后必须填写代理地址";
  if (/\s/.test(value)) return "代理地址不能包含空格";
  const withScheme = /:\/\//.test(value) ? value : `${proxyType === "socks5" ? "socks5h" : "http"}://${value}`;
  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    return "代理地址格式无法解析";
  }
  const scheme = parsed.protocol.replace(":", "").toLowerCase();
  const isSocksScheme = scheme.startsWith("socks");
  if (proxyType === "socks5" && !isSocksScheme) return "代理类型为 SOCKS5 时，地址协议必须是 socks5/socks5h";
  if (proxyType === "http" && isSocksScheme) return "代理类型为 HTTP 时，地址协议必须是 http/https";
  if (!parsed.hostname) return "代理地址缺少主机名";
  if (proxyType === "socks5" && !parsed.port) return "SOCKS5 代理必须指定端口，例如 socks5h://user:pass@host:2260";
  return null;
}

export default function OutboundProxyConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  stretch,
  isDirty,
  onReset,
  onTest,
  isTesting,
  testResult,
}: ConfigCardProps & {
  onTest?: () => void;
  isTesting?: boolean;
  testResult?: ProxyTestResponse | null;
}) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  const proxyType = (form.outbound_proxy_type ?? "none") as OutboundProxyType;
  const proxyUrl = form.outbound_proxy_url ?? "";
  const proxyEnabled = proxyType !== "none";

  const urlError = useMemo(() => {
    if (!proxyEnabled) return null;
    if (!proxyUrl || proxyUrl.includes("***")) return null;
    return validateProxyUrl(proxyUrl, proxyType);
  }, [proxyEnabled, proxyType, proxyUrl]);

  return (
    <SettingsCard
      title="出站代理（公共）"
      icon={<GlobalOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存出站代理配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        title="供按出口 IP 风控的上游接口共用"
        description="东方财富按出口 IP 风控，境外或机房 IP 直连历史接口会返回 403。代理按接口粒度启用：每个数据源自行声明生效范围，未声明的接口保持直连，不影响其反爬策略。当前生效：东财 K 线与资金流接口。"
      />
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>代理类型</div>
          <Segmented
            aria-label="出站代理类型"
            block
            value={proxyType}
            options={PROXY_TYPE_OPTIONS}
            onChange={(value) =>
              onChange({
                outbound_proxy_type: value as OutboundProxyType,
              })
            }
          />
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>代理地址</div>
          <Input.Password
            aria-label="出站代理地址"
            value={proxyUrl}
            disabled={!proxyEnabled}
            status={urlError ? "error" : undefined}
            placeholder={PLACEHOLDER[proxyType]}
            onChange={(event) => onChange({ outbound_proxy_url: event.target.value })}
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: urlError ? colors.down : colors.textMuted }}>
            {urlError ?? (
              proxyUrl.includes("***")
                ? "已保存（含凭证，内容已脱敏）。重新填写完整地址即可覆盖。"
                : "协议可省略：HTTP 代理填 host:port，SOCKS5 代理填 user:pass@host:port。"
            )}
          </div>
        </Col>
        <Col xs={24} sm={12}>
          <div style={fieldLabelStyle}>代理请求超时（秒）</div>
          <InputNumber
            aria-label="出站代理请求超时"
            min={5}
            max={120}
            step={5}
            style={{ width: "100%" }}
            value={form.outbound_proxy_timeout_seconds ?? 20}
            onChange={(value) =>
              onChange({ outbound_proxy_timeout_seconds: (value ?? 20) as number })
            }
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            走代理时覆盖接口默认超时，代理链路通常更慢。
          </div>
        </Col>
        <Col xs={24} sm={12}>
          <div style={fieldLabelStyle}>失败重试次数</div>
          <InputNumber
            aria-label="出站代理失败重试次数"
            min={0}
            max={6}
            step={1}
            style={{ width: "100%" }}
            value={form.outbound_proxy_retries ?? 2}
            onChange={(value) =>
              onChange({ outbound_proxy_retries: (value ?? 0) as number })
            }
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            代理不稳定时按指数退避重试，仅对代理请求生效。
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: "16px 0 12px" }} />
      <Row gutter={[12, 12]} align="middle">
        <Col xs={24} sm={14}>
          <Button icon={<WifiOutlined />} loading={isTesting} onClick={onTest} disabled={!proxyEnabled}>
            测试连通性
          </Button>
          {testResult && (
            <span style={{ marginLeft: 12, color: testResult.ok ? colors.success : colors.down }}>
              {testResult.ok ? "代理可用" : "代理不可用"} · {testResult.latency_ms}ms
              {testResult.exit_ip ? ` · 出口 ${testResult.exit_ip}` : ""}
            </span>
          )}
        </Col>
        <Col xs={24} sm={10}>
          {testResult && (
            <Typography.Paragraph
              type="secondary"
              style={{ marginBottom: 0, fontSize: "var(--c-font-xs)", wordBreak: "break-all" }}
            >
              {testResult.message}
            </Typography.Paragraph>
          )}
        </Col>
      </Row>

      <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: "var(--c-font-xs)" }}>
        连通性测试针对当前已保存的配置，请先保存再测试。SOCKS5 代理需要后端安装 PySocks 或
        socksio 依赖，否则请求会直接报错。
      </Typography.Paragraph>
    </SettingsCard>
  );
}