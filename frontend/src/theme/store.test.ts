import { describe, expect, it } from "vitest";
import { normalizeThemeKey } from "./store";

describe("normalizeThemeKey", () => {
  it("keeps the supported light theme", () => {
    expect(normalizeThemeKey("light")).toBe("light");
  });

  it.each(["stellar-blue", "jade-green", "twilight-purple", "unknown", null])(
    "falls back unsupported theme %s to professional dark",
    (themeKey) => {
      expect(normalizeThemeKey(themeKey)).toBe("stellar-blue");
    },
  );
});
