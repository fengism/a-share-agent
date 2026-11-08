# 本地开发指南

面向需要改代码、跑测试、发版的开发者。部署与使用说明见 [README](../README.md)。

## 一、环境要求

| 项目 | 版本 | 说明 |
| :--- | :--- | :--- |
| Python | 3.11+ | 后端运行时；开发依赖由 `uv` 管理 |
| uv | 最新 | `backend/pyproject.toml` + `uv.lock` 锁定依赖 |
| Node.js | 22 | 前端构建与测试；以仓库根 `.nvmrc` 为准（CI / Dockerfile 同源） |
| npm | 10+ | `frontend/package.json#packageManager` 已声明；本项目只用 npm |
| 可选：Docker | 20.10+ | 只在需要容器化验证时使用 |

> [!WARNING]
> **前端依赖必须用 `npm ci` 按 `frontend/package-lock.json` 安装**，不要用 pnpm/yarn。
> 仓库只维护这一份锁文件；用其他包管理器装出的 `node_modules` 与锁文件版本不一致时，
> 会出现一批只在本地复现的失败（antd / testing-library 等小版本差异就足以让快照与
> 交互断言挂掉）。遇到“别人都能过、只有我挂”先跑：
>
> ```bash
> cd frontend && rm -rf node_modules && npm ci
> ```

> [!NOTE]
> 后端**必须**用 `uv run` 执行（`cd backend && uv run pytest`）。系统自带的 `python3` 通常缺少
> pydantic / fastapi 等运行时依赖，直接调用会得到误导性的 import 错误。

## 二、首次初始化

```bash
./setup.sh                 # 安装前后端依赖与基础运行库
cp .env.example .env       # 配置环境变量（至少生成 CONFIG_ENCRYPTION_KEY）
cd backend && uv run python -c 'from app.infrastructure.persistence import init_db; init_db(); print("db ok")'
```

`init_db()` 会创建四个 SQLite 库并应用结构迁移，空行业库自动从 `backend/seeds/` 播种。

需要以下两项可选能力时再单独安装浏览器内核（下载量较大）：

```bash
make backend-browser-install                  # 后端网页抓取（patchright + Chromium）
cd frontend && npx playwright install chromium  # 前端 E2E 与 README 配图脚本
```

## 三、常用命令

### 运行与调试

| 命令 | 作用 |
| :--- | :--- |
| `make dev` / `./start.sh dev` | 启动前后端（热重载） |
| `make stop` / `make restart` | 停止 / 重启本地服务 |
| `make status` | 查看 `8000` / `5173` 端口监听状态 |
| `make logs` | 持续跟踪 `logs/backend.log`、`logs/frontend.log` |
| `make backend-dev` / `make frontend-dev` | 单独启动后端 / 前端 |
| `make prod` | 本地生产模式（构建前端产物） |

### 质量门禁

| 命令 | 内容 |
| :--- | :--- |
| `make check` | **提交前必跑**：后端 lint → 模块边界 → 类型 → 覆盖率 → OpenAPI 同步 → 前端测试 → 前端 lint → 前端构建 |
| `make backend-lint` | `ruff check app scripts tests` |
| `make backend-boundaries` | 分层/私有名/反向依赖门禁（规则见 [架构与边界](architecture.md)） |
| `make backend-type` | `mypy`（严格模式，全量源文件） |
| `make backend-test` | `pytest -q` |
| `make backend-coverage` | 覆盖率下限 44%，可用 `COVERAGE_MIN=50 make backend-coverage` 覆盖 |
| `make frontend-test` | `vitest run` |
| `make frontend-lint` | `eslint .` + 页面边界检查 + 时区门禁 + 样式卫生门禁 + 色彩纪律门禁（见下一节「硬约束」） |
| `make frontend-e2e` | Playwright 浏览器 smoke 测试（首次需 `cd frontend && npx playwright install chromium`） |
| `make frontend-api-check` | 校验 OpenAPI 生成产物是否与后端一致 |

