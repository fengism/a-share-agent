import { useEffect } from "react";
import {
  useChatCapabilities,
  useChatCapabilityAvailability,
  useConfig,
} from "../../api/queries";
import { useChatStore } from "../../store/chatStore";

export function useChatCapabilitySelection() {
  const { data: config } = useConfig();
  const { data: chatCapabilities } = useChatCapabilities();
  const { data: chatCapabilityAvailability } = useChatCapabilityAvailability();
  const agentNames = useChatStore((state) => state.agentNames);
  const skillNames = useChatStore((state) => state.skillNames);
  const setAgentNames = useChatStore((state) => state.setAgentNames);
  const setSkillNames = useChatStore((state) => state.setSkillNames);

  useEffect(() => {
    if (agentNames === null || !chatCapabilities || !config) return;
    const enabledNames = new Set(
      chatCapabilities.agents
        .filter((agent) => {
          const status = chatCapabilityAvailability?.agents[agent.name]?.status;
          return (
            !config.disabled_chat_agents.includes(agent.name)
            && status !== "unavailable"
            && status !== "disabled"
          );
        })
        .map((agent) => agent.name),
    );
    const filteredNames = agentNames.filter((name) => enabledNames.has(name));
    if (
      filteredNames.length !== agentNames.length
      || filteredNames.some((name, index) => name !== agentNames[index])
    ) {
      setAgentNames(filteredNames);
    }
  }, [
    agentNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setAgentNames,
  ]);

  useEffect(() => {
    if (skillNames === null || !chatCapabilities || !config) return;
    const enabledNames = new Set(
      chatCapabilities.skills
        .filter((skill) => {
          const status = chatCapabilityAvailability?.skills[skill.name]?.status;
          return (
            !config.disabled_chat_skills.includes(skill.name)
            && status !== "unavailable"
            && status !== "disabled"
          );
        })
        .map((skill) => skill.name),
    );
    const filteredNames = skillNames.filter((name) => enabledNames.has(name));
    if (
      filteredNames.length !== skillNames.length
      || filteredNames.some((name, index) => name !== skillNames[index])
    ) {
      setSkillNames(filteredNames);
    }
  }, [
    skillNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setSkillNames,
  ]);

  return {
    agentNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setAgentNames,
    setSkillNames,
    skillNames,
  };
}
