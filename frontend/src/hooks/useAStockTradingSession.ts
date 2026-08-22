import { useSyncExternalStore } from "react";
import {
  isAStockAutoRefreshTime,
  millisecondsUntilNextAStockSessionBoundary,
} from "../utils/tradingSession";

type SessionListener = () => void;

const listeners = new Set<SessionListener>();
let boundaryTimer: number | undefined;

function getTradingSessionSnapshot(): boolean {
  return isAStockAutoRefreshTime(new Date());
}

function scheduleNextBoundary(): void {
  const now = new Date();
  boundaryTimer = window.setTimeout(() => {
    boundaryTimer = undefined;
    for (const listener of listeners) listener();
    if (listeners.size > 0) scheduleNextBoundary();
  }, millisecondsUntilNextAStockSessionBoundary(now));
}

function subscribeToTradingSession(listener: SessionListener): () => void {
  listeners.add(listener);
  if (listeners.size === 1) scheduleNextBoundary();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && boundaryTimer !== undefined) {
      window.clearTimeout(boundaryTimer);
      boundaryTimer = undefined;
    }
  };
}

export function useAStockTradingSession(): boolean {
  return useSyncExternalStore(
    subscribeToTradingSession,
    getTradingSessionSnapshot,
    getTradingSessionSnapshot,
  );
}
