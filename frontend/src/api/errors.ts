import type { components } from "./generated/schema";

export type ErrorResponse = components["schemas"]["ErrorResponse"];

export interface ParsedApiError {
  message: string;
  code?: string;
  requestId?: string;
  errorId?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

export function parseApiError(payload: unknown, fallbackMessage: string): ParsedApiError {
  if (!isRecord(payload)) return { message: fallbackMessage };
  const response = payload as Partial<ErrorResponse> & { detail?: unknown };
  return {
    message: optionalString(response.message) ?? optionalString(response.detail) ?? fallbackMessage,
    code: optionalString(response.code),
    requestId: optionalString(response.request_id),
    errorId: optionalString(response.error_id),
  };
}
