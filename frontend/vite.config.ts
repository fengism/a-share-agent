import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
    allowedHosts: ["localhost", "127.0.0.1"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          // ECharts (+ echarts-for-react wrapper) — heaviest vendor, keep isolated
          if (id.includes("echarts")) return "vendor-echarts";
          if (id.includes("lightweight-charts")) return "vendor-charts";
          if (id.includes("antd") || id.includes("@ant-design")) return "vendor-antd";
          if (
            id.includes("/react-router") ||
            id.includes("/react-dom/") ||
            id.includes("/react/") ||
            id.includes("/scheduler/")
          )
            return "vendor-react";
          // html2canvas & jspdf are dynamically imported → Rollup auto-splits them
        },
      },
    },
  },
});
