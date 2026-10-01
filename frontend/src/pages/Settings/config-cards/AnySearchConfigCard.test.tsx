import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AnySearchConfigCard from "./AnySearchConfigCard";

describe("AnySearchConfigCard", () => {
  it("edits multiple keys and delegates saving", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    render(
      <AnySearchConfigCard
        form={{ anysearch_api_key: "key-1,key-2" }}
        onChange={onChange}
        onSave={onSave}
        isSaving={false}
        configured
      />,
    );

    expect(screen.getByText(/普通网页搜索会自动优先使用 AnySearch/)).toBeInTheDocument();
    expect(screen.getByLabelText("AnySearch API Key")).toHaveAttribute(
      "placeholder",
      "已配置；输入新的 Key 以覆盖现有配置",
    );
    fireEvent.change(screen.getByLabelText("AnySearch API Key"), {
      target: { value: "key-3,key-4" },
    });
    expect(onChange).toHaveBeenCalledWith({ anysearch_api_key: "key-3,key-4" });

    fireEvent.click(screen.getByRole("button", { name: /保存 AnySearch 配置/ }));
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