### 数据与发布

| 命令 | 作用 |
| :--- | :--- |
| `make backend-db-init` | 初始化数据库结构 |
| `make backend-export-seeds` | 从运行库导出种子到 `backend/seeds/*.csv.gz` |
| `make backend-seeds-drift` | 对比运行库与种子快照差异（只读） |
| `make backend-seed-hot-stocks TOP=100` | 为热门股票补抓经营资料 |
| `make backend-reset-admin ADMIN=admin PASS=xxx` | 无损重置管理员密码 |
| `make backend-reset-accounts` | 重置本地全部账号数据 |
| `make pack` | 打包源码（排除密钥、数据、日志与依赖） |
| `make release V=v0.8.0` | 打 tag 并推送，触发镜像构建与发版 |

## 四、质量门禁的硬约束

1. **模块边界**：`app/core`、`app/domain`、`app/infrastructure`、`app/financial_data` 不得反向依赖
   `app/modules` / `app/api` / `app/runtime`；跨模块引用不得使用下划线私有名。规则实现见
   `backend/scripts/check_import_boundaries.py`，背景见 [架构与边界](architecture.md)。
2. **类型**：`mypy` 全量通过，不新增 `# type: ignore` 作为常规手段。
3. **覆盖率**：总体不低于 44%（当前约 52%），新增模块应自带测试而不是拉低均值。
4. **契约同步**：改了后端 Pydantic 模型必须重新生成前端产物，否则 `make frontend-api-check` 失败：

   ```bash
   cd frontend && npm run api:generate   # 重新生成 src/api/generated/*
   ```

另外三条由脚本守住的单点约定（都挂在 `make check` 上）：

- **后端时间戳**：`app/` 内不要直接 `datetime.now()` / `date.today()`，一律用
  `app/domain/timezones.py` 的 `market_now()` / `market_today()`，保证落库值恒为北京时间；
  `tests/test_timezone_guard.py` 会扫描越界写法。
- **时间戳展示**：后端时间戳是「北京时间墙上时钟 + 无时区后缀」，前端一律用
  `src/utils/marketTime.ts`（`parseMarketTime` / `formatMarketDateTime` / `formatMarketClock` …）解析与渲染。
  直接 `new Date(后端时间串)` 会让非 UTC+8 用户看到整体偏移的行情时间，
  `frontend/scripts/check-market-time.mjs` 会拦住这类写法（分时图等用 `getUTC*` 自洽的地方在允许名单里）。
- **CSV 导出**：导出单元格一律经 `app/core/csv_export.py` 的 `csv_safe_row` 处理，
  阻断 `=cmd|…` 这类公式注入；新增导出接口时不要裸用 `writer.writerow([...])`。
- **错误消息不得带内部细节**：`ApplicationError` 的 `message` 会原样进 HTTP 响应
  （`app/api/errors.py` 的处理器只追加 `error_id`，**不做脱敏**）。因此 5xx 的文案必须是
  固定中文提示，不要拼 `str(exc)`、URL、参数或 SQL；底层原因靠 `raise ... from exc`
  保留到服务端日志。`tests/test_error_message_leak_guard.py` 会扫描
  「`except Exception as exc` 后把 `exc` 拼进用户可见消息」的写法。
  （按类型精确捕获的领域异常——如 `LLMConfigurationError`——其 message 本就是给用户看的提示，不在此约束内。）
- **前端 Hook 依赖**：`react-hooks/exhaustive-deps` 在 `frontend/eslint.config.js` 里已从插件的
  默认 `warn` 升为 **`error`**。CI 跑的是不带 `--max-warnings` 的 `eslint .`，`warn` 不会阻断流水线，
  而漏写依赖数组会导致 stale closure（读到上一次渲染的 state/props，极难复现）。
