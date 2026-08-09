import { useCallback, useMemo, useState } from "react";
import { useStockSearch } from "../api/queries";
import { getCurrentStockSearchResults, normalizeStockSearchInput, resolveStockSearchCode } from "../utils/stockSearch";
import { useDebouncedValue } from "./useDebouncedValue";

interface StockSearchControllerOptions {
  initialValue?: string;
  debounceMs?: number;
}

export function useStockSearchController({
  initialValue = "",
  debounceMs = 200,
}: StockSearchControllerOptions = {}) {
  const [inputValue, setInputValue] = useState(initialValue);
  const normalizedInput = normalizeStockSearchInput(inputValue);
  const query = useDebouncedValue(normalizedInput, debounceMs);
  const {
    data: results = [],
    isFetching,
    isError,
    error,
    refetch,
  } = useStockSearch(query);
  const currentResults = useMemo(
    () => getCurrentStockSearchResults(normalizedInput, query, results),
    [normalizedInput, query, results],
  );
  const isPending = normalizedInput !== query || isFetching;

  const clear = useCallback(() => setInputValue(""), []);
  const resolveCode = useCallback(
    (value = inputValue) => resolveStockSearchCode(value, query, currentResults),
    [currentResults, inputValue, query],
  );

  return {
    inputValue,
    normalizedInput,
    query,
    currentResults,
    isPending,
    isError,
    error,
    retry: refetch,
    setInputValue,
    clear,
    resolveCode,
  };
}
