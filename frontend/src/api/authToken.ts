const LEGACY_TOKEN_KEY = "a-share-agent-token";
const CSRF_COOKIE_NAME = "a_share_csrf";

let _token: string | null = null;
let _onUnauthorized: (() => void) | null = null;

try {
  localStorage.removeItem(LEGACY_TOKEN_KEY);
} catch {
  // Storage may be unavailable; cookie authentication is unaffected.
}

export function getToken(): string | null {
  return _token;
}

export function setToken(token: string | null): void {
  _token = token;
  try {
    localStorage.removeItem(LEGACY_TOKEN_KEY);
  } catch {
    // Storage may be unavailable; the token remains memory-only.
  }
}

export function getCsrfToken(): string | null {
  try {
    const prefix = `${CSRF_COOKIE_NAME}=`;
    const cookie = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  } catch {
    return null;
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
