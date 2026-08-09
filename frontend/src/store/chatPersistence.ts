import type { ChatDisplayMessage, ChatMessage } from "../types/chat";

export const CHAT_STORAGE_LIMIT = 4 * 1024 * 1024;

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

export interface SessionData {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  agentNames?: string[] | null;
  skillNames?: string[] | null;
}

export interface PersistedChatState {
  sessions: SessionMeta[];
  sessionData: Record<string, SessionData>;
  activeSessionId: string | null;
}

interface PendingPersist extends PersistedChatState {
  storage: Storage;
  userId: number;
}

interface CompactedChatData {
  sessionData: Record<string, SessionData>;
  serialized: string;
  compacted: boolean;
  fits: boolean;
}

type Warn = (message: string, error?: unknown) => void;

const defaultWarn: Warn = (message, error) => {
  console.warn(`[chatPersistence] ${message}`, error);
};

export function emptyPersistedChatState(): PersistedChatState {
  return { sessions: [], sessionData: {}, activeSessionId: null };
}

export function chatStorageKey(userId: number): string {
  return `chat-sessions:user:${userId}`;
}

function readJson(storage: Storage, key: string, warn: Warn): unknown {
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    warn(`读取 ${key} 失败，已回退为空数据`, error);
    return null;
  }
}

function parseSessions(value: unknown): SessionMeta[] {
  if (!Array.isArray(value)) return [];
  return value.filter((session): session is SessionMeta => (
    typeof session === "object"
    && session !== null
    && "id" in session
    && typeof session.id === "string"
    && "title" in session
    && typeof session.title === "string"
    && "createdAt" in session
    && typeof session.createdAt === "number"
    && "updatedAt" in session
    && typeof session.updatedAt === "number"
  ));
}

function parseSessionData(value: unknown): Record<string, SessionData> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
  const parsed: Record<string, SessionData> = {};
  for (const [sessionId, entry] of Object.entries(value)) {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) continue;
    const messages = "messages" in entry && Array.isArray(entry.messages) ? entry.messages : [];
    const history = "history" in entry && Array.isArray(entry.history) ? entry.history : [];
    const agentNames = "agentNames" in entry && Array.isArray(entry.agentNames)
      ? entry.agentNames.filter((name: unknown): name is string => typeof name === "string")
      : null;
    const skillNames = "skillNames" in entry && Array.isArray(entry.skillNames)
      ? entry.skillNames.filter((name: unknown): name is string => typeof name === "string")
      : null;
    parsed[sessionId] = {
      messages: messages as ChatDisplayMessage[],
      history: history as ChatMessage[],
      agentNames,
      skillNames,
    };
  }
  return parsed;
}

export function loadPersistedChat(
  storage: Storage,
  userId: number | null,
  warn: Warn = defaultWarn,
): PersistedChatState {
  if (userId === null) return emptyPersistedChatState();
  const key = chatStorageKey(userId);
  const metadata = readJson(storage, key, warn);
  const rawSessionData = readJson(storage, `${key}-data`, warn);
  const metadataRecord = typeof metadata === "object" && metadata !== null && !Array.isArray(metadata)
    ? metadata
    : {};
  const activeSessionId = "activeSessionId" in metadataRecord
    && typeof metadataRecord.activeSessionId === "string"
    ? metadataRecord.activeSessionId
    : null;
  return {
    sessions: parseSessions("sessions" in metadataRecord ? metadataRecord.sessions : null),
    sessionData: parseSessionData(rawSessionData),
    activeSessionId,
  };
}

export function createChatPersistSnapshot(
  sessions: SessionMeta[],
  sessionData: Record<string, SessionData>,
  activeSessionId: string | null,
  messages: ChatDisplayMessage[],
  history: ChatMessage[],
  agentNames: string[] | null,
  skillNames: string[] | null,
): PersistedChatState {
  const snapshotData = { ...sessionData };
  if (activeSessionId) {
    snapshotData[activeSessionId] = { messages, history, agentNames, skillNames };
  }
  return {
    sessions: [...sessions],
    sessionData: snapshotData,
    activeSessionId,
  };
}

function truncateText(value: string, limit: number): string {
  return value.length > limit ? `${value.slice(0, Math.max(0, limit - 1))}…` : value;
}

