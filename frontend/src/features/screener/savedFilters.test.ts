import { describe, expect, it } from "vitest";
import { DEFAULT_SCREENER_FILTERS } from "./screenerUrlState";
import { deleteSavedFilter, loadSavedFilters, saveFilter } from "./savedFilters";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() { return values.size; },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

const state = {
  filters: { ...DEFAULT_SCREENER_FILTERS, pe_max: 15 },
  showPercentile: true,
  pePercentileMax: 30,
  pbPercentileMax: 40,
};

describe("shared saved screener filters", () => {
  it("isolates saved filters by user and updates duplicate names", () => {
    const storage = createMemoryStorage();
    saveFilter(storage, 1, "低估值", state, 100);
    saveFilter(storage, 2, "用户二方案", state, 200);
    const updated = saveFilter(storage, 1, "低估值", {
      ...state,
      filters: { ...state.filters, pe_max: 10 },
    }, 300);

    expect(updated).toHaveLength(1);
    expect(updated[0].state.filters.pe_max).toBe(10);
    expect(loadSavedFilters(storage, 2).map((item) => item.name)).toEqual(["用户二方案"]);
  });

  it("deletes only the selected filter", () => {
    const storage = createMemoryStorage();
    const first = saveFilter(storage, 1, "方案一", state, 100)[0];
    saveFilter(storage, 1, "方案二", state, 200);

    expect(deleteSavedFilter(storage, 1, first.id).map((item) => item.name)).toEqual(["方案二"]);
  });
});
