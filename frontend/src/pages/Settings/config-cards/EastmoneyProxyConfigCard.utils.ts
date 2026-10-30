import type { OutboundProxyType } from "../../../types/settings";

export interface ProxyScopeOption {
  label: string;
  value: string;
  tag: string;
  tagColor: "error" | "warning" | "success" | "default";
  desc: string;
}

export const PROXY_SCOPE_OPTIONS: ProxyScopeOption[] = [
  {
    label: "东方财富",
    value: "eastmoney",
    tag: "海外必需",
    tagColor: "error",
    desc: "K线、资金流、估值比较、龙虎榜（官方接口对海外 IP 严格重置连接）",
  },
  {
    label: "AkShare",
    value: "akshare",
    tag: "海外必需",
    tagColor: "error",
    desc: "财务三张表与补充指标（底层爬取东财数据，海外环境强制走代理）",
  },
  {
    label: "财联社",
    value: "cls",
    tag: "建议配置",
    tagColor: "warning",
    desc: "市场情绪、今日题材主线、电报快讯（主端点超时收紧至 5s）",
  },
  {
    label: "同花顺",
    value: "ths",
    tag: "建议配置",
    tagColor: "warning",
    desc: "热门股票、实时资金流向、概念热榜（防频繁请求风控）",
  },
  {
    label: "新浪财经",
    value: "sina",
    tag: "直连最快",
    tagColor: "success",
    desc: "行情快照、大盘指数分时、历史K线（无境外 IP 墙，直连延迟最低）",
  },
  {
    label: "通达信（TDX）",
    value: "tdxhub",
    tag: "按需启用",
    tagColor: "default",
    desc: "实时行情、K线与 F10 直连行情服务器（原始 TCP，整条链路走代理，SOCKS5 无需额外依赖）",
  },
];

export const PLACEHOLDER: Record<OutboundProxyType, string> = {
  none: "未启用代理",
  http: "http://用户名:密码@代理地址:端口",
  socks5: "socks5h://用户名:密码@代理地址:端口",
};

/** 规范化代理地址：未提供协议头时自动补齐，便于提交与后续处理。 */
export function normalizeProxyUrl(rawUrl: string, proxyType: OutboundProxyType): string {
  const value = rawUrl.trim();
  if (!value) return "";
  const schemeMatch = value.match(/^([a-zA-Z0-9+-]+):\/\/(.*)$/);
  if (!schemeMatch) {
    return `${proxyType === "socks5" ? "socks5h" : "http"}://${value}`;
  }
  const scheme = schemeMatch[1].toLowerCase();
  const remainder = schemeMatch[2];
  if (proxyType === "socks5" && scheme === "socks") {
    return `socks5h://${remainder}`;
  }
  return value;
}

/** 提交前的前端校验，避免把明显非法的地址写进全局配置。 */
export function validateProxyUrl(url: string, proxyType: OutboundProxyType): string | null {
  const value = url.trim();
  if (!value) return "启用代理后必须填写代理地址";
  if (/\s/.test(value)) return "代理地址不能包含空格";

  const schemeMatch = value.match(/^([a-zA-Z0-9+-]+):\/\/(.*)$/);
  const rawScheme = schemeMatch ? schemeMatch[1].toLowerCase() : null;
  const remainder = schemeMatch ? schemeMatch[2] : value;

  const isSocksScheme = Boolean(rawScheme && rawScheme.startsWith("socks"));
  if (proxyType === "socks5" && rawScheme && !isSocksScheme) {
    return "代理类型为 SOCKS5 时，地址协议必须是 socks5/socks5h";
  }
  if (proxyType === "http" && isSocksScheme) {
    return "代理类型为 HTTP 时，地址协议必须是 http/https";
  }
  if (proxyType === "http" && rawScheme && rawScheme !== "http" && rawScheme !== "https") {
    return "代理类型为 HTTP 时，地址协议必须是 http/https";
  }

  // 浏览器原生 new URL() 对非标准协议（如 socks5/socks5h）在部分环境下不会解析 authority
  // （导致 hostname/port 为空）。这里借用 http:// 构造虚拟对象做稳健解析。
  let dummy: URL;
  try {
    dummy = new URL(`http://${remainder}`);
  } catch {
    return "代理地址格式无法解析";
  }

  if (!dummy.hostname) return "代理地址缺少主机名";
  if (proxyType === "socks5" && !dummy.port) {
    return "SOCKS5 代理必须指定端口，例如 socks5h://user:pass@host:2260";
  }
  return null;
}
