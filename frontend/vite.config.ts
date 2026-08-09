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
    server: {
      proxy: apiProxy,
      allowedHosts: ["localhost", "127.0.0.1"],
    },
    preview: {
      proxy: apiProxy,
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) return;
            // ECharts depends one-way on zrender; separating them keeps both
            // route-only chunks below the warning threshold without cycles.
            if (id.includes("/zrender/")) return "vendor-zrender";
            if (id.includes("/echarts/")) return "vendor-echarts";
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
