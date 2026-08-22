import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { THEME_LIST } from "../theme/themes";
import { useThemeStore } from "../theme/store";
import ThemeSelector from "./ThemeSelector";

describe("ThemeSelector", () => {
  beforeEach(() => {
    useThemeStore.getState().setThemeKey("stellar-blue");
  });

  it("renders a local radio menu and updates the active theme", () => {
    const nextTheme = THEME_LIST.find((theme) => theme.key !== "stellar-blue")!;
    render(<ThemeSelector iconOnly />);

    const trigger = screen.getByRole("button", { name: /切换主题/ });
    fireEvent.click(trigger);
    const menu = screen.getByRole("radiogroup", { name: "选择界面主题" });

    expect(trigger.parentElement).toContainElement(menu);
    fireEvent.click(screen.getByRole("radio", { name: new RegExp(nextTheme.label) }));

    expect(useThemeStore.getState().themeKey).toBe(nextTheme.key);
    expect(screen.queryByRole("radiogroup", { name: "选择界面主题" })).not.toBeInTheDocument();
  });
});
