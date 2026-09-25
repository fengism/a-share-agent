import { chatStorageKey } from "./chatPersistence";

// The existing user-scoped local snapshot is the outbox body. Store only its base
// revision here, so recovery does not double the browser's storage consumption.
const key = (userId: number) => `${chatStorageKey(userId)}-pending`;
export function readPendingChat(storage: Storage, userId: number): { revision: number | null } | null {
  const raw = storage.getItem(key(userId));
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    return { revision: Number.isSafeInteger(value?.revision) && value.revision >= 0 ? value.revision : null };
  } catch {
    return { revision: null }; // A corrupt marker must not authorize overwriting local data.
  }
}
export function markPendingChat(storage: Storage, userId: number, revision: number | null) {
  storage.setItem(key(userId), JSON.stringify({ revision }));
}
export function clearPendingChat(storage: Storage, userId: number) {
  storage.removeItem(key(userId));
}
