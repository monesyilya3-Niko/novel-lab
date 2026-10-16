// 中英文双语词条词典（暮冬念春 / Exoscribe 国际化架构）。
export type Locale = 'zh-CN' | 'en-US'

export const TRANSLATIONS: Record<string, Record<Locale, string>> = {
  // 品牌与全局头部
  brand_name: {
    'zh-CN': '暮冬念春',
    'en-US': 'Exoscribe',
  },
  brand_subtitle: {
    'zh-CN': '全功能工作台',
    'en-US': 'The Vernal Engine for Fiction',
  },
  brand_initial: {
    'zh-CN': '暮',
    'en-US': 'E',
  },
  toggle_language: {
    'zh-CN': '切换为英文 (Switch to English)',
    'en-US': '切换为中文 (Switch to Chinese)',
  },
  toggle_theme_light: {
    'zh-CN': '切换暗色',
    'en-US': 'Switch to Dark Mode',
  },
  toggle_theme_dark: {
    'zh-CN': '切换为跟随系统',
    'en-US': 'Switch to System Mode',
  },
  toggle_theme_system: {
    'zh-CN': '切换亮色',
    'en-US': 'Switch to Light Mode',
  },
  command_palette_trigger: {
    'zh-CN': '命令面板 (Ctrl+K)',
    'en-US': 'Command Palette (Ctrl+K)',
  },

  // 导航分组
  nav_group_create: {
    'zh-CN': '创作',
    'en-US': 'Creation',
  },
  nav_group_manage: {
    'zh-CN': '管理',
    'en-US': 'Management',
  },
  nav_group_help: {
    'zh-CN': '帮助',
    'en-US': 'Help',
  },

  // 导航选项
  nav_home: {
    'zh-CN': '首页',
    'en-US': 'Home',
  },
  nav_analysis: {
    'zh-CN': '分析拆书',
    'en-US': 'Deconstruction',
  },
  nav_writing: {
    'zh-CN': '辅助写作',
    'en-US': 'Writing Studio',
  },
  nav_quality: {
    'zh-CN': '质量检验',
    'en-US': 'Quality Guard',
  },
  nav_assets: {
    'zh-CN': '资产库',
    'en-US': 'Asset Matrix',
  },
  nav_advanced: {
    'zh-CN': '高级功能',
    'en-US': 'Advanced Tools',
  },
  nav_system: {
    'zh-CN': '系统',
    'en-US': 'System',
  },
  nav_settings: {
    'zh-CN': '设置',
    'en-US': 'Settings',
  },
  nav_admin: {
    'zh-CN': '管理后台',
    'en-US': 'Administration',
  },
  nav_help: {
    'zh-CN': '帮助中心',
    'en-US': 'Help Center',
  },

  // 编辑器与底栏诊断
  editor_placeholder: {
    'zh-CN': '在此粘贴或编写章节正文……',
    'en-US': 'Paste or compose chapter draft here...',
  },
  editor_poison_check: {
    'zh-CN': '🛡️ 毒点避雷排查',
    'en-US': '🛡️ Anti-Poison Check',
  },
  editor_deslop_check: {
    'zh-CN': '✨ 去AI味体检',
    'en-US': '✨ Anti-Slop Audit',
  },
  editor_constitution_check: {
    'zh-CN': '📜 设定宪法审查',
    'en-US': '📜 Novel Constitution',
  },
  editor_close_return: {
    'zh-CN': '关闭并返回写作',
    'en-US': 'Close & Return',
  },
  editor_word_unit: {
    'zh-CN': '字',
    'en-US': 'words',
  },
  editor_target_met: {
    'zh-CN': '已达目标',
    'en-US': 'Target Reached',
  },
  editor_target_prefix: {
    'zh-CN': '目标',
    'en-US': 'Target',
  },

  // 通用动作与状态
  action_save: {
    'zh-CN': '保存',
    'en-US': 'Save',
  },
  action_cancel: {
    'zh-CN': '取消',
    'en-US': 'Cancel',
  },
  action_confirm: {
    'zh-CN': '确定',
    'en-US': 'Confirm',
  },
  action_close: {
    'zh-CN': '关闭',
    'en-US': 'Close',
  },
  action_export: {
    'zh-CN': '导出',
    'en-US': 'Export',
  },
  action_import: {
    'zh-CN': '导入',
    'en-US': 'Import',
  },
  action_retry: {
    'zh-CN': '重试',
    'en-US': 'Retry',
  },
  action_search: {
    'zh-CN': '搜索',
    'en-US': 'Search',
  },

  // 平台与出海适配
  platform_panel_title: {
    'zh-CN': '多平台适配与签约诊断',
    'en-US': 'Multi-Platform Adaptation & Submission Audit',
  },
  platform_tab_diagnose: {
    'zh-CN': '多平台合规与签约诊断',
    'en-US': 'Platform Compliance & Submission Audit',
  },
  platform_tab_litrpg: {
    'zh-CN': 'LitRPG 属性面板与海外排版',
    'en-US': 'LitRPG Stat Box & Formatter',
  },
  platform_check_compliance: {
    'zh-CN': '检查合规性',
    'en-US': 'Check Compliance',
  },
  platform_diagnose_action: {
    'zh-CN': '🎯 签约过稿深度诊断',
    'en-US': '🎯 Submission Readiness Audit',
  },
  platform_parse_stat_box: {
    'zh-CN': '解析属性面板',
    'en-US': 'Parse Stat Box',
  },
  platform_format_royalroad: {
    'zh-CN': '⚡ Royal Road 一键排版',
    'en-US': '⚡ Format for Royal Road',
  },
  platform_copy_code: {
    'zh-CN': '复制排版代码',
    'en-US': 'Copy Formatted Code',
  },
  platform_copied: {
    'zh-CN': '已复制！',
    'en-US': 'Copied!',
  },
  platform_load_sample: {
    'zh-CN': '载入样例',
    'en-US': 'Load Sample',
  },

  // 毒点排查与弃坑避雷
  poison_tab_scanner: {
    'zh-CN': '毒点快速排查 (本地规则)',
    'en-US': 'Anti-Poison Scanner (Local)',
  },
  poison_tab_library: {
    'zh-CN': '弃坑避雷规范库 (10大红线)',
    'en-US': 'Fatal Taboo Library (10 Rules)',
  },
  poison_desc: {
    'zh-CN': '基于商业网文大数据提炼的纯本地 10 大核心毒点检测器（过度憋屈、圣母资敌、降智舔狗、战力断崖、长篇说教、女配白送、绿帽擦边等）。不消耗大模型 Token，零网络延迟。',
    'en-US': 'Local rule-based scanner for 10 fatal novel taboos (excessive suffering, enemy mercy, simp behavior, power collapse, preachy monologue, etc.). Zero token cost, zero latency.',
  },
  poison_placeholder: {
    'zh-CN': '请在此粘贴需要检测的章节正文或剧情草稿...',
    'en-US': 'Paste chapter draft or plot outline to inspect for fatal taboos...',
  },
  poison_scan_action: {
    'zh-CN': '一键扫描毒点',
    'en-US': 'Scan for Taboos',
  },
  poison_clear: {
    'zh-CN': '清空',
    'en-US': 'Clear',
  },
  poison_result_title: {
    'zh-CN': '检测结果：',
    'en-US': 'Audit Result:',
  },
  poison_score_label: {
    'zh-CN': '毒点扣分值：',
    'en-US': 'Penalty Score:',
  },
  poison_issues_count: {
    'zh-CN': '检出问题：',
    'en-US': 'Issues Found:',
  },
  poison_score_unit: {
    'zh-CN': '分（0分最佳）',
    'en-US': 'pts (0 is cleanest)',
  },
  poison_issues_unit: {
    'zh-CN': '处',
    'en-US': 'found',
  },
  poison_clean_alert: {
    'zh-CN': '干得漂亮！本段正文未命中任何已知的恶性毒点或降智情节，行文节奏舒畅。',
    'en-US': 'Excellent! No major narrative taboos or fatal drop-off points detected.',
  },
  poison_findings_title: {
    'zh-CN': '检出问题清单与修改建议：',
    'en-US': 'Detected Issues & Revision Guide:',
  },
  poison_matched_prefix: {
    'zh-CN': '命中关键词：',
    'en-US': 'Trigger: ',
  },
  poison_reader_pain: {
    'zh-CN': '【读者痛点】',
    'en-US': '[Reader Dropoff]',
  },
  poison_fix_guide: {
    'zh-CN': '【修改建议】',
    'en-US': '[Actionable Fix]',
  },
  poison_library_desc: {
    'zh-CN': '数百万商业读者验证的 10 大弃坑毒点红线清单。下笔前对照自检，避免因为一处剧情瑕疵引发书评区差评暴动。',
    'en-US': '10 fatal taboo rules verified by millions of webnovel readers. Review before publishing to avoid mass reader dropoffs.',
  },
  poison_fatal_tag: {
    'zh-CN': '绝对红线',
    'en-US': 'Fatal Redline',
  },
  poison_high_tag: {
    'zh-CN': '高危警报',
    'en-US': 'High Warning',
  },
  poison_phenomenon: {
    'zh-CN': '现象描述：',
    'en-US': 'Description: ',
  },
  poison_reader_reaction: {
    'zh-CN': '读者反应：',
    'en-US': 'Reader Reaction: ',
  },
  poison_taboo_guide: {
    'zh-CN': '【避雷指南】',
    'en-US': '[Avoidance Guide]',
  },
}
