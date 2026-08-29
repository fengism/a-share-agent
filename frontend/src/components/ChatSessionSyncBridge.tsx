import { useChatSessionSync } from "../hooks/useChatSessionSync";

export default function ChatSessionSyncBridge() {
  useChatSessionSync();
  return null;
}
