// 「暮冬念春」设计系统 v4 —— 简约高级白。
//
// 设计理念（2026-09-29 用户亲定：不要纸墨/国风，要简约高级的白色）：
// - 纯粹留白：纯白卡片 + 极浅灰底，信息靠间距与层级呼吸，不靠装饰
// - 墨黑主色：主按钮/主强调使用近黑，克制而高级（Vercel/Linear 式）
// - 单点缀色：克制的蓝色作为链接/选中/焦点，成功/警告/错误用低饱和语义色
// - 发丝线：1px 极浅分割线代替色块分隔
// - 暗色模式：中性深灰（去金去青），保持可用
//
// 旧 key 保留为兼容别名（逐步迁移到新语义名）。

export const ink = {
  // —— v4 新语义 ——
  bg: '#F7F7F8',            // 应用底（极浅灰）
  surface: '#FFFFFF',       // 卡片/面板（纯白）
  surfaceDeep: '#F1F1F4',   // 下沉底
  text: '#18181B',          // 主文字（近黑）
  textSecondary: '#52525B', // 次要文字
  textTertiary: '#A1A1AA',  // 辅助文字
  hairline: '#E9E9EC',      // 发丝分割线
  primary: '#18181B',       // 主按钮/主强调（墨黑）
  primaryHover: '#000000',  // 主按钮 hover
  primarySoft: '#F4F4F5',   // 主色浅底
  accent: '#2563EB',        // 点缀蓝（链接/选中/焦点）
  accentHover: '#1D4ED8',
  accentSoft: '#EFF4FF',
  success: '#16A34A',
  successSoft: '#EDF9F0',
  warning: '#B45309',
  warningSoft: '#FEF6E7',
  error: '#DC2626',
  errorSoft: '#FDECEC',

  // —— 兼容旧名（v3 迁移） ——
  paper: '#FFFFFF',
  paperDeep: '#F4F4F5',
  card: '#FFFFFF',
  ink: '#18181B',
  inkSoft: '#52525B',
  inkFaint: '#A1A1AA',
  line: '#E9E9EC',
  primaryDeep: '#000000',
  // cinnabar（原朱砂→墨青）：现映射为点缀蓝
  cinnabar: '#2563EB',
  cinnabarDeep: '#1D4ED8',
  cinnabarSoft: '#EFF4FF',
  // gold（原鎏金）：现映射为低饱和琥珀（暖色点缀）
  gold: '#B45309',
  goldDeep: '#92400E',
  goldSoft: '#FEF6E7',
  goldBright: '#D97706',
  // teal（原石青）：现映射为低饱和绿
  teal: '#059669',

  // 暗色模式（中性）
  night: '#0B0B0D',
  nightCard: '#141417',
  nightLine: '#26262B',
  moonWhite: '#FAFAFA',
  moonSoft: '#A3A3AD',
  // 旧暗色金已去，仅保留别名避免编译断裂
} as const

export const fontStack = {
  serif: '"Noto Serif SC", "Songti SC", "SimSun", serif',
  sans: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
  mono: '"JetBrains Mono", "SF Mono", Consolas, monospace',
} as const

/** 卡片：纯白 + 发丝线 + 柔和阴影 */
export const card = {
  backgroundColor: ink.surface,
  border: `1px solid ${ink.hairline}`,
  borderRadius: 12,
  boxShadow: '0 1px 2px rgba(16, 16, 20, 0.04)',
} as const

/** 卡片悬浮效果：上浮 + 阴影加深 */
export const cardHover = {
  transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: '0 8px 24px rgba(16, 16, 20, 0.08)',
  },
} as const

/** 页面入场动画 */
export const fadeUp = {
  '@keyframes fadeUp': {
    from: { opacity: 0, transform: 'translateY(12px)' },
    to: { opacity: 1, transform: 'translateY(0)' },
  },
  animation: 'fadeUp 0.4s cubic-bezier(0.4, 0, 0.2, 1) both',
} as const

/** 交错入场（列表用，index 决定延迟） */
export const stagger = (index: number, base = 0.05) => ({
  ...fadeUp,
  animationDelay: `${Math.min(index * base, 0.5)}s`,
})
