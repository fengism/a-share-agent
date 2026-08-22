export type ToolCost = "low" | "medium" | "high";
export type ToolFreshness = "realtime" | "near_realtime" | "daily" | "static";
export type ToolScope = "public" | "user";

export interface ToolParameterSchema {
  type?: string | string[];
  description?: string;
  enum?: unknown[];
  default?: unknown;
  pattern?: string;
  format?: string;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
  uniqueItems?: boolean;
  items?: ToolParameterSchema;
}

export interface ToolParametersSchema {
  type: string;
  properties: Record<string, ToolParameterSchema>;
  required?: string[];
  additionalProperties?: boolean;
}

export interface ToolPolicyInfo {
  cost: ToolCost;
  cache_ttl_seconds: number;
  freshness: ToolFreshness;
  scope: ToolScope;
  timeout_seconds?: number | null;
  max_parallel_calls?: number | null;
  max_result_characters: number;
}

export interface ToolCapabilityInfo {
  name: string;
  description: string;
  parameters: ToolParametersSchema;
  policy: ToolPolicyInfo;
  skill_names: string[];
}

export interface SkillCapabilityInfo {
  name: string;
  description: string;
  triggers: string[];
  tool_names: string[];
  rules: string[];
  exclusions: string[];
  priority: number;
}

export interface AgentCapabilityInfo {
  name: string;
  display_name: string;
  description: string;
  tool_names: string[];
  skill_names: string[];
  max_rounds: number;
}

export type CapabilityAvailabilityStatus = "ready" | "degraded" | "unavailable" | "disabled";

export interface CapabilityAvailabilityInfo {
  status: CapabilityAvailabilityStatus;
  reason: string;
}

export interface ChatCapabilityAvailabilityResponse {
  llm: CapabilityAvailabilityInfo;
  skills: Record<string, CapabilityAvailabilityInfo>;
  agents: Record<string, CapabilityAvailabilityInfo>;
}

export interface ChatCapabilitiesResponse {
  skills: SkillCapabilityInfo[];
  agents: AgentCapabilityInfo[];
  tools: ToolCapabilityInfo[];
  unassigned_tools: string[];
}
