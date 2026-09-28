// 「墨」设计系统 v2 —— 为 novel-lab 打造的文学质感视觉语言。
//
// 设计理念：
// - 纸与墨：暖纸白底色 + 墨黑文字，朱砂红点缀，还原纸质书的阅读质感
// - 衬线标题：Noto Serif SC 营造文学气息，无衬线正文保证 UI 可读性
// - 克制装饰：细分割线、柔和阴影、呼吸感留白，拒绝廉价渐变
// - 暗色模式：不是简单反色，而是"夜读"质感 —— 暖黑底 + 米白字 + 鎏金点缀

export const ink = {
  // 纸色系（浅色模式）
  paper: '#FAF7F0',        // 宣纸白
  paperDeep: '#F3EEE3',    // 纸纹深
  card: '#FFFFFF',         // 卡片白
  // 墨色系
  ink: '#1C1A16',          // 墨黑（主文字）
  inkSoft: '#4A463D',      // 淡墨（次要文字）
  inkFaint: '#8A8478',     // 退墨（辅助文字）
  line: '#E8E2D5',         // 墨线（分割线）
  // 点缀色
  cinnabar: '#C73E3A',     // 朱砂红（主强调）
  cinnabarDeep: '#A93226', // 深朱砂（hover）
  cinnabarSoft: '#FBE9E7', // 浅朱砂（背景）
  gold: '#B08D4C',         // 鎏金（次强调）
  teal: '#2A7B6B',         // 石青（成功/信息）
  // 暗色模式
  night: '#141210',        // 夜墨（暗底）
  nightCard: '#1E1B17',    // 夜卡片
  nightLine: '#2E2A24',    // 夜分割线
  moonWhite: '#EDE6D6',    // 月白（暗色主文字）
  moonSoft: '#A69E8C',     // 月灰（暗色次要）
  goldBright: '#D4A574',   // 亮金（暗色强调）
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
