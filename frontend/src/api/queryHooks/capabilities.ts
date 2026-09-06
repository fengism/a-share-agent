import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import type {
  ChatCapabilitiesResponse,
  ChatCapabilityAvailabilityResponse,
} from "../../types/capabilities";

export function useChatCapabilities() {
  return useQuery({
    queryKey: queryKeys.capabilities.catalog,
    queryFn: () => apiGet<ChatCapabilitiesResponse>("/chat/capabilities"),
    staleTime: QUERY_CACHE_POLICIES.capabilitiesCatalog.staleMs,
  });
}

export function useChatCapabilityAvailability() {
  return useQuery({
    queryKey: queryKeys.capabilities.availability,
    queryFn: () => apiGet<ChatCapabilityAvailabilityResponse>("/chat/capabilities/availability"),
    staleTime: QUERY_CACHE_POLICIES.capabilitiesAvailability.staleMs,
  });
}
