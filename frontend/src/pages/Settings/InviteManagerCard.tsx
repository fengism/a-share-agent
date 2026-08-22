import { useState } from "react";
import { CopyOutlined, DeleteOutlined, PlusOutlined, TeamOutlined } from "@ant-design/icons";
import { Button, Card, message, Popconfirm, Select, Space, Tag } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { useCreateInvite, useInvites, useRevokeInvite } from "../../api/queries";
import { queryKeys } from "../../api/queryKeys";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { InviteItem } from "../../types/auth";

export default function InviteManagerCard() {
  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const colors = useColors();
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const queryClient = useQueryClient();
  const { data: invites = [], isLoading, error, refetch } = useInvites(true);
  const createInvite = useCreateInvite();
  const revokeInvite = useRevokeInvite();
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>();

  const refresh = () => queryClient.invalidateQueries({ queryKey: queryKeys.settings.invites });

  const handleGenerate = () => {
    createInvite.mutate(expiresInDays, {
      onSuccess: () => {
        refresh();
        message.success("已生成新的邀请码");
      },
      onError: (error: Error) => message.error(`生成失败: ${error.message}`),
    });
  };

  const handleRevoke = (code: string) => {
    revokeInvite.mutate(code, {
      onSuccess: () => {
        refresh();
        message.success("邀请码已撤销");
      },
      onError: (error: Error) => message.error(`撤销失败: ${error.message}`),
    });
  };

  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      message.success("邀请码已复制");
    } catch {
      message.warning("复制失败，请手动选择复制");
    }
  };

  const statusTag = (invite: InviteItem) => {
    if (invite.used) return <Tag>已使用</Tag>;
    if (invite.expired) return <Tag style={semanticTagStyle("up")}>已过期</Tag>;
    return <Tag style={semanticTagStyle("down")}>未使用</Tag>;
  };

  const inviteControls = (
    <Space wrap style={{ width: isNarrow ? "100%" : undefined }}>
      <Select
        size="small"
        value={expiresInDays ?? 0}
        style={{ width: isNarrow ? "100%" : 128, minWidth: 128, flex: isNarrow ? 1 : undefined }}
        onChange={(value) => setExpiresInDays(value === 0 ? undefined : value)}
        options={[
          { value: 0, label: "永不过期" },
          { value: 1, label: "1 天后过期" },
          { value: 7, label: "7 天后过期" },
          { value: 30, label: "30 天后过期" },
        ]}
      />
      <Button type="primary" icon={<PlusOutlined />} onClick={handleGenerate} loading={createInvite.isPending}>
        生成邀请码
      </Button>
    </Space>
  );

  return (
    <Card
      title={<span><TeamOutlined style={{ marginRight: 8 }} />邀请码管理</span>}
      extra={isNarrow ? undefined : inviteControls}
      style={{ ...cardStyle, marginBottom: 16 }}
      styles={{ body: sectionCardBodyStyle }}
    >
      <div style={{ fontSize: 12, color: colors.textMuted, marginBottom: 12 }}>
        新用户注册需填写有效且未使用的邀请码；每个邀请码仅可使用一次。可为邀请码设置过期时间，未使用的邀请码可随时撤销。
      </div>
      {isNarrow && <div style={{ marginBottom: 12 }}>{inviteControls}</div>}
      <SectionDataState
        isLoading={isLoading && invites.length === 0}
        error={invites.length > 0 ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && invites.length === 0}
        emptyText="暂无邀请码，可通过上方操作生成"
        errorTitle="邀请码加载失败"
        minHeight={120}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {invites.map((invite) => (
            <div
              key={invite.code}
              style={{
                display: "flex",
                alignItems: isNarrow ? "stretch" : "center",
                flexDirection: isNarrow ? "column" : "row",
                justifyContent: "space-between",
                gap: 8,
                padding: "8px 12px",
                background: colors.hoverBg,
                border: `1px solid ${colors.border}`,
                borderRadius: 8,
              }}
            >
              <div style={{ minWidth: 0 }}>
                <code style={{ fontFamily: "monospace", fontSize: 13, color: colors.textPrimary, wordBreak: "break-all" }}>
                  {invite.code}
                </code>
                <div style={{ fontSize: 11, color: colors.textMuted, marginTop: 2 }}>
                  {invite.expires_at ? `过期时间：${invite.expires_at}` : "永不过期"}
                </div>
              </div>
              <Space wrap>
                {statusTag(invite)}
                {!invite.used && (
                  <Button size="small" icon={<CopyOutlined />} onClick={() => copyCode(invite.code)}>
                    复制
                  </Button>
                )}
                {!invite.used && (
                  <Popconfirm
                    title="撤销该邀请码？"
                    description="撤销后将无法用于注册。"
                    okText="撤销"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                    onConfirm={() => handleRevoke(invite.code)}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} loading={revokeInvite.isPending}>
                      撤销
                    </Button>
                  </Popconfirm>
                )}
              </Space>
            </div>
          ))}
        </div>
      </SectionDataState>
    </Card>
  );
}
