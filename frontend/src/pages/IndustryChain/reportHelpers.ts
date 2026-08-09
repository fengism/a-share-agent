export function extractBestString(value: unknown, depth = 0): string {
  if (depth > 5) return "";
  if (typeof value === "string" && value.length > 10) return value;

  if (Array.isArray(value)) {
    for (const item of value) {
      const result = extractBestString(item, depth + 1);
      if (result) return result;
    }
    return value.filter((item) => typeof item === "string" && item.length > 4).join("\n\n").slice(0, 50000);
  }

  if (value && typeof value === "object") {
    const entries = value as Record<string, unknown>;
    const priorityKeys = [
      "llm_report",
      "content",
      "text",
      "review",
      "llm_review",
      "markdown",
      "summary",
      "analysis",
      "report",
    ];
    for (const key of priorityKeys) {
      if (typeof entries[key] === "string" && entries[key].length > 10) return entries[key];
    }

    const parts: string[] = [];
    const collect = (item: unknown, currentDepth: number) => {
      if (currentDepth > 10) return;
      if (typeof item === "string" && item.length > 4) parts.push(item);
      else if (Array.isArray(item)) item.forEach((child) => collect(child, currentDepth + 1));
      else if (item && typeof item === "object") {
        Object.values(item as Record<string, unknown>).forEach((child) => collect(child, currentDepth + 1));
      }
    };
    collect(value, 0);
    if (parts.length > 0) return parts.join("\n\n").slice(0, 50000);
  }

  return "";
}

export function tryExtractFromJson(raw: string): string {
  const tryParse = (value: string): unknown => {
    try {
      return JSON.parse(value);
    } catch {
      return null;
    }
  };
  const escapeLiteralNewlines = (value: string) => value.replace(
    /:\s*"((?:[^"\\]|\\.)*?)"/gs,
    (match) => match.replace(/\n/g, "\\n").replace(/\r/g, "\\r"),
  );

  let parsed = tryParse(raw);
  if (!parsed) parsed = tryParse(escapeLiteralNewlines(raw));

  if (!parsed) {
    const start = raw.indexOf("{");
    const end = raw.lastIndexOf("}");
    if (start !== -1 && end > start) {
      const jsonPortion = raw.slice(start, end + 1);
      parsed = tryParse(jsonPortion) || tryParse(escapeLiteralNewlines(jsonPortion));
    }
  }

  return parsed && typeof parsed === "object" ? extractBestString(parsed) : raw;
}