- **样式卫生（棘轮）**：`frontend/scripts/check-style-hygiene.mjs` 对内联样式 `style={{ ... }}`
  与 CSS `!important` 设有**总量预算**，并对单个 CSS 文件设有**行数上限**与**结构体检**：
  都只允许下降，不允许上调。收敛一批后请同步下调脚本里的 `INLINE_STYLE_BUDGET` /
  `IMPORTANT_BUDGET` / `MAX_CSS_LINES`。新样式优先写成页面 CSS 类并复用 `--c-*` 变量，
  不要把布局与颜色继续塞进行内样式。本地可用 `npm run lint:all` 额外执行 `api:check`
  校验 OpenAPI 生成物是否与后端一致（需本地 `uv` 可用）。
- **A 股色彩纪律门禁**：`frontend/scripts/check-color-discipline.mjs`（已接入 `npm run lint`）。
  A 股交易软件有极其严格的心智模型：**红（涨 / 净流入 / 涨停）、绿（跌 / 净流出 / 跌停）必须专用于价格与资金**。
  严禁在非价格维度（如业务分类、阶段标识、普通成功/失败标签、主营构成条）滥用 `color="red"` / `color="green"` /
  `color="volcano"` / `color="lime"` 或以 `error` / `success` 充当通用状态。
  规范用法：
  - 业务与产业链分类：统一使用 `blue` (上游/科技)、`purple` (中游/集成)、`cyan` (下游/量化)、`orange/gold` (热度/特征)；
  - 状态与提示：当前/运行中 `processing` 或 `blue`；预警/异常 `warning` (金黄)；中性/无数据 `default` (灰)；
  - 自选与勾选：已加入图标使用主题色 `var(--c-primary)`，禁止使用绿勾；
  - 语义化样式复用：优先使用 `src/theme/hooks.ts` 的 `semanticTagStyle(color)`。
- **三层字阶与视觉降噪规范 (Three-Tier Typography)**：
  金融终端信息密度高，杜绝字重与字号失控，全站严格遵循三层阶梯与等宽数字对齐：
  - **Primary 主文本 / 核心指标**：`var(--c-text-primary)`，字重 `600` 或 `700`。用于大字号核心指标数值（如 `3120.45`）、模块主标题、关键股票简称；
  - **Secondary 次级文本 / 描述说明**：`var(--c-text-secondary)`，字重 `400` 或 `500`。用于字段标签名、表格表头、描述段落、次级参数；
  - **Tertiary 弱化文本 / 辅助元数据**：`var(--c-text-muted)`，字重 `400`。用于更新时间戳、单位提示、辅助说明、空状态占位符与微注；
  - **核心数字对齐**：所有动态指标与浮点数值统一挂载 `.financial-num`（等宽字体 `var(--c-font-mono)`、`tabular-nums`、`white-space: nowrap`），严禁拆行折叠。
- **低对比度边框与表格边框收敛规范 (Border Token Discipline)**：
  - 严禁在页面或组件中使用硬编码的高对比度硬描边（如 `#444`、`#000` 或强对比实线），杜绝任何生硬的高对比度斑马纹（harsh striped borders）；
  - 全站卡片、表格与分栏边框一律使用低侵入性语义变量 `var(--c-border)`（暗色主题下柔和微透明、明色主题下浅灰淡边）；
  - 嵌套区域与次级分割使用 `var(--c-border-subtle)` 或 `rgba(255, 255, 255, 0.05)`；表格单元格悬浮一律使用 `var(--c-hover-bg)` 或 `rgba(255, 255, 255, 0.035)` 微底色，保持平滑呼吸感。
