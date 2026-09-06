import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { IndustryChainEvidence } from "../../types/stock";
import EvidenceLinkedText from "./EvidenceLinkedText";

const catalog: IndustryChainEvidence[] = [
  {
    evidence_id: "ev_report",
    tool_name: "fetch_url",
    title: "人形机器人产业发展报告",
    source_urls: ["https://example.com/reports/humanoid"],
  },
  {
    evidence_id: "ev_domain",
    tool_name: "web_search",
    source_urls: ["https://www.example.org/news/1"],
  },
  {
    evidence_id: "ev_no_url",
    tool_name: "fetch_url",
    title: "无链接报告",
    source_urls: [],
  },
];

describe("EvidenceLinkedText", () => {
  it("replaces a known evidence id with its title link", () => {
    const { container } = render(
      <EvidenceLinkedText text="核心结论（证据 ev_report）成立" evidenceCatalog={catalog} />,
    );

    expect(container.textContent).toBe("核心结论（人形机器人产业发展报告）成立");
    expect(container.textContent).not.toContain("ev_report");
    expect(screen.getByRole("link", { name: "人形机器人产业发展报告" })).toHaveAttribute(
      "href",
      "https://example.com/reports/humanoid",
    );
  });

  it("replaces multiple references and uses the hostname when a title is absent", () => {
    render(<EvidenceLinkedText text="证据 ev_report 与 ev_domain 相互印证" evidenceCatalog={catalog} />);

    expect(screen.getByRole("link", { name: "人形机器人产业发展报告" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "example.org" })).toHaveAttribute(
      "href",
      "https://www.example.org/news/1",
    );
    expect(screen.queryByText(/ev_(report|domain)/)).not.toBeInTheDocument();
  });

  it("hides internal ids when evidence or its URL is unavailable", () => {
    const { container } = render(
      <EvidenceLinkedText text="证据 ev_no_url；证据 ev_unknown" evidenceCatalog={catalog} />,
    );

    expect(screen.getAllByText("相关证据")).toHaveLength(2);
    expect(container.textContent).not.toContain("ev_no_url");
    expect(container.textContent).not.toContain("ev_unknown");
  });

  it("does not create links for unsafe URLs", () => {
    const { container } = render(
      <EvidenceLinkedText
        text="证据 ev_unsafe"
        evidenceCatalog={[{
          evidence_id: "ev_unsafe",
          tool_name: "fetch_url",
          title: "不安全来源",
          source_urls: ["javascript:alert(1)"],
        }]}
      />,
    );

    expect(screen.getByText("相关证据")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
    expect(container.textContent).not.toContain("ev_unsafe");
  });
});
