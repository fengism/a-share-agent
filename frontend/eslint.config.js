import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', '**/._*'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // 依赖数组漏写会导致 stale closure（读到上一次渲染的 state/props）——
      // 这类 bug 极难复现。插件默认给的是 warn，而 CI 跑的是不带
      // --max-warnings 的 `eslint .`，warn 不会阻断流水线，等于形同虚设。
      // 当前仓库该项 0 告警，直接升为 error。
      'react-hooks/exhaustive-deps': 'error',
      // 该规则的目标是保证 Fast Refresh 可用，属于开发体验而非正确性，
      // 保留 warn 即可，不要让它阻断 CI（与上面的正确性规则区分开）。
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
)