- **改视觉样式前先量计算样式**：CSS 改动对单测不可见（`npm run test` 全绿不代表样式没变），
  也不能只看截图。可靠做法是用 Playwright 临时夹具在每个 e2e 用例结束时 dump
  所有元素的计算样式，改动前后逐条 diff，**零差异**才算安全。三个必踩的坑：
  dev server 不能当基准（Vite 以 `<style>` 注入路由 CSS，同特异性平局的胜负与生产的
  `<link>` 不同，必须 `build && preview`）；过渡/波纹动画会污染采样（静置后再连采两次，
  只保留两次一致的属性）；字体加载有竞态（用两次对照运行建「不稳定属性掩码」再排除）。
- **卡片外观只由 CSS 类决定，不要用 JS 内联样式下发**。历史上 `useStyles().cardStyle`
  会把圆角/描边/阴影/背景写进元素 `style`（用了 189 次），而 `reset.css` 又用
  `!important` 去覆盖它——同一份外观定义两遍、互相打架。现在统一用 `.u-card` /
  `.u-card-soft`（与旧 `cardStyle` 逐声明等价的 CSS 变量实现）。内联样式只能用
  `!important` 覆盖，靠提高选择器特异性或 `@layer` 都无效，所以别再把外观写回 JS。
- **token 值已带单位时不要再拼单位**。`t.space[3]` 的值是 `"12px"`，写
  `${t.space[3]}px` 会得到非法的 `12pxpx`；浏览器静默丢弃该声明（padding 变 0），
  单测和构建都不会报错。迁移这类内联样式时，先算一遍实际生效值，再决定新类是
  「等价迁移」还是「顺手修复」；是修复就要在验证里明确列为预期视觉变更。
- **不要机械删除 `!important`**，先判断它属于哪一类（三类处理方式完全不同）：
  ① **压制 JS 内联样式** —— 把外观改回 CSS 类后即可删除（如 `cardStyle` → `.u-card`）；
  ② **压制页面自身意图** —— 例如页面想给某张卡片加渐变，全局规则用 `!important` 强行
  改回纯色，删掉会让页面样式「复活」（`reset.css` 的 `background` 类多属此类），
  属于视觉变更，要设计决策而不是重构；
  ③ **antd 选择器与我们平局** —— antd v6 的规则是
  `:where(.css-hash).ant-table-wrapper .ant-table-thead > tr > th`。`:where()` **不计分**，
  所以它只有 (0,2,1)，与 `[data-theme] .ant-table-thead > tr > th` 的 (0,2,1) **平局**；
  平局时后注入的 antd 胜出。这类必须保留 `!important`，或迁到 `theme.components.*` token。
  ⚠ **不要**用“给全局规则再加一级类”的方式提特异性：它会同时压过页面自己写的
  (0,2,1) 覆盖规则（实测 NationalTeam 热力图表头被从 11px 抬到 12px）。
- **CSS 变量必须先定义，否则声明会静默失效**。`background: var(--c-bg-card)` 中若该变量从未定义，
  整个声明在 computed-value 阶段变为无效 → 背景透明（`font-family` 则退回继承）；
  若写了 fallback，则会永远停在硬编码值上、不跟随主题（暗色下出现白卡片这类问题）。
  新增 `var(--x)` 前先确认 `--x` 在 `App.tsx` 的 `tokensToCssVars` 或 `theme/hooks.ts` 里有定义，
  并避免“变体拼写”（`--c-card-bg` 写成 `--c-bg-card`）。
- **`useStyles()` 会订阅主题 store**（`useStyles` → `useColors` → `useThemeStore`）。
  删掉一个组件的 `useStyles()` 调用同时移除了它的 store 订阅，会改变重渲染时序，
  纯 className 重构也可能因此暴露出依赖时序的 e2e 抖动。
