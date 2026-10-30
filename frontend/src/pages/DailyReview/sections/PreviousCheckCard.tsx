import { CheckCircleFilled, CloseCircleFilled, MinusCircleOutlined } from "@ant-design/icons";
import { Card, Progress, Space, Tag, Typography } from "antd";
import { useColors } from "../../../styles/ui";
import { formatSignedPct, type DailyReviewPayload } from "../reviewView";
import "./daily-review-sections.css";

const { Paragraph, Text } = Typography;

type CheckPayload = NonNullable<DailyReviewPayload["previous_review_check"]>;

interface PreviousCheckCardProps {
  check: CheckPayload;
  accuracy: number | null;
}

/**
 * 昨日复盘自检。
 *
 * 复盘真正的价值在"昨天的判断今天对不对"，所以把它从普通卡片里的几个 Tag
 * 升格为：命中率环形 + 逐项对照表（观察锚点 / 实际表现 / 是否命中）。
 */
export default function PreviousCheckCard({ check, accuracy }: PreviousCheckCardProps) {
  const c = useColors();
  const watchlist = check.watchlist ?? [];
  const indices = check.indices ?? [];
  const delta = check.limit_up_delta;

  return (
    <Card className="daily-review-check-card" size="small">
      <div className="daily-review-check-card__head">
        <div className="daily-review-check-card__meta">
          <Text type="secondary">
            {check.review_date || "上一交易日"} 复盘 → {check.verified_date || "次日"} 实际表现
          </Text>
          <Space size={6} wrap>
            {check.previous_stage ? <Tag color="purple">昨日周期：{check.previous_stage}</Tag> : null}
            {delta !== null && delta !== undefined ? (
              <Tag color={delta >= 0 ? "red" : "green"}>
                涨停家数 {check.previous_limit_up_count ?? "-"} → {check.limit_up_count ?? "-"}
              </Tag>
            ) : null}
          </Space>
        </div>
        {accuracy !== null ? (
          <Progress
            type="circle"
            size={64}
            percent={Math.round(accuracy * 100)}
            strokeColor={c.primary}
            trailColor="var(--c-border)"
            format={(percent) => <span className="daily-review-check-card__percent">{percent}%</span>}
          />
        ) : (
          <Tag>暂无可核验行情</Tag>
        )}
      </div>

      {watchlist.length ? (
        <div className="daily-review-check-card__table-wrap">
          <table className="daily-review-check-card__table">
            <caption className="daily-review-check-card__caption">观察锚点逐项对照</caption>
            <thead>
              <tr>
                <th scope="col">观察锚点</th>
                <th scope="col">实际表现</th>
                <th scope="col">结论</th>
              </tr>
            </thead>
            <tbody>
              {watchlist.map((item) => {
                const verdict = item.missing ? "missing" : item.hit ? "hit" : "miss";
                return (
                  <tr key={`${item.name}-${item.code ?? ""}`} data-verdict={verdict}>
                    <th scope="row">
                      <span className="daily-review-check-card__name">{item.name}</span>
                      {item.code ? <Text type="secondary"> {item.code}</Text> : null}
                    </th>
                    <td className="financial-num">
                      {item.missing ? (
                        <Text type="secondary">次日行情缺失</Text>
                      ) : (
                        <span style={{ color: (item.change_pct ?? 0) >= 0 ? c.up : c.down }}>
                          {formatSignedPct(item.change_pct)}
                          {item.limit_up ? <Tag color="volcano" style={{ marginLeft: 6 }}>涨停</Tag> : null}
                        </span>
                      )}
                    </td>
                    <td>
                      {verdict === "hit" ? (
                        <Tag color="success" icon={<CheckCircleFilled />}>命中</Tag>
                      ) : verdict === "miss" ? (
                        <Tag color="error" icon={<CloseCircleFilled />}>未命中</Tag>
                      ) : (
                        <Tag icon={<MinusCircleOutlined />}>无数据</Tag>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {indices.length ? (
        <div className="daily-review-check-card__indices">
          {indices.map((item) => (
            <Text key={`${item.name}-${item.code ?? ""}`} type="secondary">
              {item.name}：{formatSignedPct(item.previous_change_pct)} → {formatSignedPct(item.change_pct)}
            </Text>
          ))}
        </div>
      ) : null}

      {check.note ? (
        <Paragraph type="secondary" className="daily-review-check-card__note">
          {check.note}
        </Paragraph>
      ) : null}
    </Card>
  );
}
