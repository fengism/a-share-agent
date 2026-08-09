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
    queryFn: ({ signal }) => apiGet<ChatCapabilitiesResponse>("/chat/capabilities", undefined, { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useChatCapabilityAvailability() {
  return useQuery({
    queryKey: queryKeys.capabilities.availability,
    queryFn: ({ signal }) => apiGet<ChatCapabilityAvailabilityResponse>(
      "/chat/capabilities/availability",
      undefined,
      { signal },
    ),
    staleTime: 30 * 1000,
  });
}