- **样式改动要用计算样式差分验证，不能只靠单测**。工具已入库：

  | 文件 | 作用 |
  | :--- | :--- |
  | `e2e/base.ts` | 统一基座：所有 spec 从 `./base` 导入；按 `PROBE_OUT` / `DENSITY_OUT` 自动挂载采样 |
  | `e2e/instrument/probe.ts` | 计算样式采样实现（整页 `body *` 的计算值） |
  | `e2e/instrument/density.ts` | 布局密度采样实现（卡片/表格/表单间距分布） |
  | `playwright.probe.config.ts` | 生产构建（`build && preview`）下跑探针，非 dev server |
  | `scripts/diff-style-probe.mjs` | 比对两次探针产物，输出差异属性值统计 |

  用法（无需修改 spec，环境变量开启采样）：

  ```bash
  npx vite build
  SKIP_BUILD=1 PROBE_OUT=/tmp/probe-before npx playwright test --config playwright.probe.config.ts
  # 改样式……
  npx vite build
  SKIP_BUILD=1 PROBE_OUT=/tmp/probe-after npx playwright test --config playwright.probe.config.ts
  node scripts/diff-style-probe.mjs /tmp/probe-before /tmp/probe-after
  ```

  判定标准：**差异属性值必须为 0**。五个必踩的坑：

  ⓪ **属性名必须用 kebab-case**。`getComputedStyle().getPropertyValue()` 只认
  `font-size`，不认 `fontSize`；传驼峰会**静默返回空串**，导致 `fontSize`、`lineHeight`、
  `backgroundColor`、`borderTopColor`、`boxShadow`、`borderRadius`、`padding*`、`margin*`、
  `min/max-Width/Height` 等属性永远“相等”。夹具已做驼峰→短横线转换；
  写任何新的采样列表时务必同样处理，否则结论会漏掉字号/颜色/边框这类最关键的变化。

  ① 必须用生产构建 —— dev server 以 `<style>` 注入路由 CSS，同特异性平局的胜负
  与生产 `<link>` 相反；
  ② 动画/波纹会污染采样 —— 夹具已内置「静置 + 连采两次取稳定值」，但**跨运行**的
  抖动它挡不住；
  ③ 跨运行噪声里量级最大的不是滚动条，而是**容器查询重排**：估值页同代码两跑可出现成片
  `+70px / +210px` 的宽度差异（远大于多数真实回归）。因此**先跑同代码对照对**，
  建立不稳定 `(场景, 元素, 属性)` 集合，再从待判定差异中剔除（掩码差分），只报稳定差；
  纵向滚动条出现/消失会使内容宽度整体收缩 18px（差值恒为 18px），夹具已记录滚动条
  元素数供差分脚本报警；若某次基线的 `unstable` 计数明显偏高且元素数与 after 不一致，
  应**重跑该场景的基线**（必要时在 HEAD worktree 中跑），不要把采样丢元素误判为结构回归；
  ④ 仍残留的单点差异，先用「同一份代码单独跑」排除指针 hover/focus 状态抖动
  （如 antd 单选按钮的琥珀色派生色、fund-flow 卡片阴影翻转），再判定为回归。
  ⑤ **把内联样式改成 className 时，不能用默认差分脚本**：dump 的键包含 className，
  类名变化会让同一元素变成「新增/删除」而被忽略，得出假“零差异”。类名迁移的 A/B
  必须按 dump 的文档顺序对齐（`Object.entries` 顺序）逐属性比较，并允许“预期内的颜色/规格变更”清单。
  同时检查目标元素是否已被页面 `@media` 规则覆盖：内联优先级最高，改为类名后同特异性的
  媒体查询规则可能反超（真实案例：知识图谱移动端 `gap` 从 8px 变 6px）。
  ⑥ 探针只在**测试结束时的最终状态**采样：一个测试若先看 A 标签页再跳去 B，
  dump 里只有 B（真实案例：宏观测试先看商品页再切 trade，导致商品页类名完全不在 dump 中）。
  要给这类页签补证据，写一个临时 spec 让它停在目标页签，再分别用 HEAD worktree 与当前树跑探针；
  并主动 grep dump 确认新类名真的出现，避免“类没渲染”的假零差。

  **判定任何差异前先跑一次同代码对照**：这是唯一能把「回归」和「噪声」分开的手段。
  本仓库已两次靠它避免误判（ant-steps 字体度量竞态、滚动条 18px 级联）。
