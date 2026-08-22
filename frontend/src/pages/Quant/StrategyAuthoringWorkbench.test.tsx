import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StrategyAuthoringWorkbench from "./StrategyAuthoringWorkbench";

const mocks = vi.hoisted(() => ({
  generate: vi.fn(),
  update: vi.fn(),
  validate: vi.fn(),
  backtest: vi.fn(),
  publish: vi.fn(),
  drafts: [] as unknown[],
}));

const draft = {
  id: "draft-one",
  created_by: 1,
  prompt: "生成一个双均线策略",
  definition_hash: `sha256:${"a".repeat(64)}`,
  status: "backtested" as const,
  definition: {
    api_version: "quant.strategy/v1" as const,
    key: "generated_ma_cross",
    version: "1.0.0",
    enabled: true,
    name: "在线双均线",
    description: "短期均线上穿长期均线时入场，下穿时退出",
    scenario: "趋势行情",
    risk_level: "medium" as const,
    parameters: {},
    constraints: [],
    indicators: {},
    signals: {
      entry: { operator: "greater_than" as const, left: "close", right: 0, operands: [] },
      exit: { operator: "less_than" as const, left: "close", right: 0, operands: [] },
    },
  },
  validation: { valid: true, definition_hash: `sha256:${"a".repeat(64)}`, warnings: [] },
  quality_gate: {
    passed: true,
    run_status: "succeeded",
    definition_hash: `sha256:${"a".repeat(64)}`,
    minimum_trade_count: 1,
    maximum_drawdown_pct: 80,
    trade_count: 4,
    max_drawdown: -12,
    errors: [],
  },
  created_at: 1,
  updated_at: 2,
};

vi.mock("../../api/queries", () => ({
  useQuantStrategyDrafts: () => ({ data: mocks.drafts, isLoading: false }),
  useQuantStrategyRegistryStatus: () => ({
    data: { generation: 3, published_directory: "/data/quant-strategies-published" },
  }),
  useGenerateQuantStrategyDraft: () => ({ mutateAsync: mocks.generate, isPending: false }),
  useUpdateQuantStrategyDraft: () => ({ mutateAsync: mocks.update, isPending: false }),
  useValidateQuantStrategyDraft: () => ({ mutateAsync: mocks.validate, isPending: false }),
  useBacktestQuantStrategyDraft: () => ({ mutateAsync: mocks.backtest, isPending: false }),
  usePublishQuantStrategyDraft: () => ({ mutateAsync: mocks.publish, isPending: false }),
}));

describe("StrategyAuthoringWorkbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.generate.mockResolvedValue(draft);
    mocks.update.mockResolvedValue(draft);
    mocks.validate.mockResolvedValue(draft);
    mocks.publish.mockResolvedValue({ ...draft, status: "published" });
    mocks.drafts = [draft];
  });

  it("blocks validation and publication while the definition has unsaved edits", async () => {
    mocks.drafts = [{ ...draft, status: "validated", quality_gate: null }];
    render(<StrategyAuthoringWorkbench onBacktestCreated={vi.fn()} />);

    const editor = await screen.findByPlaceholderText("生成草稿后可在这里编辑完整 StrategyDefinition JSON");
    expect(editor).toBeEnabled();

    fireEvent.change(editor, { target: { value: "{}" } });

    expect(screen.getByText("有未保存修改")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /编译校验/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /发布策略/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /使用当前快照试跑/ })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /保存定义/ }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({
      draftId: draft.id,
      expectedDefinitionHash: draft.definition_hash,
      definition: {},
    }));
  });

  it("publishes only after the explicit confirmation", async () => {
    render(<StrategyAuthoringWorkbench onBacktestCreated={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: /发布策略/ }));
    expect(mocks.publish).not.toHaveBeenCalled();
    fireEvent.click(await screen.findByRole("button", { name: "确认发布" }));

    await waitFor(() => expect(mocks.publish).toHaveBeenCalledWith({
      draftId: draft.id,
      expectedDefinitionHash: draft.definition_hash,
    }));
  });

  it("shows the durable publication path for a published draft", async () => {
    mocks.drafts = [{
      ...draft,
      status: "published",
      published_path: "/data/quant-strategies-published/generated_ma_cross-1.0.0.yaml",
    }];

    render(<StrategyAuthoringWorkbench onBacktestCreated={vi.fn()} />);

    expect(await screen.findByText(/generated_ma_cross-1\.0\.0\.yaml/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /发布策略/ })).toBeDisabled();
  });

  it("sends the administrator prompt to the generation mutation", async () => {
    render(<StrategyAuthoringWorkbench onBacktestCreated={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText(/例如：使用 20 日和 60 日均线/), {
      target: { value: "生成一个 20 日均线上穿 60 日均线后买入的策略" },
    });
    fireEvent.click(screen.getByRole("button", { name: /生成受限策略草稿/ }));

    await waitFor(() => expect(mocks.generate).toHaveBeenCalledWith(
      "生成一个 20 日均线上穿 60 日均线后买入的策略",
    ));
  });
});
