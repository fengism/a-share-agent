import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";

const pagesRoot = path.resolve("src/pages");
const sourceFiles = [];

function collectSourceFiles(directory) {
  for (const entry of readdirSync(directory)) {
    const entryPath = path.join(directory, entry);
    if (statSync(entryPath).isDirectory()) {
      collectSourceFiles(entryPath);
    } else if (/\.(ts|tsx)$/.test(entry)) {
      sourceFiles.push(entryPath);
    }
  }
}

collectSourceFiles(pagesRoot);

const importPattern = /(?:from\s+|import\s*\()\s*["']([^"']+)["']/g;
const violations = [];

for (const sourceFile of sourceFiles) {
  const sourceOwner = path.relative(pagesRoot, sourceFile).split(path.sep)[0];
  const source = readFileSync(sourceFile, "utf8");
  for (const match of source.matchAll(importPattern)) {
    const specifier = match[1];
    if (!specifier.startsWith(".")) continue;
    const target = path.resolve(path.dirname(sourceFile), specifier);
    const relativeTarget = path.relative(pagesRoot, target);
    if (relativeTarget.startsWith("..") || path.isAbsolute(relativeTarget)) continue;
    const targetOwner = relativeTarget.split(path.sep)[0];
    if (targetOwner !== sourceOwner) {
      violations.push(
        `${path.relative(process.cwd(), sourceFile)} imports page ${targetOwner} via ${specifier}`,
      );
    }
  }
}

if (violations.length > 0) {
  console.error(`Route pages must not import other route pages:\n${violations.join("\n")}`);
  process.exit(1);
}

console.log("Frontend page boundaries passed");
