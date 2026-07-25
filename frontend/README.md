# A股智能分析助手 · 前端

A 股智能分析平台的 Web 前端:实时行情、资金流向、龙虎榜、宏观数据,以及基于大模型的深度个股分析与对话。

## 技术栈

- **构建**:Vite 5 + TypeScript 5
- **框架**:React 18 + React Router 7
- **UI**:Ant Design 6 + @ant-design/icons
- **图表**:ECharts 6(按需引入,见 `src/charts/echarts-setup.ts`)、lightweight-charts(K 线/分时)
- **状态/数据**:Zustand(主题等本地状态)、TanStack Query(服务端数据)
- **其他**:react-markdown + remark-gfm、DOMPurify;PDF 导出用 html2canvas + jsPDF(按需动态加载)

## 开发

```bash
npm install
npm run dev        # 启动开发服务器(默认 5173)
```

开发服务器把 `/api` 代理到本地后端 `http://127.0.0.1:8000`(见 `vite.config.ts`),需先启动后端。

## 构建与预览

```bash
npm run build      # tsc -b 类型检查 + vite 生产构建,产物在 dist/
npm run preview    # 本地预览生产构建
npm run lint       # ESLint 检查
```

## 目录结构

```
src/
  api/         # 后端请求封装、TanStack Query hooks、SSE 流
  charts/      # ECharts 按需注册、K 线/分时/指标图
  components/  # 布局(AppLayout)、错误边界、通用组件
  pages/       # 各功能页:Dashboard/Market/Macro/Compare/Feed/
               #   Screener/Chat/DailyReview/Analysis/IndustryChain/Settings
  store/       # Zustand store(分析、对话)
  theme/       # 主题定义与 hooks(4 套主题,支持切换,持久化)
  styles/      # 全局基础样式、Markdown、导出样式
  types/       # 领域类型定义
  utils/       # 格式化、日期、字段标签等工具
```

## 主题

内置 4 套主题(星空蓝 / 翡翠绿 / 暮光紫 / 清晨白),通过侧边栏底部按钮切换,选择持久化在 `localStorage`。`index.html` 内置了防白屏脚本,会在 React 挂载前按上次主题铺底色。

> A 股习惯:**红涨绿跌**(与欧美相反),配色已遵循此约定。

## 部署

`Dockerfile` 基于 nginx 提供静态产物,`nginx.conf` 配置了 gzip、静态资源长缓存、`/api` 反向代理与限流。见仓库根目录的 `docker-compose.yml`。
