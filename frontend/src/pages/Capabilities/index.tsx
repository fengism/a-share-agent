import { lazy, Suspense, useEffect, useState } from "react";
import { message, Typography } from "antd";
import {
  useChatCapabilities,
  useChatCapabilityAvailability,
  useConfig,
  useUpdateConfig,
} from "../../api/queries";
import RefreshBadge from "../../components/RefreshBadge";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import type { ConfigUpdate } from "../../types/settings";
import SkillAgentConfigCard from "./SkillAgentConfigCard";
import "./capabilities.css";

const CapabilityCatalog = lazy(() => import("./CapabilityCatalog"));
const { Paragraph, Title } = Typography;

function CatalogFallback() {
  return (
    <div role="status" aria-live="polite" style={{ minHeight: 320, padding: 24 }}>
      正在加载能力目录...
    </div>
  );
}

export default function CapabilitiesPage() {
  const { pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
  const { data, error, isFetching, isLoading, refetch } = useChatCapabilities();
  const {
    data: config,
    error: configError,
    isLoading: isLoadingConfig,
    refetch: refetchConfig,
  } = useConfig();
  const {
    data: availability,
    isFetching: isCheckingAvailability,
    refetch: refetchAvailability,
  } = useChatCapabilityAvailability();
  const updateConfig = useUpdateConfig();
  const [section, setSection] = useState<"account" | "catalog">("account");
  const [capabilityPatch, setCapabilityPatch] = useState<ConfigUpdate>({});

  const disabledSkillNames = capabilityPatch.disabled_chat_skills
    ?? config?.disabled_chat_skills
    ?? [];
  const disabledAgentNames = capabilityPatch.disabled_chat_agents
    ?? config?.disabled_chat_agents
    ?? [];
  const hasUnsavedCapabilityChanges = (
    disabledSkillNames.join("\0") !== (config?.disabled_chat_skills ?? []).join("\0")
    || disabledAgentNames.join("\0") !== (config?.disabled_chat_agents ?? []).join("\0")
  );

  useEffect(() => {
    if (!hasUnsavedCapabilityChanges) return undefined;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedCapabilityChanges]);

  const handleCapabilityChange = (patch: ConfigUpdate) => {
    setCapabilityPatch((current) => ({ ...current, ...patch }));
  };

  const handleSaveCapabilities = () => {
    updateConfig.mutate(
      { disabled_chat_skills: disabledSkillNames, disabled_chat_agents: disabledAgentNames },
      {
        onSuccess: () => {
          setCapabilityPatch({});
          void refetchAvailability();
          message.success("账号能力配置已保存");
        },
        onError: (saveError: Error) => message.error(`保存失败: ${saveError.message}`),
      },
    );
  };

  return (
    <div style={pageContainerStyle} className="capability-page">
      <div className="capability-page-header">
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>能力中心</Title>
          </div>
          <Paragraph style={pageDescriptionStyle}>
            管理当前账号的 Chat 能力，并查看 Skill 路由、Tool 参数与运行策略。
          </Paragraph>
        </div>
        {isFetching && !isLoading && <RefreshBadge label="正在同步" />}
      </div>

      <SectionDataState
        isLoading={isLoading}
        error={error}
        onRetry={() => refetch()}
        errorTitle="能力清单加载失败"
        isEmpty={!isLoading && !error && !data}
      >
        {data && (
          <ResponsiveSectionNav
            items={[
              {
                key: "account",
                label: hasUnsavedCapabilityChanges ? "我的能力 · 未保存" : "我的能力",
                mobileLabel: hasUnsavedCapabilityChanges ? "我的能力（未保存）" : "我的能力",
                children: (
                  <SkillAgentConfigCard
                    capabilities={data}
                    availability={availability}
                    disabledSkillNames={disabledSkillNames}
                    disabledAgentNames={disabledAgentNames}
                    onChange={handleCapabilityChange}
                    onSave={handleSaveCapabilities}
                    isSaving={updateConfig.isPending}
                    isLoading={isLoadingConfig}
                    error={configError}
                    onRetry={() => refetchConfig()}
                    isCheckingAvailability={isCheckingAvailability}
                    onCheckAvailability={() => refetchAvailability()}
                    hasChanges={hasUnsavedCapabilityChanges}
                  />
                ),
              },
              {
                key: "catalog",
                label: "能力目录",
                children: (
                  <Suspense fallback={<CatalogFallback />}>
                    <CapabilityCatalog capabilities={data} />
                  </Suspense>
                ),
              },
            ]}
            activeKey={section}
            onChange={(key) => setSection(key as "account" | "catalog")}
            ariaLabel="能力中心视图"
          />
        )}
      </SectionDataState>
    </div>
  );
}
