import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SettingsMobileRecordList from "./SettingsMobileRecordList";

interface Row {
  id: number;
  name: string;
  status: string;
  detail: string;
}

const rows: Row[] = [
  { id: 1, name: "alice", status: "正常", detail: "首次登录" },
  { id: 2, name: "bob", status: "已禁用", detail: "多次失败" },
];

describe("SettingsMobileRecordList", () => {
  it("renders one card per record with primary and labelled detail rows", () => {
    render(
      <SettingsMobileRecordList
        items={rows}
        rowKey={(row) => row.id}
        ariaLabel="示例记录列表"
        fields={[
          { label: "名称", primary: true, render: (row) => row.name },
          { label: "状态", render: (row) => row.status },
          { label: "说明", fullWidth: true, render: (row) => row.detail },
        ]}
      />,
    );

    const list = screen.getByRole("list", { name: "示例记录列表" });
    const cards = within(list).getAllByRole("listitem");
    expect(cards).toHaveLength(2);

    expect(within(cards[0]).getByText("alice")).toBeInTheDocument();
    expect(within(cards[0]).getByText("状态")).toBeInTheDocument();
    expect(within(cards[0]).getByText("正常")).toBeInTheDocument();
    expect(within(cards[0]).getByText("首次登录")).toBeInTheDocument();
    expect(within(cards[1]).getByText("多次失败")).toBeInTheDocument();
    // 主字段不再重复渲染为键值行
    expect(within(cards[0]).queryByText("名称")).not.toBeInTheDocument();
  });

  it("renders optional trailing content and actions", () => {
    render(
      <SettingsMobileRecordList
        items={rows}
        rowKey={(row) => row.id}
        ariaLabel="示例记录列表"
        fields={[{ label: "名称", primary: true, render: (row) => row.name }]}
        trailing={(row) => <span>#{row.id}</span>}
        actions={(row) => <button type="button">编辑 {row.name}</button>}
      />,
    );

    const list = screen.getByRole("list", { name: "示例记录列表" });
    expect(within(list).getAllByText(/^#\d$/)).toHaveLength(2);
    expect(within(list).getByRole("button", { name: "编辑 bob" })).toBeInTheDocument();
  });
});
