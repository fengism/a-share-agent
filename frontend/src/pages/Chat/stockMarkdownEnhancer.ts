/**
 * 将 Markdown 中的股票代码及名称转换为 stock:// 自定义协议链接，
 * 供 ReactMarkdown 渲染为交互式 StockMentionPill 组件。
 *
 * 例：贵州茅台(600519) -> [贵州茅台 (600519)](stock://600519?name=%E8%B4%B5%E5%B7%9E%E8%8C%85%E5%8F%B0)
 */

const LEADING_KEYWORDS_REGEX =
  /^(.*)(关注|推荐|分析|看好|买入|卖出|增持|减持|持有|如|比如|例如|与|和|及|包括|重仓|标的|个股|正文|关于)/;

export function enrichStockMentions(markdown: string): string {
  if (!markdown) return "";

  // 分割代码块与普通文本，避免替换代码块中的文本
  const codeBlockRegex = /(```[\s\S]*?```|`[^`\n]+`)/g;
  const parts = markdown.split(codeBlockRegex);

  return parts
    .map((part) => {
      // 如果是代码块或内联代码，原样返回
      if (part.startsWith("`")) {
        return part;
      }

      // 匹配：股票名称 + (代码)
      return part.replace(
        /([\u4e00-\u9fa5A-Za-z0-9*]{2,8})\s*[（(]([03468]\d{5}|\d{5})[）)]/g,
        (_match, rawName, code) => {
          let prefix = "";
          let cleanName = rawName;

          const keywordMatch = rawName.match(LEADING_KEYWORDS_REGEX);
          if (keywordMatch) {
            prefix = keywordMatch[1] + keywordMatch[2];
            cleanName = rawName.slice(prefix.length);
          }

          if (cleanName.length < 2) {
            cleanName = rawName;
            prefix = "";
          }

          const encodedName = encodeURIComponent(cleanName);
          return `${prefix}[${cleanName} (${code})](stock://${code}?name=${encodedName})`;
        },
      );
    })
    .join("");
}

export function parseStockProtocolUrl(href: string): { code: string; name?: string } | null {
  if (!href.startsWith("stock://")) return null;
  try {
    const raw = href.replace(/^stock:\/\//, "");
    const [code, queryString] = raw.split("?");
    if (!code) return null;

    let name: string | undefined;
    if (queryString) {
      const params = new URLSearchParams(queryString);
      name = params.get("name") || undefined;
    }
    return { code, name };
  } catch {
    return null;
  }
}
