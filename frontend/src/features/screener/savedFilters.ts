import type { ScreenerUrlState } from "./screenerUrlState";

export interface SavedScreenerFilter {
  id: string;
  name: string;
  state: ScreenerUrlState;
  updatedAt: number;
}

const STORAGE_PREFIX = "screener-filters:user:";
const MAX_SAVED_FILTERS = 20;

function storageKey(userId: number): string {
  return `${STORAGE_PREFIX}${userId}`;
}

function isSavedFilter(value: unknown): value is SavedScreenerFilter {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<SavedScreenerFilter>;
  return typeof candidate.id === "string"
    && typeof candidate.name === "string"
    && typeof candidate.updatedAt === "number"
    && typeof candidate.state === "object"
    && candidate.state !== null
    && typeof candidate.state.filters === "object"
    && candidate.state.filters !== null;
}

export function loadSavedFilters(storage: Storage, userId: number): SavedScreenerFilter[] {
  try {
    const value: unknown = JSON.parse(storage.getItem(storageKey(userId)) ?? "[]");
    return Array.isArray(value)
      ? value.filter(isSavedFilter).sort((left, right) => right.updatedAt - left.updatedAt)
      : [];
  } catch {
    return [];
  }
}

function persistFilters(
  storage: Storage,
  userId: number,
  filters: SavedScreenerFilter[],
): SavedScreenerFilter[] {
  storage.setItem(storageKey(userId), JSON.stringify(filters));
  return filters;
}

export function saveFilter(
  storage: Storage,
  userId: number,
  name: string,
  state: ScreenerUrlState,
  updatedAt = Date.now(),
): SavedScreenerFilter[] {
  const normalizedName = name.trim();
  const filters = loadSavedFilters(storage, userId);
  const existing = filters.find((filter) => filter.name === normalizedName);
  const saved: SavedScreenerFilter = {
    id: existing?.id ?? `filter-${updatedAt}-${encodeURIComponent(normalizedName)}`,
    name: normalizedName,
    state,
    updatedAt,
  };
  const next = [saved, ...filters.filter((filter) => filter.id !== saved.id)]
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .slice(0, MAX_SAVED_FILTERS);
  return persistFilters(storage, userId, next);
}

export function deleteSavedFilter(
  storage: Storage,
  userId: number,
  filterId: string,
): SavedScreenerFilter[] {
  return persistFilters(
    storage,
    userId,
    loadSavedFilters(storage, userId).filter((filter) => filter.id !== filterId),
  );
}
