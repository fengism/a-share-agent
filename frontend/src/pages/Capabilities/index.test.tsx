import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChatCapabilitiesResponse } from "../../types/capabilities";
import CapabilitiesPage from ".";

const mocks = vi.hoisted(() => ({ updateConfig: vi.fn() }));

const capabilities: ChatCapabilitiesResponse = {
  skills: [{
    name: "stock_analysis",
    description: "个股分析",
    triggers: ["股票代码"],
    tool_names: [],
    rules: ["分析个股"],
    exclusions: [],
    priority: 30,
  }],
  agents: [],
  tools: [],
  unassigned_tools: [],
};

vi.mock("../../api/queries", () => ({
  useChatCapabilities: () => ({
    data: capabilities,
    error: null,
    isFetching: false,
    isLoading: false,
    refetch: vi.fn(),
  }),
  useConfig: () => ({
    data: { disabled_chat_skills: [], disabled_chat_agents: [] },
    error: null,
    isLoading: false,
    refetch: vi.fn(),
  }),
  useChatCapabilityAvailability: () => ({
    data: undefined,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useUpdateConfig: () => ({ mutate: mocks.updateConfig, isPending: false }),
}));

describe("CapabilitiesPage", () => {
  it("owns account capability preferences and saves their draft", () => {
    render(<CapabilitiesPage />);

    expect(screen.getByText("账号能力配置")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /保存账号能力/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("switch", { name: "个股分析 Skill" }));
    expect(screen.getByText("未保存")).toBeInTheDocument();
    const saveButton = screen.getByRole("button", { name: /保存账号能力/ });
    expect(saveButton).toBeEnabled();
    fireEvent.click(saveButton);

    expect(mocks.updateConfig).toHaveBeenCalledWith(
      { disabled_chat_skills: ["stock_analysis"], disabled_chat_agents: [] },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });

  it("separates account preferences from the capability catalog", async () => {
    render(<CapabilitiesPage />);

    fireEvent.click(screen.getByRole("tab", { name: "能力目录" }));
    expect(screen.queryByText("账号能力配置")).not.toBeInTheDocument();
    expect(await screen.findByText("Skill 视图 (1)")).toBeInTheDocument();
  });
});
