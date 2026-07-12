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
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-antd": ["antd", "@ant-design/icons"],
          "vendor-echarts": ["echarts", "echarts-for-react"],
          "vendor-charts": ["lightweight-charts"],
          "vendor-pdf": ["html2canvas", "jspdf"],
        },
      },
    },
  },
});
