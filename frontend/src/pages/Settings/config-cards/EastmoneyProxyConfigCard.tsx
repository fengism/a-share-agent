import { useMemo } from "react";
import { GlobalOutlined, InfoCircleOutlined, WifiOutlined } from "@ant-design/icons";
import { Alert, Button, Checkbox, Col, Divider, Input, InputNumber, Row, Segmented, Tag, Tooltip, Typography } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";
import type { OutboundProxyType, ProxyTestResponse, TdxProxyTestResponse } from "../../../types/settings";
import {
  PLACEHOLDER,
  PROXY_SCOPE_OPTIONS,
  validateProxyUrl,
} from "./EastmoneyProxyConfigCard.utils";

const PROXY_TYPE_OPTIONS: { value: OutboundProxyType; label: string }[] = [
  { value: "none", label: "直连（不使用代理）" },
  { value: "http", label: "HTTP 代理" },
  { value: "socks5", label: "SOCKS5 代理" },
];

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
  onTestTdx,
  isTestingTdx,
  tdxTestResult,
}: ConfigCardProps & {
  onTest?: () => void;
  isTesting?: boolean;
  testResult?: ProxyTestResponse | null;
  onTestTdx?: () => void;
  isTestingTdx?: boolean;
  tdxTestResult?: TdxProxyTestResponse | null;
}) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  const proxyType = (form.outbound_proxy_type ?? "none") as OutboundProxyType;
  const proxyUrl = form.outbound_proxy_url ?? "";
  const proxyEnabled = proxyType !== "none";
  const selectedScopes = form.outbound_proxy_scopes ?? ["eastmoney"];
  const tdxScopeEnabled = selectedScopes.includes("tdxhub");

  const urlError = useMemo(() => {
    if (!proxyEnabled) return null;
    if (!proxyUrl || proxyUrl.includes("***")) return null;
    return validateProxyUrl(proxyUrl, proxyType);
  }, [proxyEnabled, proxyType, proxyUrl]);

  const scopeOptions = useMemo(
    () =>
      PROXY_SCOPE_OPTIONS.map((opt) => ({
        value: opt.value,
        label: (
          <span>
            <span style={{ fontWeight: 500 }}>{opt.label}</span>
            <Tag
              color={opt.tagColor}
              style={{
                marginLeft: 6,
                fontSize: "var(--c-font-xs)",
                lineHeight: "18px",
                padding: "0 4px",
                borderRadius: 2,
              }}
            >
              {opt.tag}
            </Tag>
            <span style={{ color: colors.textMuted, fontSize: "var(--c-font-xs)" }}>
              （{opt.desc}）
            </span>
          </span>
        ),
      })),
    [colors.textMuted],
  );

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
        title="数据源出站代理路由"
        description="国内财经站点常对境外或机房出口 IP 实行严格风控（如返回 403 或重置连接）。您可灵活勾选下方需要走代理的数据源；未勾选的接口将保持直连以获得最优速度。"
      />
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>代理类型</div>
          <Segmented
            aria-label="出站代理类型"
            block
            value={proxyType}
            options={PROXY_TYPE_OPTIONS}
            onChange={(value) => {
              const nextType = value as OutboundProxyType;
              const patch: { outbound_proxy_type: OutboundProxyType; outbound_proxy_url?: string } = {
                outbound_proxy_type: nextType,
              };
              if (nextType === "none") {
                patch.outbound_proxy_url = "";
              } else if (proxyUrl.includes("***")) {
                patch.outbound_proxy_url = "";
              }
              onChange(patch);
            }}
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
        <Col span={24}>
          <div style={fieldLabelStyle}>走代理的接口与数据源</div>
          <Checkbox.Group
            aria-label="走代理的接口与数据源"
            disabled={!proxyEnabled}
            options={scopeOptions}
            value={selectedScopes}
            onChange={(checkedValues) =>
              onChange({ outbound_proxy_scopes: checkedValues as string[] })
            }
          />
          {proxyEnabled && selectedScopes.length === 0 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginTop: 8 }}
              message="当前未选中任何数据源，所有出网请求将保持直连；如需代理请至少勾选一项（海外服务器推荐勾选东财与 AkShare）。"
            />
          )}
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            仅选中的数据源出网请求会通过代理转发；未勾选的接口保持直连以获得最优速度与稳定性。
          </div>
        </Col>
      </Row>

      <Divider style={{ margin: "16px 0 12px" }} />
      <Row gutter={[12, 12]} align="middle">
        <Col xs={24} sm={14}>
          <Button icon={<WifiOutlined />} loading={isTesting} onClick={onTest} disabled={!proxyEnabled}>
            测试连通性
          </Button>
          {isDirty && proxyEnabled && (
            <Tooltip title="配置已修改但尚未保存，连通性测试将测试后端当前已保存生效的配置">
              <span style={{ marginLeft: 8, color: colors.warning, fontSize: "var(--c-font-xs)", cursor: "help" }}>
                <InfoCircleOutlined style={{ marginRight: 4 }} />
                配置有变动，请先保存再测试
              </span>
            </Tooltip>
          )}
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

      {/* TDX 行情走原始 TCP，HTTP 探测测不到，需要单独做隧道 + 协议往返验证 */}
      {proxyEnabled && tdxScopeEnabled && (
        <Row gutter={[12, 12]} align="middle" style={{ marginTop: 8 }}>
          <Col xs={24} sm={14}>
            <Button icon={<WifiOutlined />} loading={isTestingTdx} onClick={onTestTdx}>
              测试 TDX 连通性
            </Button>
            {tdxTestResult && (
              <span style={{ marginLeft: 12, color: tdxTestResult.ok ? colors.success : colors.down }}>
                {tdxTestResult.ok ? "TDX 可用" : "TDX 不可用"} · {tdxTestResult.latency_ms}ms
                {tdxTestResult.endpoint ? ` · ${tdxTestResult.endpoint}` : ""}
              </span>
            )}
          </Col>
          <Col xs={24} sm={10}>
            {tdxTestResult && (
              <Typography.Paragraph
                type="secondary"
                style={{ marginBottom: 0, fontSize: "var(--c-font-xs)", wordBreak: "break-all" }}
              >
                {tdxTestResult.message}
              </Typography.Paragraph>
            )}
          </Col>
        </Row>
      )}

      <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0, fontSize: "var(--c-font-xs)" }}>
        连通性测试针对当前已保存的配置，请先保存再测试。SOCKS5 代理需要后端安装 PySocks 或
        socksio 依赖，否则请求会直接报错。
      </Typography.Paragraph>
      {proxyEnabled && tdxScopeEnabled && (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0, fontSize: "var(--c-font-xs)" }}>
          TDX 连通性测试会先建立代理隧道，再向行情节点发一次 round2 协议请求；
          “代理隧道不可用”说明代理配置有问题，“目标行情节点不可用”说明代理正常但该节点行情接口异常。
        </Typography.Paragraph>
      )}
    </SettingsCard>
  );
}
