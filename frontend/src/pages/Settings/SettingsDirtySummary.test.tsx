import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SettingsDirtySummary from "./SettingsDirtySummary";
import type { CardKey } from "./cardSpecs";
import type { SettingsCards } from "./useSettingsForm";

function makeCards(dirtyKeys: CardKey[]): SettingsCards & { save: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> } {
  const dirty = {} as Record<CardKey, boolean>;
  for (const key of ["llm", "feishu", "notion", "notificationChannels", "iwencai", "twitter", "fred",
    "anysearch", "fuyao", "dataSourceCookies", "outboundProxy", "eastmoneyRateLimit", "backup",
    "scheduledTasks", "researchBudget", "marketDaily", "bot"] as CardKey[]) {
    dirty[key] = dirtyKeys.includes(key);
  }
  return {
    save: vi.fn(),
    reset: vi.fn(),
    dirty,
    isSaving: false,
  } as unknown as SettingsCards & { save: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> };
}

describe("SettingsDirtySummary", () => {
  it("renders nothing when no card is dirty", () => {
    const { container } = render(<SettingsDirtySummary cards={makeCards([])} onJumpToCard={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists every dirty card with its section and jumps on click", () => {
    const onJumpToCard = vi.fn();
    render(<SettingsDirtySummary cards={makeCards(["llm", "outboundProxy"])} onJumpToCard={onJumpToCard} />);

    fireEvent.click(screen.getByRole("button", { name: /未保存变更/ }));

    const panel = screen.getByTestId("settings-dirty-panel");
    expect(within(panel).getByText("大模型配置")).toBeInTheDocument();
    expect(within(panel).getByText("出站代理")).toBeInTheDocument();
    expect(within(panel).getByText("AI 模型配置")).toBeInTheDocument();
    expect(within(panel).getByText("数据源管理")).toBeInTheDocument();

    fireEvent.click(within(panel).getByText("出站代理"));
    expect(onJumpToCard).toHaveBeenCalledWith("data-sources", "settings-anchor-network");
  });

  it("saves and resets all dirty cards", () => {
    const cards = makeCards(["llm", "feishu"]);

    render(<SettingsDirtySummary cards={cards} onJumpToCard={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /未保存变更/ }));
    fireEvent.click(screen.getByRole("button", { name: /保存全部/ }));

    expect(cards.save).toHaveBeenCalledWith("llm");
    expect(cards.save).toHaveBeenCalledWith("feishu");

    fireEvent.click(screen.getByRole("button", { name: /未保存变更/ }));
    fireEvent.click(screen.getByRole("button", { name: /全部撤销/ }));
    fireEvent.click(screen.getByRole("button", { name: "确认撤销" }));

    expect(cards.reset).toHaveBeenCalledWith("llm");
    expect(cards.reset).toHaveBeenCalledWith("feishu");
  });
});