- **CSS 结构体检为何存在**：`feed.css` 曾残留一条改坏的编辑——规则已闭合，后面又跟了一行
  声明和孤立的 `}`。浏览器静默跳过，所以没人发现，但它让 postcss/压缩器/`@import` 直接报
  `Unexpected }`。**构建通过不等于 CSS 合法**；门禁按“顶层语句边界”判定（不猜属性名，
  避免把 `::before`、`:hover` 误判），已能拦住这类残渣。
- **全局样式目录**：`frontend/src/styles/base/` 是原 2637 行 `base.css` 按关注点拆出的 15 个分片，
  由同目录 `index.css` 按固定顺序 `@import`。页面级巨型样式同样拆到页内的
  `styles/` 或同名子目录（`NationalTeam` 9 片、`IndustryChain` 8 片、`Stock` 6 片、`Macro` 5 片、
  `Watchlist` 7 片、`Chat` 4 片、`Concept` 4 片、`Dashboard` 3 片、`Settings` 3 片、
  `Analysis/workspace` 3 片、`Quant/quant-results` 3 片、`Market/market-emotion` 3 片、
  `Settings/config-cards/market-daily-bar-manager` 4 片、`Portfolio` 5 片、`Potential` 1 片、
  `features/feed` 6 片、`features/investment-research` 8 片）；
  组件级巨型样式放在与样式同名的子目录里（如 `components/market-overview/` 7 片、
  `components/market-wind/` 3 片，入口 `index.css`）。**不要重排 `@import` 顺序**——同特异性规则靠源序决胜负，
  重排会改变层叠结果。拆分时必须用 postcss 顶层节点边界（`node.source.start.line`）切，
  不能按行号硬切：跨行的选择器列表（`a,\nb { }`）被切开会让构建直接 `Unknown word` 失败。
  拆分后的硬标准是：**构建产物 CSS 与拆分前逐字节相同**（含哈希文件名）。
- **CSS Modules**：组件私有样式用 `Xxx.module.css` + `import styles from "./Xxx.module.css"`，
  类名取短名（`root` / `meta` / `actions`），不再手写 `xxx__yyy` 前缀。试点见
  `frontend/src/components/SectionToolbar.module.css`。

### 前端请求超时

`frontend/src/api/client.ts` 里所有请求都必须经 `createAbortScope(signal, timeoutMs)` 拿
`AbortSignal`，不要直接把 `options.signal` 交给 `fetch`。原因：下载类接口（PDF 渲染、CSV 导出）
既不传 `signal` 又曾不经超时包装，后端卡住时 `await fetch` 会挂到页面关闭——用户既等不到结果
也无法取消。

- `apiRequest` 默认超时 `API_TIMEOUTS.DEFAULT`（20s），可按调用点用 `timeoutMs` 覆盖
  （如 `SCREENER` / `LONG_RUNNING` 为 300s）。
- `apiDownload` / `apiDownloadPost` 默认 `API_TIMEOUTS.LONG_RUNNING`（300s，要留给 PDF 渲染）。
- `await response.blob()` 也必须落在同一个 scope 里，否则重定向头已返回、body 卡住的情况仍会挂死。
- scope 的 `dispose()` 要放 `finally`；`isTimeout()` 用来把 `AbortError` 转成 `ApiTimeoutError`。

另外两条账号域约定（靠 code review + 测试保证，尚未脚本化）：

- **管理员写操作必须留痕**：新增/修改涉及「改别人的账号或全局配置」的接口时，在同一处调用
  `app/infrastructure/persistence/admin_audit_store.py` 的 `record_admin_action(...)`，
  记录 `action` / `target_label` / `details`（只放字段名与布尔值，**绝不写密码、Token、密钥**）。
  前端「设置 → 安全审计 → 管理员操作」直接读这张表。清理期限由 `ADMIN_AUDIT_RETENTION_DAYS` 控制。
