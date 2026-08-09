import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssistantProcess } from "./AssistantProcess";

describe("AssistantProcess", () => {
  it("renders the live agent plan and step statuses", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-plan",
          role: "assistant",
          content: "",
          isStreaming: true,
          plan: {
            summary: "问题涉及技术面和风险评估",
            steps: [
              {
                id: "technical",
                title: "技术分析",
                description: "分析价格趋势",
                dependencies: [],
                status: "running",
                attempt: 1,
              },
              {
                id: "risk",
                title: "风险分析",
                description: "识别潜在风险",
                dependencies: ["technical"],
                status: "pending",
                attempt: 0,
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("问题涉及技术面和风险评估")).toBeInTheDocument();
    expect(screen.getByText("技术分析")).toBeInTheDocument();
    expect(screen.getByText("执行中")).toBeInTheDocument();
    expect(screen.getByText("风险分析")).toBeInTheDocument();
    expect(screen.getByText("等待执行")).toBeInTheDocument();
  });
});
