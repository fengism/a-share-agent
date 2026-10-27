import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const nodeMajorVersion = Number(process.versions.node.split(".")[0]);

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    env: {
      NODE_ENV: "test",
    },
    globals: true,
    poolOptions: {
      forks: {
        execArgv: nodeMajorVersion >= 22 ? ["--no-experimental-webstorage"] : [],
      },
    },
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});