- **草稿/会话类个人资源按 owner 过滤**：量化策略草稿（`quant_strategy_drafts.created_by`）、登录设备（`auth_sessions.user_id`）、
  「我的登录记录」（`login_audit_logs.user_id`）都必须用「登录态 user_id」过滤，越权访问统一返回 404（不要 403，
  否则会泄露资源是否存在）。新增这类「个人资源」接口时，管理员分支（看全量）要显式判断 `is_admin`，不要靠前端隐藏按钮。
- **私密配置的"空串=删除覆盖"**：写接口里私密字段传空串表示删除该用户的个人覆盖
  （`user_config_store.delete_user_config_keys`），掩码值表示"未修改"。新增"一键回退默认/继承"这类按钮时，
  必须显式把密钥字段写成空串提交（`buildCardPatch` 默认会跳过空密钥，容易"看着生效其实没清掉"）；
  `Literal` 类字段（如 `llm_api_mode`）传空串会被请求校验 422，要写回该字段的默认语义值。
  回归测试：`tests/test_llm_config_inheritance.py`、`frontend/src/pages/Settings/useSettingsForm.llmClear.test.tsx`。
- **有继承语义的卡片要声明 `skipUnchanged`**：字段留空=沿用全局的卡片（如 LLM）必须在 `cardSpecs.ts`
  里标 `skipUnchanged: true`，让 `buildCardPatch` 只提交与生效配置不同的字段；否则"用户只改了无关项却把
  继承值钉成个人覆盖"这类问题会以"管理员改了配置某些人跟不动"的形式出现，很难排查。
- **凭据只跟着端点走**：全局（管理员）配置里的密钥，只有在**端点与全局一致**时才允许被继承复用。
  判定落在两处：`app/configuration/effective.py::overlay_private`（生效配置）与
  `app/infrastructure/llm/spec.py::_shares_global_endpoint`（真正构建出网客户端处，兜底）。
  新增"用户可自定义地址"的凭据类配置（数据源、推送通道、LLM）时，必须同时实现这两层，
  否则会出现"管理员 Key 被发到用户指定地址"的凭据泄漏。
- **账号域时间戳显式传入**：`users` / `auth_sessions` / `invites` / `password_resets` / `login_audit_logs`
  的 `created_at` 由 INSERT 显式写 `now_ts()`（北京时间的字符串），不要依赖 DDL 的
  `datetime('now','localtime')`——容器里恰好设了 `TZ`，裸机/k8s 没设时会写成 UTC，两者相差 8 小时。
  回归测试见 `tests/test_account_timestamp_timezone.py`。

## 五、依赖维护

| 目标 | 做法 |
| :--- | :--- |
| 升级后端依赖 | `cd backend && uv lock --upgrade-package <pkg>` 后 `uv sync --frozen`，再跑 `make check` |
| 检查后端漏洞 | `cd backend && uv run --with pip-audit pip-audit`（当前基线：无已知漏洞） |
| 检查前端漏洞 | `cd frontend && npm audit --omit=dev`（当前基线：生产依赖 0 漏洞） |
| 前端传递依赖打补丁 | 在 `package.json` 的 `overrides` 里钉版本，别为此升级主依赖 |

`overrides` 里现有 `dompurify`：它由 `jspdf` 传递引入，3.4.14 命中多个 DOM XSS advisory，
而 `jsPDF.html()` 本仓库并未使用。等 `jspdf` 自身的 `dompurify` 依赖 ≥3.4.17 后即可删除该条。
`npm audit` 剩余项都在 vitest/esbuild 工具链上，需要 vitest 5 破坏性升级，暂缓。

## 六、测试约定

