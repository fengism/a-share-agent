/**
 * 手写类型与 OpenAPI 生成类型的编译期契约。
 *
 * vitest 走 esbuild 不做类型检查，因此这里不写运行时断言：文件被 `tsc -b`
 * 纳入检查，任一侧字段增删或类型漂移都会让构建失败。
 */
import type { components } from "../../api/generated/schema";
import type {
  PotentialDailyResult,
  PotentialPerformanceSummary,
  PotentialRunStatus,
  PotentialStockItem,
} from "./potential";

type DeepRequired<T> = T extends (infer U)[]
  ? DeepRequired<U>[]
  : T extends object
    ? { [K in keyof T]-?: DeepRequired<T[K]> }
    : T;

type GeneratedStockItem = DeepRequired<components["schemas"]["PotentialStockItem"]>;
type GeneratedDailyResult = DeepRequired<components["schemas"]["PotentialDailyResult"]>;
type GeneratedPerformanceSummary = DeepRequired<components["schemas"]["PotentialPerformanceSummary"]>;
type GeneratedRunStatus = DeepRequired<components["schemas"]["PotentialRunStatus"]>;

export function assertGeneratedTypeContracts(): void {
  const stockFromGenerated: PotentialStockItem = null as unknown as GeneratedStockItem;
  const stockToGenerated: GeneratedStockItem = null as unknown as PotentialStockItem;
  const dailyFromGenerated: PotentialDailyResult = null as unknown as GeneratedDailyResult;
  const dailyToGenerated: GeneratedDailyResult = null as unknown as PotentialDailyResult;
  const performanceFromGenerated: PotentialPerformanceSummary = null as unknown as GeneratedPerformanceSummary;
  const performanceToGenerated: GeneratedPerformanceSummary = null as unknown as PotentialPerformanceSummary;
  const runStatusFromGenerated: PotentialRunStatus = null as unknown as GeneratedRunStatus;
  const runStatusToGenerated: GeneratedRunStatus = null as unknown as PotentialRunStatus;

  void [
    stockFromGenerated,
    stockToGenerated,
    dailyFromGenerated,
    dailyToGenerated,
    performanceFromGenerated,
    performanceToGenerated,
    runStatusFromGenerated,
    runStatusToGenerated,
  ];
}
