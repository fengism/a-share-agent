import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  ChatCapabilitiesResponse,
  ChatCapabilityAvailabilityResponse,
} from "../../types/capabilities";

export function useChatCapabilities() {
  return useQuery({
    queryKey: queryKeys.capabilities.catalog,
    queryFn: () => apiGet<ChatCapabilitiesResponse>("/chat/capabilities"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useChatCapabilityAvailability() {
  return useQuery({
    queryKey: queryKeys.capabilities.availability,
    queryFn: () => apiGet<ChatCapabilityAvailabilityResponse>("/chat/capabilities/availability"),
    staleTime: 30 * 1000,
  });
}