- **后端**（`backend/tests/`）：pytest + `anyio`，异步用例标 `pytestmark = pytest.mark.anyio`。
  按被测对象分文件（`test_<模块>.py`），子域可用子目录（如 `tests/agentic/`）。
  **测试必须自洽**：不得依赖 `backend/data` 里的真实运行时文件（快照、名称映射、归档日线），
  这些文件在跑过应用的开发机上一定存在，会让断言环境敏感。需要"文件不存在"的场景请显式
  `monkeypatch` 掉兜底读取路径。
- **前端**（`frontend/src/**/*.test.tsx`）：vitest + Testing Library，按组件就近放置用例。
- **E2E**（`frontend/e2e/`）：Playwright 拦截 `/api/**` 并注入夹具，不依赖真实后端，可在 CI 运行。
- **README 配图**（`frontend/scripts/capture-readme-screenshots.mjs`）：依赖真实运行实例，不进 CI，
  用法见 [README「开发与维护」](../README.md#开发与维护)。

## 七、本地调试技巧

- **交互式 API 文档**默认关闭（避免未认证访问者拉取全量路由表）。本地需要时：
  `APP_EXPOSE_DOCS=1 make backend-dev`，然后访问 `http://127.0.0.1:8000/docs`。
- **健康检查**：`/api/health/live`、`/api/health/ready`、`/api/health` 无需鉴权；
  `/api/health/metrics` 与 `/api/health/metrics/prometheus` 需要鉴权（Prometheus 抓取请用带凭据的代理）。
- **日志**：本地写 `logs/backend.log`；容器内 `docker compose logs -f backend`。
  访问日志对健康检查/轮询路径已降噪到 DEBUG，排查时把日志级别调回 INFO 以上即可。
- **数据库**：四个 SQLite 库都在 `backend/data/`（容器内 `/app/data`），
  结构与迁移见 `backend/app/infrastructure/persistence/migrations.py`。
- **连接生命周期**：SQLite 连接按「线程 + 库」复用（WAL 模式支持多连接并发读写），
  连接由每线程一个 `_ThreadConnectionBundle` 持有。线程结束时 CPython 会清空该线程的
  `threading.local` 数据，从而释放 bundle 并触发 `__del__` 自动 `close()` + 从全局注册表
  摘除。这一点很重要：项目里多处 provider 用 `with ThreadPoolExecutor(...)` 做并发抓取，
  worker 线程用完即销毁；若连接只登记在全局注册表里，线程死后就再没人能关闭它们。
  `close_connection()` / `close_all_connections()` 仍是显式关闭通道，与自动回收幂等共存。

## 八、提交与发布约定

- 按仓库 `AGENTS.md`：**修改后先说明改动内容并获得确认，不要自行 `git commit` / `git push`。**
- 发版由 tag 驱动：`make release V=vX.Y.Z` 推送标签后，GitHub Actions 构建并发布多架构镜像。
- **镜像构建/发布只在 tag 或手动触发时进行**（Actions → *Build & Publish Docker Images* → *Run workflow*）：
  推送到 `main` 只跑质量门禁 + E2E，避免每次推送都完整构建四个镜像而快速耗尽
  （私有仓库按量计费的）Actions 分钟。改动 Dockerfile / nginx.conf / 沙箱运行时时，PR 会由
  `docker-build-check.yml` 额外做一次不推送镜像的构建与冒烟。
- 破坏性配置变更必须向后兼容（见 [配置系统开发指南](configuration.md) 第六节）。

## 九、相关文档

- [架构与边界](architecture.md) — 分层、依赖环基线、Agentic/估值/潜力股链路
- [配置系统开发指南](configuration.md) — 配置来源、作用域、新增字段流程
- [数据源与降级机制](data-sources.md) — Provider 清单、熔断、限流、质量校验
- [故障排查手册](troubleshooting.md) — 启动、数据、LLM、推送与前端常见问题
- [自动推送与通知配置](push-notifications.md)
