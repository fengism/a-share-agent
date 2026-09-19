import { HistoryOutlined } from "@ant-design/icons";
import { Collapse, Empty, Tag } from "antd";
import type { IndustryChainChangeItem, IndustryChainChangeSet } from "../../types/stock";

const TYPE_META: Record<IndustryChainChangeItem["change_type"], { label: string; color: string }> = {
  added: { label: "新增", color: "success" },
  removed: { label: "移除", color: "default" },
  updated: { label: "更新", color: "processing" },
};

function ChangeDetail({ item }: { item: IndustryChainChangeItem }) {
  if (item.change_type === "updated") {
    return (
      <div className="industry-report-changes__comparison">
        {item.before && <p><span>此前</span>{item.before}</p>}
        {item.after && <p><span>当前</span>{item.after}</p>}
      </div>
    );
  }
  return <p className="industry-report-changes__detail">{item.after || item.before || item.detail}</p>;
}

export default function IndustryReportChanges({ changes }: { changes?: IndustryChainChangeSet }) {
  if (!changes?.previous_archive_id) return null;
  const summary = `新增 ${changes.added_count} · 更新 ${changes.updated_count} · 移除 ${changes.removed_count}`;
  return (
    <section className="industry-report-changes" aria-label="较上一版变化">
      <header>
        <div><HistoryOutlined /><strong>较上一版变化</strong></div>
        <span>{summary}</span>
      </header>
      {!changes.has_changes || changes.items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="核心信息与上一版一致" />
      ) : (
        <Collapse
          ghost
          size="small"
          items={[{
            key: "changes",
            label: `查看 ${changes.items.length} 项变化`,
            children: (
              <ul>
                {changes.items.map((item, index) => (
                  <li key={`${item.category}-${item.change_type}-${item.title}-${index}`}>
                    <div className="industry-report-changes__title">
                      <Tag color={TYPE_META[item.change_type].color}>{TYPE_META[item.change_type].label}</Tag>
                      <strong>{item.title}</strong>
                    </div>
                    <ChangeDetail item={item} />
                  </li>
                ))}
              </ul>
            ),
          }]}
        />
      )}
    </section>
  );
}
