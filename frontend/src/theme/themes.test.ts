import { describe, expect, it } from "vitest";
import { THEME_LIST } from "./themes";

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((index) => Number.parseInt(hex.slice(index, index + 2), 16) / 255);
  const [red, green, blue] = channels.map((channel) => (
    channel <= 0.03928
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastWithWhite(hex: string): number {
  return 1.05 / (relativeLuminance(hex) + 0.05);
}

describe("theme brand colors", () => {
  it.each(THEME_LIST)("keeps $key primary tokens readable and synchronized", (theme) => {
    expect(theme.antToken.colorPrimary).toBe(theme.colors.primary);
    expect(theme.colors.primary).not.toBe(theme.colors.up);
    expect(theme.colors.primary).not.toBe(theme.colors.down);
    expect(contrastWithWhite(theme.colors.primary)).toBeGreaterThanOrEqual(4.5);
  });
});
