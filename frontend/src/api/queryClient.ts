import { QueryClient } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "./cachePolicies";
import { ApiError, ApiTimeoutError } from "./client";

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  if (error instanceof ApiTimeoutError) return false;
  if (error instanceof ApiError) return error.status >= 500;
  if (
    typeof error === "object"
    && error !== null
    && "name" in error
    && error.name === "AbortError"
  ) return false;
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetryQuery,
      refetchOnWindowFocus: false,
      staleTime: QUERY_CACHE_POLICIES.defaultQuery.staleMs,
    },
  },
});
