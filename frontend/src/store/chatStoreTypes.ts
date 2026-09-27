import type { ReasoningSource } from "../types/chat";
import type {
  AgentToolResultSummary,
  AgentPlan,
  AgentPlanStepUpdate,
  ChatDisplayMessage,
  ChatMessage,
  ChatProcessUpdate,
  ChatProcessOutcome,
  ToolCallInfo,
} from "../types/chat";
import type { SessionData, SessionMeta } from "./chatPersistence";
import type { PersistedChatState } from "./chatPersistence";
import type { ChatRegenerationRequest } from "./chatStoreHelpers";

export type ChatSyncStatus = "loading" | "synced" | "error";

export interface ChatState {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  agentNames: string[] | null;
  skillNames: string[] | null;
  isStreaming: boolean;
  activeRunSessionId: string | null;
  activeRunLabel: string | null;
  syncStatus: ChatSyncStatus;
  abortController: AbortController | null;
  sessions: SessionMeta[];
  activeSessionId: string | null;
  sessionData: Record<string, SessionData>;
  hydrateSessions: (snapshot: PersistedChatState) => void;
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
    resultSummary?: AgentToolResultSummary,
  ) => void;
  setAssistantPlan: (messageId: string, plan: AgentPlan) => void;
  updateAssistantPlanStep: (messageId: string, update: AgentPlanStepUpdate) => void;
  setReasoningContent: (messageId: string, reasoningContent: string) => void;
  appendToReasoning: (messageId: string, text: string, source?: ReasoningSource) => void;
  addAssistantProcessUpdate: (messageId: string, update: ChatProcessUpdate) => void;
  setAssistantProcessOutcome: (messageId: string, outcome: ChatProcessOutcome) => void;
  setAssistantStatus: (messageId: string, status: string) => void;
  setStreaming: (streaming: boolean) => void;
  setActiveRun: (sessionId: string | null, label: string | null) => void;
  setSyncStatus: (status: ChatSyncStatus) => void;
  setAbortController: (controller: AbortController | null) => void;
  clearChat: () => void;
  finalizeMessage: (messageId: string, outcome?: ChatProcessOutcome) => void;
  regenerateLastAssistant: () => ChatRegenerationRequest | null;
  editUserMessage: (messageId: string, content: string) => ChatRegenerationRequest | null;
}
