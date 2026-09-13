import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'

export default tseslint.config(
  { ignores: ['dist/', 'node_modules/', '*.cjs'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs['recommended-latest'],
  {
    rules: {
      // 存量代码大量 `as` 断言与非空断言，P3 API 层重构时统一收敛；
      // 现阶段先拦 error 级问题，风格类交给 Prettier。
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      // v6 新规则（React Compiler 时代）：存量"effect 内初始加载"是合法常见
      // 模式，P3 重构时逐处治理；暂记 warning 不作门禁。
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
)