function compactActiveSession(data: SessionData, textLimit: number): SessionData {
  return {
    agentNames: data.agentNames ?? null,
    skillNames: data.skillNames ?? null,
    messages: data.messages.slice(-2).map((message) => ({
      ...message,
      content: truncateText(message.content, textLimit),
      reasoningContent: message.reasoningContent
        ? truncateText(message.reasoningContent, textLimit)
        : message.reasoningContent,
      plan: message.plan
        ? {
            summary: message.plan.summary
              ? truncateText(message.plan.summary, textLimit)
              : message.plan.summary,
            steps: message.plan.steps.slice(0, 12).map((step) => ({
              ...step,
              description: step.description
                ? truncateText(step.description, textLimit)
                : step.description,
              detail: step.detail ? truncateText(step.detail, textLimit) : step.detail,
            })),
          }
        : message.plan,
      toolCalls: message.toolCalls?.slice(-8).map((toolCall) => ({
        ...toolCall,
        arguments: truncateText(toolCall.arguments, textLimit),
        result: toolCall.result ? truncateText(toolCall.result, textLimit) : toolCall.result,
      })),
    })),
    history: data.history.slice(-4).map((message) => ({
      ...message,
      content: message.content ? truncateText(message.content, textLimit) : message.content,
      reasoning_content: message.reasoning_content
        ? truncateText(message.reasoning_content, textLimit)
        : message.reasoning_content,
      tool_calls: message.tool_calls?.slice(-8).map((toolCall) => ({
        ...toolCall,
        function: {
          ...toolCall.function,
          arguments: truncateText(toolCall.function.arguments, textLimit),
        },
      })),
    })),
  };
}

function serializeSessionData(sessionData: Record<string, SessionData>): string {
  return JSON.stringify(sessionData);
}

export function compactChatSessionData(
  sessions: SessionMeta[],
  sessionData: Record<string, SessionData>,
  activeSessionId: string | null,
  maxSize = CHAT_STORAGE_LIMIT,
): CompactedChatData {
  let compacted = false;
  const nextData = { ...sessionData };
  let serialized = serializeSessionData(nextData);
  if (serialized.length <= maxSize) {
    return { sessionData: nextData, serialized, compacted, fits: true };
  }

  const oldestFirst = [...sessions].sort((left, right) => left.updatedAt - right.updatedAt);
  for (const session of oldestFirst) {
    if (session.id === activeSessionId) continue;
    const entry = nextData[session.id];
    if (!entry) continue;
    compacted = true;
    nextData[session.id] = {
      messages: entry.messages.slice(-2),
      history: entry.history.slice(-4),
      agentNames: entry.agentNames ?? null,
      skillNames: entry.skillNames ?? null,
    };
    serialized = serializeSessionData(nextData);
    if (serialized.length <= maxSize) {
      return { sessionData: nextData, serialized, compacted, fits: true };
    }
  }

  for (const session of oldestFirst) {
    if (session.id === activeSessionId || !(session.id in nextData)) continue;
    delete nextData[session.id];
    compacted = true;
    serialized = serializeSessionData(nextData);
    if (serialized.length <= maxSize) {
      return { sessionData: nextData, serialized, compacted, fits: true };
    }
  }

  if (activeSessionId && nextData[activeSessionId]) {
    const activeData = nextData[activeSessionId];
    let textLimit = Math.max(16, Math.floor(maxSize / 16));
    while (textLimit >= 16) {
      nextData[activeSessionId] = compactActiveSession(activeData, textLimit);
      compacted = true;
      serialized = serializeSessionData(nextData);
      if (serialized.length <= maxSize) {
        return { sessionData: nextData, serialized, compacted, fits: true };
      }
      if (textLimit === 16) break;
      textLimit = Math.max(16, Math.floor(textLimit / 2));
    }
  }

  return { sessionData: nextData, serialized, compacted, fits: false };
}

export function persistChatSnapshot(
  storage: Storage,
  userId: number,
  snapshot: PersistedChatState,
  maxSize = CHAT_STORAGE_LIMIT,
  warn: Warn = defaultWarn,
): boolean {
  const compacted = compactChatSessionData(
    snapshot.sessions,
    snapshot.sessionData,
    snapshot.activeSessionId,
    maxSize,
  );
  if (!compacted.fits) {
    warn(`用户 ${userId} 的会话数据无法压缩到 ${maxSize} 字符以内`);
    return false;
  }
  const key = chatStorageKey(userId);
  try {
    storage.setItem(`${key}-data`, compacted.serialized);
    storage.setItem(key, JSON.stringify({
      sessions: snapshot.sessions,
      activeSessionId: snapshot.activeSessionId,
    }));
    return true;
  } catch (error) {
    warn(`写入用户 ${userId} 的会话数据失败`, error);
    return false;
  }
}

let persistTimer: ReturnType<typeof setTimeout> | null = null;
let pendingPersist: PendingPersist | null = null;

export function scheduleChatPersist(
  storage: Storage,
  userId: number | null,
  snapshot: PersistedChatState,
) {
  if (userId === null) return;
  pendingPersist = { storage, userId, ...snapshot };
  if (persistTimer) return;
  persistTimer = setTimeout(() => {
    persistTimer = null;
    if (!pendingPersist) return;
    const { storage: pendingStorage, userId: pendingUserId, ...pendingSnapshot } = pendingPersist;
    pendingPersist = null;
    persistChatSnapshot(pendingStorage, pendingUserId, pendingSnapshot);
  }, 300);
}

export function flushChatPersist() {
  if (persistTimer) {
    clearTimeout(persistTimer);
    persistTimer = null;
  }
  if (!pendingPersist) return;
  const { storage, userId, ...snapshot } = pendingPersist;
  pendingPersist = null;
  persistChatSnapshot(storage, userId, snapshot);
}
