export function formatToolArguments(value?: string): string {
  if (!value?.trim()) return "{}";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}
