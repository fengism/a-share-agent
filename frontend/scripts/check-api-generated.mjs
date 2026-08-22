import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

const generatedFiles = [
  "src/api/generated/openapi.json",
  "src/api/generated/request-schema.ts",
  "src/api/generated/schema.ts",
];
const before = new Map(generatedFiles.map((file) => [file, readFileSync(file)]));
const command = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(command, ["run", "api:generate"], { stdio: "inherit" });
if (result.status !== 0) process.exit(result.status ?? 1);

const changed = generatedFiles.filter((file) => !before.get(file)?.equals(readFileSync(file)));
if (changed.length > 0) {
  console.error(`OpenAPI 生成产物未同步: ${changed.join(", ")}`);
  process.exit(1);
}
console.log("OpenAPI 生成产物已同步");
