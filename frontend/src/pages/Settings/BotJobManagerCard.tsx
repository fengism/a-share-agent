import { ReloadOutlined, RetweetOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Card, Space, Tag, message } from "antd";
import { useBotJobs, useRetryBotJob } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { BotAdminJob } from "../../types/settings";

export default function BotJobManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const { data, isLoading, error, refetch, isFetching } = useBotJobs(true);
  const retryJob = useRetryBotJob();
  const jobs = data?.jobs ?? [];

  const handleRetry = (job: BotAdminJob) => {
    retryJob.mutate(job.id, {
      onSuccess: () => {
        message.success(`任务 ${job.id.slice(0, 8)} 已重新入队`);
        refetch();
      },
      onError: (retryError: Error) => message.error(`重试失败: ${retryError.message}`),
    });
  };

  return (
    <Card
      title={<span><WarningOutlined style={{ marginRight: 8 }} />Bot 失败任务</span>}
      extra={(
        <Button
          size="small"
          icon={<ReloadOutlined />}
          loading={isFetching}
          onClick={() => refetch()}
        >
          刷新
        </Button>
      )}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <Space wrap style={{ marginBottom: 12 }}>
        <Tag style={semanticTagStyle("info")}>等待 {data?.counts.pending ?? 0}</Tag>
        <Tag style={semanticTagStyle("primary")}>执行中 {data?.counts.running ?? 0}</Tag>
        <Tag style={semanticTagStyle("down")}>成功 {data?.counts.succeeded ?? 0}</Tag>
        <Tag style={semanticTagStyle("up")}>失败 {data?.counts.failed ?? 0}</Tag>
      </Space>
      <SectionDataState
        isLoading={isLoading && jobs.length === 0}
        error={jobs.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && jobs.length === 0}
        emptyText="暂无失败任务"
        errorTitle="Bot 任务加载失败"
        minHeight={120}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {jobs.map((job) => (
            <div
              key={job.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 8,
                border: `1px solid ${colors.border}`,
                background: colors.hoverBg,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ color: colors.textPrimary }}>
                  <code>{job.id.slice(0, 8)}</code>
                  <span style={{ marginLeft: 8 }}>/ {job.command_name || "unknown"}</span>
                  <Tag style={{ ...semanticTagStyle("up"), marginLeft: 8 }}>失败</Tag>
                </div>
                <div style={{ color: colors.textMuted, fontSize: 12, marginTop: 4 }}>
                  用户 {job.request_user_id || "未知"} · 尝试 {job.attempts}/{job.max_attempts}
                  {job.last_error ? ` · ${job.last_error}` : ""}
                  {` · ${new Date(job.updated_at * 1000).toLocaleString()}`}
                </div>
              </div>
              <Button
                size="small"
                type="primary"
                icon={<RetweetOutlined />}
                loading={retryJob.isPending && retryJob.variables === job.id}
                onClick={() => handleRetry(job)}
              >
                重试
              </Button>
            </div>
          ))}
        </div>
      </SectionDataState>
    </Card>
  );
}
