import type {
  AgentPlan,
  AgentPlanStepUpdate,
  ChatDisplayMessage,
  ChatMessage,
  ToolCallInfo,
} from "../types/chat";
import type { SessionData, SessionMeta } from "./chatPersistence";
import type { ChatRegenerationRequest } from "./chatStoreHelpers";

export interface ChatState {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  agentNames: string[] | null;
  skillNames: string[] | null;
  isStreaming: boolean;
  abortController: AbortController | null;
  sessions: SessionMeta[];
  activeSessionId: string | null;
  sessionData: Record<string, SessionData>;
  createSession: () => string;
  setActiveSession: (sessionId: string) => void;
  setAgentNames: (agentNames: string[] | null) => void;
  setSkillNames: (skillNames: string[] | null) => void;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, title: string) => void;
  syncSessionTitle: () => void;
  addUserMessage: (content: string) => void;
  addAssistantMessage: (id: string) => void;
  appendToAssistant: (id: string, text: string) => void;
  addToolCall: (messageId: string, toolCall: ToolCallInfo) => void;
  updateToolResult: (
    messageId: string,
    toolCallId: string,
    result: string,
    isError: boolean,
  ) => void;
  setAssistantPlan: (messageId: string, plan: AgentPlan) => void;
  updateAssistantPlanStep: (messageId: string, update: AgentPlanStepUpdate) => void;
  setReasoningContent: (messageId: string, reasoningContent: string) => void;
  appendToReasoning: (messageId: string, text: string) => void;
  setAssistantStatus: (messageId: string, status: string) => void;
  setStreaming: (streaming: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
  clearChat: () => void;
  finalizeMessage: (messageId: string) => void;
  regenerateLastAssistant: () => ChatRegenerationRequest | null;
}
