import { useSyncExternalStore } from "react";

function subscribe(callback: () => void): () => void {
  if (typeof document === "undefined") return () => undefined;
  document.addEventListener("visibilitychange", callback);
  return () => document.removeEventListener("visibilitychange", callback);
}

function getSnapshot(): boolean {
  return typeof document !== "undefined" ? document.visibilityState === "visible" : true;
}

function getServerSnapshot(): boolean {
  return true;
}

export function usePageVisibility(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
