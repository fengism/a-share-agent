import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiProxy = {
    "/api": {
      target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
      changeOrigin: true,
    },
  };

  return {
    plugins: [react()],
    resolve: {
      alias: {
        html2canvas: "html2canvas-pro",
      },
    },
    server: {
      proxy: apiProxy,
      allowedHosts: ["localhost", "127.0.0.1"],
    },
    preview: {
      proxy: apiProxy,
    },
    build: {
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) return;
            // ECharts 与 zrender 保持单向依赖；树图模块不能单独拆分，
            // 否则与 vendor-echarts 形成循环 chunk，运行时报
            // "Class extends value undefined"（评估顺序错乱）。
            if (id.includes("/zrender/") || id.includes("/echarts/"))
              return "vendor-echarts";
            if (id.includes("lightweight-charts")) return "vendor-charts";
            if (
              id.includes("/react-router") ||
              id.includes("/react-dom/") ||
              id.includes("/react/") ||
              id.includes("/scheduler/")
            )
              return "vendor-react";
            // Ant Design follows route-aware automatic splitting. html2canvas
            // and jspdf are dynamically imported only when exporting PDFs.
          },
        },
      },
    },
  };
});
