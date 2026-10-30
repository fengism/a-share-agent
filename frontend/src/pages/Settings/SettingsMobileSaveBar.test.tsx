import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsMobileSaveBar from "./SettingsMobileSaveBar";
import type { CardKey } from "./cardSpecs";
import type { SettingsCards } from "./useSettingsForm";

const mocks = vi.hoisted(() => ({
  useMediaQuery: vi.fn(),
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: (query: string) => mocks.useMediaQuery(query),
}));

function makeCards(dirtyKeys: CardKey[]) {
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
  } as unknown as SettingsCards & { save: ReturnType<typeof vi.fn> };
}

describe("SettingsMobileSaveBar", () => {
  beforeEach(() => {
    mocks.useMediaQuery.mockReset();
  });

  it("stays hidden on wide screens", () => {
    mocks.useMediaQuery.mockReturnValue(false);
    const { container } = render(<SettingsMobileSaveBar cards={makeCards(["llm"])} onResetAll={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("stays hidden when nothing is dirty", () => {
    mocks.useMediaQuery.mockReturnValue(true);
    const { container } = render(<SettingsMobileSaveBar cards={makeCards([])} onResetAll={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("saves all dirty cards from the sticky bar", () => {
    mocks.useMediaQuery.mockReturnValue(true);
    const cards = makeCards(["llm", "outboundProxy"]);

    render(<SettingsMobileSaveBar cards={cards} onResetAll={vi.fn()} />);

    expect(screen.getByText("2 项未保存")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /保存全部/ }));

    expect(cards.save).toHaveBeenCalledWith("llm");
    expect(cards.save).toHaveBeenCalledWith("outboundProxy");
  });

  it("delegates reset-all to the page handler after confirmation", () => {
    mocks.useMediaQuery.mockReturnValue(true);
    const onResetAll = vi.fn();

    render(<SettingsMobileSaveBar cards={makeCards(["llm"])} onResetAll={onResetAll} />);
    fireEvent.click(screen.getByRole("button", { name: /撤销/ }));
    fireEvent.click(screen.getByRole("button", { name: "确认撤销" }));

    expect(onResetAll).toHaveBeenCalledTimes(1);
  });
});
