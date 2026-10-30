import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { CodeBlock } from "./CodeBlock";

describe("CodeBlock", () => {
  const writeTextMock = vi.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });
  });

  it("renders code block with language badge and copies text", async () => {
    const code = "def strategy(kline):\n    return kline.macd > 0";
    render(
      <CodeBlock>
        <code className="language-python">{code}</code>
      </CodeBlock>,
    );

    expect(screen.getByText("PYTHON")).toBeInTheDocument();
    expect(screen.getByText("量化策略片段")).toBeInTheDocument();
    expect(screen.getByText(/def strategy/)).toBeInTheDocument();

    const copyBtn = screen.getByRole("button", { name: /复制/ });
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith(code);
    });
  });

  it("renders fallback CODE badge when no language specified", () => {
    render(
      <CodeBlock>
        <code>SELECT * FROM stock_pool</code>
      </CodeBlock>,
    );

    expect(screen.getByText("CODE")).toBeInTheDocument();
    expect(screen.getByText("SELECT * FROM stock_pool")).toBeInTheDocument();
  });
});
