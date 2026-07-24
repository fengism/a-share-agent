/**
 * Session token holder — single source of truth for the Bearer token.
 *
 * Kept in-memory for fast synchronous reads (every API request) and mirrored to
 * localStorage so the session survives reloads. This is a dependency-free leaf
 * module: both the API layer (client/sse/chat) and the auth store import it,
 * avoiding an import cycle.
 */
const TOKEN_KEY = "a-share-agent-token";

function readStored(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

let _token: string | null = readStored();
let _onUnauthorized: (() => void) | null = null;

export function getToken(): string | null {
  return _token;
}

export function setToken(token: string | null): void {
  _token = token;
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode / quota) — in-memory still works */
  }
}

/** Register the handler invoked when an authenticated request is rejected (401). */
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  _onUnauthorized = fn;
}

/** Called by the API layer when a request carrying a token gets a 401. */
export function notifyUnauthorized(): void {
  if (_onUnauthorized) _onUnauthorized();
}
