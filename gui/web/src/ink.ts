// 「暮冬念春」设计系统 v3 —— 高级质感视觉语言。
//
// 设计理念：
// - 墨青为主：深邃墨青替代朱砂红，沉稳内敛的高级感
// - 鎏金点缀：香槟金为唯一高光，克制而珍贵
// - 纸墨延续：暖纸白底色 + 墨黑文字，保留纸质书的阅读质感
// - 衬线标题：Noto Serif SC 营造文学气息，无衬线正文保证 UI 可读性
// - 暗色模式：「夜读」质感 —— 暖黑底 + 米白字 + 鎏金点缀

export const ink = {
  // 纸色系（浅色模式）
  paper: '#FAF8F2',        // 宣纸白
  paperDeep: '#F1ECE0',    // 纸纹深
  card: '#FFFFFF',         // 卡片白
  // 墨色系
  ink: '#1A1C1A',          // 墨黑（主文字）
  inkSoft: '#454843',      // 淡墨（次要文字）
  inkFaint: '#8A8D86',     // 退墨（辅助文字）
  line: '#E6E1D4',         // 墨线（分割线）
  // 点缀色 —— v3：墨青主色 + 鎏金高光（去朱砂红）
  primary: '#0F3A3A',      // 墨青（主强调，深邃沉稳）
  primaryDeep: '#0A2A2A',  // 深墨青（hover）
  primarySoft: '#E6EFEA',  // 浅墨青（背景）
  gold: '#C6A15B',         // 鎏金（高光点缀，克制使用）
  goldDeep: '#A8843F',     // 深金（hover）
  goldSoft: '#FAF3E3',     // 浅金（背景）
  teal: '#2A7B6B',         // 石青（成功/信息）
  // 兼容旧名（逐步迁移）
  cinnabar: '#0F3A3A',     // → primary（墨青）
  cinnabarDeep: '#0A2A2A', // → primaryDeep
  cinnabarSoft: '#E6EFEA', // → primarySoft
  // 暗色模式
  night: '#121413',        // 夜墨（暗底）
  nightCard: '#1C1F1D',    // 夜卡片
  nightLine: '#2C302C',     // 夜分割线
  moonWhite: '#EDE8D8',    // 月白（暗色主文字）
  moonSoft: '#A8A294',     // 月灰（暗色次要）
  goldBright: '#D9B96F',   // 亮金（暗色强调）
} as const

export const fontStack = {
  serif: '"Noto Serif SC", "Songti SC", "SimSun", serif',
  sans: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
  mono: '"JetBrains Mono", "SF Mono", Consolas, monospace',
} as const

/** 卡片悬浮效果：上浮 + 阴影加深 */
export const cardHover = {
  transition: 'transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
  '&:hover': {
    transform: 'translateY(-2px)',
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
