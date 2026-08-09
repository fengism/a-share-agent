import { queryClient } from "../api/queryClient";

type UserScopeHandler = (
  userId: number | null,
  previousUserId: number | null,
) => void;

let activeUserId: number | null = null;
const handlers = new Set<UserScopeHandler>();

export function getActiveUserScope() {
  return activeUserId;
}

export function setActiveUserScope(userId: number | null) {
  if (userId === activeUserId) return;

  const previousUserId = activeUserId;
  activeUserId = userId;
  queryClient.clear();
  handlers.forEach((handler) => handler(userId, previousUserId));
}

export function registerUserScopeHandler(handler: UserScopeHandler) {
  handlers.add(handler);
  return () => handlers.delete(handler);
}
