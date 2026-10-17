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

  // 去 AI 味全维度诊断与润色 (DeslopPanel)
  deslop_title: {
    'zh-CN': '去 AI 味全维度诊断与润色',
    'en-US': 'Anti-Slop Full-Spectrum Diagnostics & Polish',
  },
  deslop_desc: {
    'zh-CN': '精准扫描假大空修辞、同义反复、直陈式情绪喊话、机械排比与「让」字被动句',
    'en-US': 'Precision scan for LLM clichés, tautologies, filter words, mechanical parallelism, and passive phrasing',
  },
  deslop_btn_compare: {
    'zh-CN': '一键生成去味稿并对比',
    'en-US': 'Generate Polished Draft & Compare',
  },
  deslop_placeholder: {
    'zh-CN': '在此粘贴待检测的章节或片段……（支持万字长文快速诊断）',
    'en-US': 'Paste chapter or snippet to diagnose... (supports quick scan of 10k+ words)',
  },
  deslop_char_count: {
    'zh-CN': '当前字数：',
    'en-US': 'Length: ',
  },
  deslop_chars_unit: {
    'zh-CN': '字',
    'en-US': 'chars',
  },
  deslop_mode_auto: {
    'zh-CN': '双语自适应',
    'en-US': 'Bilingual Auto',
  },
  deslop_mode_zh: {
    'zh-CN': '中文网文',
    'en-US': 'Chinese Webnovel',
  },
  deslop_mode_en: {
    'zh-CN': 'Exoscribe 英文',
    'en-US': 'Exoscribe English',
  },
  deslop_scanning: {
    'zh-CN': '全维扫描中…',
    'en-US': 'Scanning...',
  },
  deslop_btn_diagnose: {
    'zh-CN': '开始去 AI 味诊断',
    'en-US': 'Start Anti-Slop Diagnosis',
  },
  deslop_score_title: {
    'zh-CN': 'AI 味指数（越低越自然）',
    'en-US': 'Slop Index (lower is more natural)',
  },
  deslop_suggestions_title: {
    'zh-CN': '核心优化建议',
    'en-US': 'Key Suggestions',
  },
  deslop_clean_success: {
    'zh-CN': '✓ 文风非常自然生动，未检测到典型 AI 模板句式与机械套路！',
    'en-US': '✓ Prose is exceptionally natural and vivid, no typical AI clichés or mechanical tropes detected!',
  },
  deslop_word_count: {
    'zh-CN': '有效字数',
    'en-US': 'Word Count',
  },
  deslop_western_word_count: {
    'zh-CN': '西文词数',
    'en-US': 'Western Words',
  },
  deslop_sentence_count: {
    'zh-CN': '句子总数',
    'en-US': 'Sentences',
  },
  deslop_issues_found: {
    'zh-CN': '命中疑点',
    'en-US': 'Issues Found',
  },
  deslop_count_unit: {
    'zh-CN': '处',
    'en-US': 'found',
  },
  deslop_adverb_density: {
    'zh-CN': '-ly 副词占比',
    'en-US': '-ly Adverb Ratio',
  },
  deslop_rang_density: {
    'zh-CN': '「让」字千字密度',
    'en-US': 'Rang Passive Density',
  },
  deslop_issues_title: {
    'zh-CN': '问题定位与逐句优化清单',
    'en-US': 'Issue Locations & Sentence Optimization Checklist',
  },
  deslop_no_issues: {
    'zh-CN': '未发现需整改的 AI 模板句式',
    'en-US': 'No AI template phrasing requiring revision found',
  },
  deslop_optimize_tip: {
    'zh-CN': '💡 优化建议：',
    'en-US': '💡 Suggestion: ',
  },
  deslop_empty_input_error: {
    'zh-CN': '请输入需要诊断的章节文本',
    'en-US': 'Please enter chapter text to diagnose',
  },
  deslop_error_prefix: {
    'zh-CN': '诊断失败: ',
    'en-US': 'Diagnosis failed: ',
  },

  // 双栏对比审校视图 (DiffReviewView)
  diff_title: {
    'zh-CN': '双栏对比审校',
    'en-US': 'Side-by-Side Review',
  },
  diff_orig_prefix: {
    'zh-CN': '原稿',
    'en-US': 'Original',
  },
  diff_polish_prefix: {
    'zh-CN': '润色稿',
    'en-US': 'Polished',
  },
  diff_paras_unit: {
    'zh-CN': '段',
    'en-US': 'paras',
  },
  diff_copy_btn: {
    'zh-CN': '复制润色稿',
    'en-US': 'Copy Polished',
  },
  diff_copied: {
    'zh-CN': '已复制！',
    'en-US': 'Copied!',
  },
  diff_reject_btn: {
    'zh-CN': '放弃改动',
    'en-US': 'Discard',
  },
  diff_accept_btn: {
    'zh-CN': '采纳润色稿',
    'en-US': 'Accept Polish',
  },
  diff_orig_header: {
    'zh-CN': '原稿（修改前）',
    'en-US': 'Original Draft (Before)',
  },
  diff_polish_header: {
    'zh-CN': 'AI 润色 / 去味优化稿',
    'en-US': 'AI Polish / Anti-Slop Revision (After)',
  },
  diff_empty_para: {
    'zh-CN': '（段落留白）',
    'en-US': '(Blank paragraph)',
  },

  // 创作工作台顶栏与流水线 (WritingWorkbench)
  workbench_mode_studio: {
    'zh-CN': '沉浸创作室 (Studio)',
    'en-US': 'Writing Studio',
  },
  workbench_mode_pipeline: {
    'zh-CN': '工坊流水线 (Pipeline)',
    'en-US': 'Craft Pipeline',
  },
  pipeline_tab_inject: {
    'zh-CN': '资产注入',
    'en-US': 'Asset Injection',
  },
  pipeline_tab_generate: {
    'zh-CN': 'AI 章节生成',
    'en-US': 'Chapter Generation',
  },
  pipeline_tab_score: {
    'zh-CN': '单章质检打分',
    'en-US': 'Quality Scoring',
  },
  pipeline_tab_assemble: {
    'zh-CN': '拆书资产组装',
    'en-US': 'Deconstruction Matrix',
  },
  pipeline_tab_style: {
    'zh-CN': '文风模型分析',
    'en-US': 'Voice & Style Modeling',
  },
  pipeline_tab_extras: {
    'zh-CN': '创作者企划中心',
    'en-US': 'Creator Project Hub',
  },
  pipeline_tab_deslop: {
    'zh-CN': '去 AI 味实验室',
    'en-US': 'Anti-Slop Lab',
  },
  pipeline_tab_poison: {
    'zh-CN': '灵感与毒点避雷工坊',
    'en-US': 'Inspiration & Taboo Shield',
  },
  pipeline_tab_essence: {
    'zh-CN': '小说精华数据库',
    'en-US': 'Fiction Essence Vault',
  },

  // 创作扩展企划中心 (WritingExtras)
  extras_project_label: {
    'zh-CN': '写作项目',
    'en-US': 'Project',
  },
  extras_project_desc: {
    'zh-CN': '大纲、人物、便签、创作者仪表盘与导出均按项目隔离',
    'en-US': 'Outlines, characters, notes, dashboard, and exports are scoped by project',
  },
  extras_no_project_alert: {
    'zh-CN': '请先在「写作」页签新建写作项目',
    'en-US': 'Please create a writing project in the Writing Studio first',
  },
  extras_tab_outline: {
    'zh-CN': '大纲架构',
    'en-US': 'Outline & Structure',
  },
  extras_tab_character: {
    'zh-CN': '人物卡与关系',
    'en-US': 'Characters & Relations',
  },
  extras_tab_notes: {
    'zh-CN': '灵感便签',
    'en-US': 'Inspiration Notes',
  },
  extras_tab_dashboard: {
    'zh-CN': '创作者仪表盘',
    'en-US': 'Creator Dashboard',
  },
  extras_tab_export: {
    'zh-CN': '规范导出',
    'en-US': 'Manuscript Export',
  },

  // 大纲架构面板 (OutlinePanel)
  extras_outline_volume: {
    'zh-CN': '卷',
    'en-US': 'Vol',
  },
  extras_outline_chapter: {
    'zh-CN': '章',
    'en-US': 'Ch',
  },
  extras_outline_status_planned: {
    'zh-CN': '待写',
    'en-US': 'Planned',
  },
  extras_outline_status_writing: {
    'zh-CN': '写作中',
    'en-US': 'Drafting',
  },
  extras_outline_status_done: {
    'zh-CN': '已完成',
    'en-US': 'Completed',
  },
  extras_outline_add_btn: {
    'zh-CN': '新增分卷 / 章节',
    'en-US': 'Add Volume / Chapter',
  },
  extras_outline_hook_template_btn: {
    'zh-CN': '🚀 引用黄金三章模板',
    'en-US': '🚀 First 3 Chapters Template',
  },
  extras_outline_empty: {
    'zh-CN': '还没有大纲，先从第一卷/第一章开始规划架构吧',
    'en-US': 'No outlines yet. Start planning from Volume 1 or Chapter 1',
  },
  extras_outline_edit_title: {
    'zh-CN': '编辑大纲',
    'en-US': 'Edit Outline',
  },
  extras_outline_new_title: {
    'zh-CN': '新增大纲架构',
    'en-US': 'New Outline Item',
  },
  extras_outline_kind: {
    'zh-CN': '类型',
    'en-US': 'Type',
  },
  extras_outline_kind_volume: {
    'zh-CN': '分卷（Volume）',
    'en-US': 'Volume',
  },
  extras_outline_kind_chapter: {
    'zh-CN': '章节（Chapter）',
    'en-US': 'Chapter',
  },
  extras_outline_item_title: {
    'zh-CN': '标题',
    'en-US': 'Title',
  },
  extras_outline_summary: {
    'zh-CN': '内容概要 / 剧情线',
    'en-US': 'Summary / Plotline',
  },
  extras_outline_summary_ph: {
    'zh-CN': '这一卷/章的核心冲突、情绪线、重要伏笔……',
    'en-US': 'Core conflict, emotional arc, key foreshadowing for this volume/chapter...',
  },
  extras_outline_status: {
    'zh-CN': '状态',
    'en-US': 'Status',
  },
  extras_outline_template_dialog_title: {
    'zh-CN': '🚀 黄金三章开篇模型库',
    'en-US': '🚀 First 3 Chapters Hook Models',
  },
  extras_outline_template_dialog_subtitle: {
    'zh-CN': '内置 10 大提升留存率的成熟开篇节拍',
    'en-US': 'Built-in 10 battle-tested beats to maximize reader retention',
  },
  extras_outline_template_select: {
    'zh-CN': '选择开篇模板',
    'en-US': 'Select Opening Template',
  },
  extras_outline_template_first300: {
    'zh-CN': '🔥 前 300 字吸睛钩子：',
    'en-US': '🔥 First 300 Words Hook:',
  },
  extras_outline_template_beat1: {
    'zh-CN': '第 1 章节拍（生死危机与冲突）：',
    'en-US': 'Chapter 1 Beat (Crisis & Immediate Conflict):',
  },
  extras_outline_template_beat2: {
    'zh-CN': '第 2 章节拍（压迫激化与转机）：',
    'en-US': 'Chapter 2 Beat (Escalation & Opportunity):',
  },
  extras_outline_template_beat3: {
    'zh-CN': '第 3 章节拍（首爽破局与爽点兑现）：',
    'en-US': 'Chapter 3 Beat (First Payoff & Breakthrough):',
  },
  extras_outline_template_apply: {
    'zh-CN': '一键应用为前三章大纲',
    'en-US': 'Apply as Chapters 1-3 Outline',
  },

  // 人物卡与关系网 (CharacterPanel)
  extras_char_add_btn: {
    'zh-CN': '新建人物卡',
    'en-US': 'New Character Card',
  },
  extras_char_empty: {
    'zh-CN': '还没有人物卡，先给主角建立第一张人设立体档案吧',
    'en-US': 'No characters yet. Create a dimensional profile for your protagonist',
  },
  extras_char_edit_title: {
    'zh-CN': '编辑人物卡档案',
    'en-US': 'Edit Character Profile',
  },
  extras_char_new_title: {
    'zh-CN': '新建人物卡档案',
    'en-US': 'New Character Profile',
  },
  extras_char_name: {
    'zh-CN': '姓名',
    'en-US': 'Name',
  },
  extras_char_random_name: {
    'zh-CN': '🎲 随机名',
    'en-US': '🎲 Random Name',
  },
  extras_char_role: {
    'zh-CN': '定位',
    'en-US': 'Role',
  },
  extras_char_role_ph: {
    'zh-CN': '如：男主 / 女主 / 幕后黑手 / 剑术师尊……',
    'en-US': 'e.g. Protagonist / Deuteragonist / Hidden Master / Antagonist...',
  },
  extras_char_camp: {
    'zh-CN': '所属阵营',
    'en-US': 'Faction / Alignment',
  },
  extras_char_camp_protagonist: {
    'zh-CN': '主角阵营',
    'en-US': 'Protagonist Faction',
  },
  extras_char_camp_antagonist: {
    'zh-CN': '反派宿敌',
    'en-US': 'Antagonist / Rival',
  },
  extras_char_camp_neutral: {
    'zh-CN': '中立势力',
    'en-US': 'Neutral Power',
  },
  extras_char_camp_sect: {
    'zh-CN': '宗门高层',
    'en-US': 'Sect Leadership',
  },
  extras_char_camp_hermit: {
    'zh-CN': '世外高人',
    'en-US': 'Hermit Sage',
  },
  extras_char_rel_target: {
    'zh-CN': '关系关联角色',
    'en-US': 'Related Character',
  },
  extras_char_rel_target_ph: {
    'zh-CN': '如：林天（留空则不设）',
    'en-US': 'e.g. Lin Tian (blank if none)',
  },
  extras_char_rel_type: {
    'zh-CN': '关系类型',
    'en-US': 'Relation Type',
  },
  extras_char_rel_type_ph: {
    'zh-CN': '如：宿敌 / 师徒 / 知己',
    'en-US': 'e.g. Rival / Master / Ally',
  },
  extras_char_desc: {
    'zh-CN': '性格特质、人设背景与人物弧光',
    'en-US': 'Personality, Backstory & Character Arc',
  },
  extras_char_desc_ph: {
    'zh-CN': '外貌特征、口癖、行为动机、阴暗面、核心羁绊……',
    'en-US': 'Appearance, catchphrases, core motivation, fatal flaw, relationships...',
  },

  // 灵感便签 (NotePanel)
  extras_note_add_btn: {
    'zh-CN': '速记灵感',
    'en-US': 'Quick Note',
  },
  extras_note_empty: {
    'zh-CN': '灵感稍纵即逝，随时把冒出的金句、桥段、反转记在这里',
    'en-US': 'Inspiration is fleeting. Record memorable lines, twists, and tropes here anytime',
  },
  extras_note_untitled: {
    'zh-CN': '（无标题灵感）',
    'en-US': '(Untitled Note)',
  },
  extras_note_edit_title: {
    'zh-CN': '编辑灵感便签',
    'en-US': 'Edit Note',
  },
  extras_note_new_title: {
    'zh-CN': '速记一条灵感',
    'en-US': 'New Inspiration Note',
  },
  extras_note_title: {
    'zh-CN': '标题',
    'en-US': 'Title',
  },
  extras_note_content: {
    'zh-CN': '灵感详情',
    'en-US': 'Content',
  },
  extras_note_content_ph: {
    'zh-CN': '突然想到的战斗机制、反转包袱、人物对白金句……',
    'en-US': 'Combat mechanics, reveal setups, punchlines, witty dialogue...',
  },

  // 创作者仪表盘 (DashboardPanel)
  extras_dash_title: {
    'zh-CN': '创作者数据大盘',
    'en-US': 'Creator Analytics Dashboard',
  },
  extras_dash_timespan: {
    'zh-CN': '时间跨度',
    'en-US': 'Time Range',
  },
  extras_dash_7days: {
    'zh-CN': '近 7 天',
    'en-US': 'Last 7 Days',
  },
  extras_dash_30days: {
    'zh-CN': '近 30 天',
    'en-US': 'Last 30 Days',
  },
  extras_dash_90days: {
    'zh-CN': '近 90 天',
    'en-US': 'Last 90 Days',
  },
  extras_dash_loading: {
    'zh-CN': '正在加载创作者大盘数据……',
    'en-US': 'Loading analytics data...',
  },
  extras_dash_today_words: {
    'zh-CN': '今日码字',
    'en-US': "Today's Words",
  },
  extras_dash_words_unit: {
    'zh-CN': '字',
    'en-US': 'words',
  },
  extras_dash_total_words: {
    'zh-CN': '全书总字数',
    'en-US': 'Total Book Words',
  },
  extras_dash_chapters_unit: {
    'zh-CN': '章已落盘',
    'en-US': 'chapters written',
  },
  extras_dash_streak: {
    'zh-CN': '连续更文',
    'en-US': 'Writing Streak',
  },
  extras_dash_streak_unit: {
    'zh-CN': '天不断更',
    'en-US': 'day streak',
  },
  extras_dash_today_chapters: {
    'zh-CN': '今日成章',
    'en-US': "Today's Chapters",
  },
  extras_dash_chapters_done: {
    'zh-CN': '章',
    'en-US': 'chapters',
  },
  extras_dash_creation_chart_title: {
    'zh-CN': '每日码字与创作速率平滑折线',
    'en-US': 'Daily Words & Writing Rate Trajectory',
  },
  extras_dash_wave_chart_title: {
    'zh-CN': '章节情绪张力起伏波形（起承转合）',
    'en-US': 'Narrative Tension & Pacing Waveform',
  },
  extras_dash_benchmark: {
    'zh-CN': '对标神作',
    'en-US': 'Benchmark',
  },
  extras_dash_bm_classic: {
    'zh-CN': '经典起承转合',
    'en-US': 'Classic 4-Act Pacing',
  },
  extras_dash_bm_fast_hook: {
    'zh-CN': '黄金强入局',
    'en-US': 'Golden In Medias Res',
  },
  extras_dash_bm_steady: {
    'zh-CN': '稳健发育流',
    'en-US': 'Steady Progression',
  },
  extras_dash_bm_face_slap: {
    'zh-CN': '压抑打脸流',
    'en-US': 'Tension & Reversal',
  },
  extras_dash_btn_analyze: {
    'zh-CN': '测算草稿',
    'en-US': 'Analyze Draft',
  },
  extras_dash_radar_title: {
    'zh-CN': '网文爽点节奏多维雷达图',
    'en-US': 'Narrative Rhythm & Payoff Radar',
  },
  extras_dash_radar_subtitle: {
    'zh-CN': '爽点推进、打脸期待、信息密度、金手指进化、章末钩子全维扫描',
    'en-US': 'Payoff velocity, anticipation, information density, power progression, end-of-chapter hooks',
  },

  // 规范多格式导出 (ExportPanel)
  extras_export_title: {
    'zh-CN': '导出全书作品',
    'en-US': 'Export Entire Book',
  },
  extras_export_desc: {
    'zh-CN': '纯 Python 标准库零依赖规范导出，支持直接交付排版、投稿或本地备份',
    'en-US': 'Zero-dependency pure standard library export for publishing, submission, or backup',
  },
  extras_export_docx_title: {
    'zh-CN': 'Word 规范文档 (.docx)',
    'en-US': 'Standard Word Document (.docx)',
  },
  extras_export_docx_tag: {
    'zh-CN': '国内出版 / 责编首选',
    'en-US': 'Industry Standard Submission',
  },
  extras_export_docx_desc: {
    'zh-CN': '符合网文投稿与出版规约，标题居中、章节居左、正文首行缩进 2 字符、1.5 倍行距，Word / WPS 秒开。',
    'en-US': 'Standard formatting: centered title, left-aligned chapters, indented paragraphs, 1.5 line spacing. Compatible with Word/WPS.',
  },
  extras_export_docx_btn: {
    'zh-CN': '导出 Word (.docx)',
    'en-US': 'Export Word (.docx)',
  },
  extras_export_epub_title: {
    'zh-CN': '标准电子书 (.epub)',
    'en-US': 'Standard eBook (.epub)',
  },
  extras_export_epub_tag: {
    'zh-CN': 'Kindle / Apple Books',
    'en-US': 'Kindle / Apple Books',
  },
  extras_export_epub_desc: {
    'zh-CN': 'EPUB 3.0 出版规范容器，无压缩 mimetype 居首，内嵌完整目录导航与样式，适配主流电子阅读器。',
    'en-US': 'EPUB 3.0 container with uncompressed mimetype, embedded navigation index, and responsive styling for e-readers.',
  },
  extras_export_epub_btn: {
    'zh-CN': '导出 EPUB (.epub)',
    'en-US': 'Export EPUB (.epub)',
  },
  extras_export_shunn_title: {
    'zh-CN': '国际标准文稿 (.txt)',
    'en-US': 'International Standard Manuscript (.txt)',
  },
  extras_export_shunn_tag: {
    'zh-CN': 'William Shunn SMF 规约',
    'en-US': 'William Shunn SMF Format',
  },
  extras_export_shunn_desc: {
    'zh-CN': '国际奇幻与科幻期刊通用投稿规范：页眉联系人、百字取整字数估算、居中标题与 # 场景分界符。',
    'en-US': 'Standard Manuscript Format (SMF) for English speculative fiction: contact block, word count rounding, centered header, # breaks.',
  },
  extras_export_shunn_btn: {
    'zh-CN': '导出 Shunn 文稿',
    'en-US': 'Export Shunn Manuscript',
  },
  extras_export_md_title: {
    'zh-CN': 'Markdown 结构化 (.md)',
    'en-US': 'Structured Markdown (.md)',
  },
  extras_export_md_tag: {
    'zh-CN': '跨平台排版首选',
    'en-US': 'Cross-platform Markdown',
  },
  extras_export_md_desc: {
    'zh-CN': '规范二级标题与元数据，适合导入 Obsidian、Typora、Notion 或多平台分发工具。',
    'en-US': 'Clean headings and metadata, ideal for Obsidian, Typora, Notion, or multi-platform distribution.',
  },
  extras_export_md_btn: {
    'zh-CN': '导出 Markdown (.md)',
    'en-US': 'Export Markdown (.md)',
  },
  extras_export_txt_title: {
    'zh-CN': '纯文本格式 (.txt)',
    'en-US': 'Plain Text Format (.txt)',
  },
  extras_export_txt_tag: {
    'zh-CN': '通用无格式备份',
    'en-US': 'Universal Plain Text',
  },
  extras_export_txt_desc: {
    'zh-CN': 'UTF-8 标准编码，按章号纯净拼接，各大网文作家后台直接全选粘贴无格式污染。',
    'en-US': 'UTF-8 standard encoding, clean chapter stitching without formatting artifacts. Direct paste ready.',
  },
  extras_export_txt_btn: {
    'zh-CN': '导出纯文本 (.txt)',
    'en-US': 'Export Plain Text (.txt)',
  },

  // 灵感工坊 (InspirationWorkbench) - 8大标签页与各子模块
  inspiration_tab_name: {
    'zh-CN': '起名工坊 (离线智能)',
    'en-US': 'Smart Name Generator (Offline AI)',
  },
  inspiration_tab_hook: {
    'zh-CN': '开篇钩子库 (黄金三章)',
    'en-US': 'Opening Hooks (First 3 Chapters)',
  },
  inspiration_tab_goldfinger: {
    'zh-CN': '金手指机制库 (12大外挂)',
    'en-US': 'Power & Cheat Mechanics (12 Archetypes)',
  },
  inspiration_tab_shuangdian: {
    'zh-CN': '爽点打脸设计 (三段闭环)',
    'en-US': 'Trope & Climax Catharsis (3-Stage Loop)',
  },
  inspiration_tab_world: {
    'zh-CN': '世界观体系 (力量阶梯)',
    'en-US': 'Worldbuilding Systems (Power Ladder)',
  },
  inspiration_tab_dialogue: {
    'zh-CN': '名场面台词库 (反AI对话)',
    'en-US': 'Signature Dialogue & Anti-Slop (Spoken)',
  },
  inspiration_tab_character: {
    'zh-CN': '爆款人设矩阵 (反差弧光)',
    'en-US': 'Character Persona & Contrast Matrix',
  },
  inspiration_tab_emotion: {
    'zh-CN': '情绪高潮演出 (五感通感)',
    'en-US': 'Emotional Climax & Sensory Show-Don\'t-Tell',
  },

  // 1. 起名工坊
  inspiration_name_desc: {
    'zh-CN': '纯本地离线起名算法：自动结合古典意象与现代网感，规避烂大街套路名（如林动、萧炎式流水线），点击药丸直接复制到剪贴板。',
    'en-US': 'Pure local offline naming algorithm: fuses classical imagery and modern web feel, avoids generic cliché names. Click any chip to copy directly to clipboard.',
  },
  inspiration_name_kind_label: {
    'zh-CN': '生成类别',
    'en-US': 'Category',
  },
  inspiration_name_kind_character: {
    'zh-CN': '人物角色',
    'en-US': 'Character',
  },
  inspiration_name_kind_title: {
    'zh-CN': '爆款书名 (网文标题)',
    'en-US': 'Catchy Book Title',
  },
  inspiration_name_kind_sect: {
    'zh-CN': '宗门 / 仙门',
    'en-US': 'Sect / Clan',
  },
  inspiration_name_kind_corp: {
    'zh-CN': '集团 / 财阀',
    'en-US': 'Corporation / Conglomerate',
  },
  inspiration_name_kind_team: {
    'zh-CN': '电竞 / 战队',
    'en-US': 'Esports Team',
  },
  inspiration_name_kind_shelter: {
    'zh-CN': '末世 / 避难所',
    'en-US': 'Apocalyptic Shelter',
  },
  inspiration_name_kind_org: {
    'zh-CN': '怪谈 / 收容机构',
    'en-US': 'SCP / Anomaly Agency',
  },
  inspiration_name_kind_skill: {
    'zh-CN': '功法 / 战技',
    'en-US': 'Cultivation Art / Martial Skill',
  },
  inspiration_name_kind_artifact: {
    'zh-CN': '神兵 / 法宝',
    'en-US': 'Artifact / Divine Relic',
  },
  inspiration_name_novel_genre: {
    'zh-CN': '小说题材',
    'en-US': 'Novel Genre',
  },
  inspiration_genre_xianxia: {
    'zh-CN': '仙侠修真',
    'en-US': 'Xianxia / Cultivation',
  },
  inspiration_genre_dushi: {
    'zh-CN': '都市神豪',
    'en-US': 'Urban / Tycoon',
  },
  inspiration_genre_kehuan: {
    'zh-CN': '科幻末日',
    'en-US': 'Sci-Fi / Apocalypse',
  },
  inspiration_genre_xuanyi: {
    'zh-CN': '悬疑怪谈',
    'en-US': 'Suspense / Mystery',
  },
  inspiration_genre_duanpian: {
    'zh-CN': '知乎反转短篇',
    'en-US': 'Twist Short Story',
  },
  inspiration_name_style_label: {
    'zh-CN': '题材风格',
    'en-US': 'Theme Style',
  },
  inspiration_style_xianxia: {
    'zh-CN': '仙侠古典',
    'en-US': 'Classical Xianxia',
  },
  inspiration_style_dushi: {
    'zh-CN': '都市现代',
    'en-US': 'Modern Urban',
  },
  inspiration_style_kehuan: {
    'zh-CN': '科幻末世',
    'en-US': 'Sci-Fi Apocalypse',
  },
  inspiration_style_lishi: {
    'zh-CN': '历史争霸',
    'en-US': 'Historical Hegemony',
  },
  inspiration_style_wuxia: {
    'zh-CN': '传统武侠',
    'en-US': 'Traditional Wuxia',
  },
  inspiration_name_gender_label: {
    'zh-CN': '角色性别',
    'en-US': 'Gender',
  },
  inspiration_gender_all: {
    'zh-CN': '通用 / 随机',
    'en-US': 'Unisex / Random',
  },
  inspiration_gender_male: {
    'zh-CN': '男性',
    'en-US': 'Male',
  },
  inspiration_gender_female: {
    'zh-CN': '女性',
    'en-US': 'Female',
  },
  inspiration_gender_neutral: {
    'zh-CN': '中性 / 出尘',
    'en-US': 'Neutral / Ethereal',
  },
  inspiration_name_count_label: {
    'zh-CN': '生成数量',
    'en-US': 'Count',
  },
  inspiration_count_items: {
    'zh-CN': '个',
    'en-US': 'items',
  },
  inspiration_name_btn_generate: {
    'zh-CN': '换一批 (离线随机)',
    'en-US': 'Reroll (Offline Random)',
  },
  inspiration_name_empty: {
    'zh-CN': '暂无生成结果，请点击「换一批」生成。',
    'en-US': 'No generation results yet. Click "Reroll" to generate.',
  },
  inspiration_chip_tooltip: {
    'zh-CN': '点击复制到剪贴板',
    'en-US': 'Click to copy to clipboard',
  },
  inspiration_copied_prefix: {
    'zh-CN': '已复制: ',
    'en-US': 'Copied: ',
  },

  // 2. 开篇钩子库
  inspiration_hook_desc: {
    'zh-CN': '黄金三章节奏拍点公式库：精选 10 款经实战检验的起步钩子，点击卡片右上角可直接复制前三章节奏模板。',
    'en-US': 'First-Three-Chapters Pacing Formula: 10 battle-tested opening hooks. Click the card button to copy the 3-chapter beat outline.',
  },
  inspiration_hook_first_300: {
    'zh-CN': '前 300 字切入：',
    'en-US': 'First 300 words hook: ',
  },
  inspiration_hook_ch1: {
    'zh-CN': '第 1 章钩子：',
    'en-US': 'Chapter 1 Hook: ',
  },
  inspiration_hook_ch2: {
    'zh-CN': '第 2 章反转：',
    'en-US': 'Chapter 2 Twist: ',
  },
  inspiration_hook_ch3: {
    'zh-CN': '第 3 章高潮：',
    'en-US': 'Chapter 3 Climax: ',
  },
  inspiration_hook_btn_copy: {
    'zh-CN': '复制本套三章细纲',
    'en-US': 'Copy 3-Chapter Beat Outline',
  },

  // 3. 金手指机制库
  inspiration_gf_desc: {
    'zh-CN': '12 大经典外挂设定库：包含触发机制、成长曲线、使用限制与防战力崩坏铁律，帮助设定有代偿、有深度、不廉价的核心金手指。',
    'en-US': '12 Classic Cheat Mechanics: trigger mechanisms, progression curves, limitations, and power-creep iron rules for deep, non-trivial core setups.',
  },
  inspiration_gf_trigger: {
    'zh-CN': '触发机制：',
    'en-US': 'Trigger Mechanism: ',
  },
  inspiration_gf_curve: {
    'zh-CN': '成长曲线：',
    'en-US': 'Progression Curve: ',
  },
  inspiration_gf_cost: {
    'zh-CN': '代价与限制：',
    'en-US': 'Costs & Limits: ',
  },
  inspiration_gf_anticollapse: {
    'zh-CN': '防崩盘铁律：',
    'en-US': 'Anti-Collapse Iron Rule: ',
  },
  inspiration_gf_btn_copy: {
    'zh-CN': '复制金手指设定',
    'en-US': 'Copy Cheat Setup',
  },

  // 4. 爽点打脸设计库
  inspiration_sd_desc: {
    'zh-CN': '网文爽点与打脸逆袭闭环设计库：覆盖 12 大成熟爽点模式，包含三段式闭环（压抑-蓄势-释放）、打脸四拍（嘲讽-沉默-碾压-围观）及升级防疲劳链。',
    'en-US': 'Webnovel Catharsis & Climax Design: 12 mature catharsis tropes, 3-stage loop (Suppression-Buildup-Release), 4-beat execution, and anti-fatigue escalation chains.',
  },
  inspiration_sd_suppression: {
    'zh-CN': '【压抑前奏】',
    'en-US': '[Suppression Prelude]',
  },
  inspiration_sd_buildup: {
    'zh-CN': '【暗中蓄势】',
    'en-US': '[Hidden Buildup]',
  },
  inspiration_sd_fourbeats: {
    'zh-CN': '打脸四拍执行节拍：',
    'en-US': 'Catharsis 4-Beat Pacing:',
  },
  inspiration_sd_upgradepath: {
    'zh-CN': '升级路径：',
    'en-US': 'Escalation Path: ',
  },
  inspiration_sd_antifatigue: {
    'zh-CN': '防疲劳提示：',
    'en-US': 'Anti-Fatigue Tip: ',
  },
  inspiration_sd_btn_copy: {
    'zh-CN': '复制本套爽点模型',
    'en-US': 'Copy Trope Model',
  },

  // 5. 世界观体系库
  inspiration_wd_desc: {
    'zh-CN': '多题材世界观与力量体系设定库：包含清晰境界阶梯、三大不可违背法则铁律、货币资源兑换链及战力防崩红线。',
    'en-US': 'Multigenre Worldbuilding & Power Systems: clear progression tiers, unbreakable iron laws, currency/resource conversion, and power creep safeguards.',
  },
  inspiration_wd_ladder: {
    'zh-CN': '境界进阶阶梯：',
    'en-US': 'Progression Ladder:',
  },
  inspiration_wd_power: {
    'zh-CN': '能力：',
    'en-US': 'Power: ',
  },
  inspiration_wd_cost: {
    'zh-CN': '代价：',
    'en-US': 'Cost: ',
  },
  inspiration_wd_ironrules: {
    'zh-CN': '法则铁律：',
    'en-US': 'Iron Rules:',
  },
  inspiration_wd_currency: {
    'zh-CN': '货币与资源：',
    'en-US': 'Currencies & Resources: ',
  },
  inspiration_wd_collapsewarning: {
    'zh-CN': '防崩红线：',
    'en-US': 'Power Creep Warning Line: ',
  },
  inspiration_wd_btn_copy: {
    'zh-CN': '复制世界观设定',
    'en-US': 'Copy World Setting',
  },

  // 6. 名场面台词库
  inspiration_dlg_desc: {
    'zh-CN': '名场面金句与反AI台词设计库：精选 12 大经典高频交锋场景，提供【AI书面腔反例】与【真人网文口语台词】对照，拆解潜台词、动作节拍与语言指纹。',
    'en-US': 'Signature Dialogue & Anti-Slop Library: 12 classic confrontational scenes contrasting AI expository clichés against vivid humanized spoken dialogue, with subtext, action beats, and speech profiles.',
  },
  inspiration_dlg_ai_bad: {
    'zh-CN': '❌ AI说明文书面腔（反例）：',
    'en-US': '❌ AI Expository Cliche (Negative Example):',
  },
  inspiration_dlg_human_good: {
    'zh-CN': '✅ 顶级网文口语台词（推荐）：',
    'en-US': '✅ Vivid Spoken Dialogue (Recommended):',
  },
  inspiration_dlg_subtext: {
    'zh-CN': '【潜台词拆解】',
    'en-US': '[Subtext Breakdown]',
  },
  inspiration_dlg_actions: {
    'zh-CN': '【神态动作搭配】',
    'en-US': '[Action & Facial Beats]',
  },
  inspiration_dlg_speechtip: {
    'zh-CN': '【语言指纹建议】',
    'en-US': '[Speech Profile Tip]',
  },
  inspiration_dlg_btn_copy: {
    'zh-CN': '复制台词与动作',
    'en-US': 'Copy Dialogue & Beats',
  },

  // 7. 爆款人设矩阵
  inspiration_chr_desc: {
    'zh-CN': '爆款人设反差矩阵：提炼 12 大成熟立体的网文角色原型，以表面伪装 vs 隐藏反差构筑张力，防脸谱化、降智与人设崩塌。',
    'en-US': 'Viral Character Persona Matrix: 12 multi-dimensional character archetypes utilizing surface mask vs hidden contrast to prevent flat stereotypes and out-of-character drift.',
  },
  inspiration_chr_surface: {
    'zh-CN': '【表面标签】',
    'en-US': '[Surface Persona]',
  },
  inspiration_chr_contrast: {
    'zh-CN': '【隐藏反差】',
    'en-US': '[Hidden Contrast]',
  },
  inspiration_chr_desire: {
    'zh-CN': '【核心欲望】',
    'en-US': '[Core Motivation]',
  },
  inspiration_chr_flaw: {
    'zh-CN': '【致命弱点】',
    'en-US': '[Fatal Flaw]',
  },
  inspiration_chr_anticollapse: {
    'zh-CN': '【防崩铁律】',
    'en-US': '[Anti-OOC Iron Rule]',
  },
  inspiration_chr_action: {
    'zh-CN': '【高光动作】',
    'en-US': '[Signature Action / Catchphrase]',
  },
  inspiration_chr_arc: {
    'zh-CN': '【成长轨迹】',
    'en-US': '[Character Arc]',
  },
  inspiration_chr_btn_copy: {
    'zh-CN': '复制完整人设卡',
    'en-US': 'Copy Full Persona Card',
  },
  inspiration_chr_copied_card: {
    'zh-CN': '已复制人设卡: ',
    'en-US': 'Copied Persona Card: ',
  },

  // 8. 情绪高潮演出
  inspiration_emt_desc: {
    'zh-CN': '情绪高潮演出与五感通感库：专治网文 AI 味直白喊情绪（他很愤怒/我好难过），以微表情、心跳冷汗、环境共鸣将情绪演出来。',
    'en-US': 'Emotional Climax & Sensory Show-Don\'t-Tell: cures AI-style blunt emotion telling through micro-expressions, visceral physiological reactions, and atmospheric resonance.',
  },
  inspiration_emt_ai_bad: {
    'zh-CN': '❌ AI直白喊情绪（反例）：',
    'en-US': '❌ AI Blunt Telling (Negative Example):',
  },
  inspiration_emt_human_good: {
    'zh-CN': '✅ 顶级网文高潮演出正文（示范）：',
    'en-US': '✅ Evocative Scene Show-Don\'t-Tell (Recommended):',
  },
  inspiration_emt_vision: {
    'zh-CN': '【视觉微表情】',
    'en-US': '[Visual & Micro-Expressions]',
  },
  inspiration_emt_physio: {
    'zh-CN': '【生理本能反应】',
    'en-US': '[Physiological Reactions]',
  },
  inspiration_emt_touch: {
    'zh-CN': '【触觉与温感】',
    'en-US': '[Touch & Temperature]',
  },
  inspiration_emt_sound: {
    'zh-CN': '【听觉与空白】',
    'en-US': '[Sound & Silence]',
  },
  inspiration_emt_env: {
    'zh-CN': '【环境通感渲染】',
    'en-US': '[Atmospheric Resonance]',
  },
  inspiration_emt_rhythm: {
    'zh-CN': '【节拍秘籍】',
    'en-US': '[Pacing & Rhythm Secret]',
  },
  inspiration_emt_btn_copy: {
    'zh-CN': '复制范例与五感细节',
    'en-US': 'Copy Sample & Sensory Details',
  },
  inspiration_emt_copied_scene: {
    'zh-CN': '已复制情绪范例: ',
    'en-US': 'Copied Emotion Sample: ',
  },

  // 小说精华数据库 (EssenceWorkbench) - 五大顶层标签页
  essence_tab_macro: {
    'zh-CN': '离线精读与解构提炼',
    'en-US': 'Offline Deep Read & Extraction',
  },
  essence_tab_assets: {
    'zh-CN': '五维精华资产库',
    'en-US': '5D Essence Asset Matrix',
  },
  essence_tab_chains: {
    'zh-CN': '伏笔暗线图谱',
    'en-US': 'Foreshadowing & Plot Chains',
  },
  essence_tab_books: {
    'zh-CN': '已精读书籍档案',
    'en-US': 'Archived Masterpiece Books',
  },
  essence_tab_constitution: {
    'zh-CN': '宪法正典审查',
    'en-US': 'Canon Guard & Constitution',
  },

  // 五维分类
  essence_cat_all: {
    'zh-CN': '全部五维分类',
    'en-US': 'All 5D Categories',
  },
  essence_cat_outline: {
    'zh-CN': '骨架大纲',
    'en-US': 'Structural Outline',
  },
  essence_cat_hook: {
    'zh-CN': '开篇钩子',
    'en-US': 'Opening Hook',
  },
  essence_cat_character: {
    'zh-CN': '人设反差',
    'en-US': 'Character Persona',
  },
  essence_cat_trope: {
    'zh-CN': '爆款桥段',
    'en-US': 'Viral Trope',
  },
  essence_cat_style: {
    'zh-CN': '反AI口语',
    'en-US': 'Anti-Slop Dialogue',
  },

  // 1. 离线精读与宏观解构提炼
  essence_macro_desc: {
    'zh-CN': '100% 纯本地离线精读引擎：对长篇正文进行章节切片、黄金三章钩子探测、对白与叙述比例核算、高频反 AI 口语词频统计，提炼出可直接反哺创作的五维结构化资产。',
    'en-US': '100% pure local offline deep reading engine: parses chapters, detects opening hooks, calculates dialogue ratios, and identifies anti-slop patterns to distill 5D reusable assets.',
  },
  essence_macro_title_label: {
    'zh-CN': '精图书籍/样本名称',
    'en-US': 'Sample Book Name',
  },
  essence_macro_title_placeholder: {
    'zh-CN': '例如：《宿命之环》《我在精神病院学斩神》',
    'en-US': 'e.g. Mistborn, Cradle, Lord of the Mysteries',
  },
  essence_macro_platform_label: {
    'zh-CN': '目标平台生态',
    'en-US': 'Target Platform Ecosystem',
  },
  essence_macro_genre_label: {
    'zh-CN': '所属题材类别',
    'en-US': 'Genre Category',
  },
  essence_macro_text_label: {
    'zh-CN': '输入精读正文（支持多章连粘，自动识别章节序号）',
    'en-US': 'Input Draft/Sample Text (multiple chapters supported)',
  },
  essence_macro_text_placeholder: {
    'zh-CN': '粘贴小说样本文字...',
    'en-US': 'Paste novel draft or sample text...',
  },
  essence_macro_btn_start: {
    'zh-CN': '开始深度精读与宏观解构',
    'en-US': 'Start Deep Read & Extraction',
  },
  essence_macro_btn_analyzing: {
    'zh-CN': '离线深度精读分析中...',
    'en-US': 'Analyzing offline...',
  },
  essence_macro_report_chip: {
    'zh-CN': '精读提炼报告',
    'en-US': 'Extraction Report',
  },
  essence_macro_metric_chapters: {
    'zh-CN': '总解析章节',
    'en-US': 'Parsed Chapters',
  },
  essence_macro_metric_words: {
    'zh-CN': '总精读字数',
    'en-US': 'Total Word Count',
  },
  essence_macro_metric_avg_words: {
    'zh-CN': '平均章字数',
    'en-US': 'Avg Chapter Words',
  },
  essence_macro_metric_dialogue_ratio: {
    'zh-CN': '对白占比',
    'en-US': 'Dialogue Ratio',
  },
  essence_macro_metric_climax_interval: {
    'zh-CN': '高潮节奏周期',
    'en-US': 'Climax Pacing Interval',
  },
  essence_macro_metric_ai_slop: {
    'zh-CN': 'AI 味指数 (0-10)',
    'en-US': 'AI Slop Index (0-10)',
  },
  essence_macro_h3_opening: {
    'zh-CN': '黄金三章开篇解构（抓人感与钩子演进）',
    'en-US': 'First 3 Chapters Hook Deconstruction',
  },
  essence_macro_h3_speech: {
    'zh-CN': '高频真实网感口语 / 特色句式',
    'en-US': 'Vivid Humanized Dialogue Patterns',
  },
  essence_macro_h3_suggested: {
    'zh-CN': '结构化资产建议（点击一键沉淀入库）',
    'en-US': 'Suggested Structured Assets',
  },
  essence_macro_btn_save_asset: {
    'zh-CN': '沉淀入库',
    'en-US': 'Save Asset',
  },
  essence_macro_toast_done: {
    'zh-CN': '深度精读与宏观提炼完成，已建立书籍档案！',
    'en-US': 'Deep reading and macro extraction complete. Book archive created!',
  },
  essence_macro_toast_saved: {
    'zh-CN': '已成功入库资产：',
    'en-US': 'Asset saved successfully: ',
  },

  // 2. 五维精华资产库
  essence_assets_category_filter: {
    'zh-CN': '五维分类',
    'en-US': '5D Category',
  },
  essence_assets_platform_filter: {
    'zh-CN': '生态平台',
    'en-US': 'Platform Ecosystem',
  },
  essence_assets_all_platforms: {
    'zh-CN': '全平台生态',
    'en-US': 'All Platforms',
  },
  essence_assets_search_placeholder: {
    'zh-CN': '模糊检索 (标题/标签/摘要)',
    'en-US': 'Search (Title, Tags, Summary)',
  },
  essence_assets_btn_refresh: {
    'zh-CN': '刷新',
    'en-US': 'Refresh',
  },
  essence_assets_empty: {
    'zh-CN': '暂无符合条件的精读资产。可在「离线精读与解构提炼」页签粘贴正文进行智能分析萃取。',
    'en-US': 'No matching essence assets found. Extract from sample texts in the extraction tab.',
  },
  essence_assets_platform_prefix: {
    'zh-CN': '生态: ',
    'en-US': 'Platform: ',
  },
  essence_assets_genre_prefix: {
    'zh-CN': '题材: ',
    'en-US': 'Genre: ',
  },
  essence_assets_note_prefix: {
    'zh-CN': '创作者感悟: ',
    'en-US': 'Creator Note: ',
  },
  essence_assets_btn_delete: {
    'zh-CN': '删除',
    'en-US': 'Delete',
  },
  essence_assets_btn_adopt: {
    'zh-CN': '一键反哺创作',
    'en-US': 'Adopt to Project',
  },
  essence_assets_adopt_title: {
    'zh-CN': '一键反哺至写作工坊',
    'en-US': 'Adopt Asset to Writing Project',
  },
  essence_assets_adopt_target_project: {
    'zh-CN': '目标项目',
    'en-US': 'Target Project',
  },
  essence_assets_adopt_target_kind: {
    'zh-CN': '反哺转存形态',
    'en-US': 'Target Entity',
  },
  essence_assets_adopt_kind_outline: {
    'zh-CN': '转入写作大纲 (writing_outlines)',
    'en-US': 'Inject as Outline (writing_outlines)',
  },
  essence_assets_adopt_kind_character: {
    'zh-CN': '转入人物卡片 (writing_characters)',
    'en-US': 'Inject as Character (writing_characters)',
  },
  essence_assets_adopt_kind_note: {
    'zh-CN': '转入灵感便签 (writing_notes)',
    'en-US': 'Inject as Inspiration Note (writing_notes)',
  },
  essence_assets_adopt_btn_cancel: {
    'zh-CN': '取消',
    'en-US': 'Cancel',
  },
  essence_assets_adopt_btn_confirm: {
    'zh-CN': '确认反哺',
    'en-US': 'Confirm Adoption',
  },

  // 3. 已精读书籍档案
  essence_books_desc: {
    'zh-CN': '本地精读档案库：沉淀每部精读长篇的字数、对白率、节奏模型，支持全生命周期管理与结构化提纲导出。',
    'en-US': 'Local Masterpiece Archive: records word count, dialogue ratios, and rhythm models, supporting lifecycle management and outline export.',
  },
  essence_books_btn_refresh: {
    'zh-CN': '刷新档案',
    'en-US': 'Refresh Archives',
  },
  essence_books_empty: {
    'zh-CN': '暂无已精读的书籍档案。请先在「离线精读与解构提炼」页签输入样本进行解析。',
    'en-US': 'No archived books found. Extract sample text first.',
  },
  essence_books_dialogue_ratio: {
    'zh-CN': '对白占比: ',
    'en-US': 'Dialogue Ratio: ',
  },
  essence_books_climax_interval: {
    'zh-CN': '高潮间隔: ',
    'en-US': 'Climax Interval: ',
  },
  essence_books_ai_slop: {
    'zh-CN': 'AI 味道评分: ',
    'en-US': 'AI Slop Score: ',
  },
  essence_books_btn_export_outline: {
    'zh-CN': '导出大纲',
    'en-US': 'Export Outline',
  },
  essence_books_btn_export_beats: {
    'zh-CN': '导出节拍',
    'en-US': 'Export Beats',
  },
  essence_books_btn_adopt_book: {
    'zh-CN': '整本反哺',
    'en-US': 'Adopt Entire Book',
  },
  essence_books_adopt_title: {
    'zh-CN': '一键整本反哺到写作工坊',
    'en-US': 'Adopt Full Book Assets to Writing Project',
  },
  essence_books_adopt_target: {
    'zh-CN': '目标创作项目',
    'en-US': 'Target Writing Project',
  },
  essence_books_adopt_btn_confirm: {
    'zh-CN': '确认注入',
    'en-US': 'Confirm Injection',
  },
  essence_books_adopt_btn_adopting: {
    'zh-CN': '正在注入...',
    'en-US': 'Injecting...',
  },

  // 4. 伏笔暗线图谱
  essence_chains_filter_book: {
    'zh-CN': '筛选书籍档案',
    'en-US': 'Filter by Book',
  },
  essence_chains_all_books: {
    'zh-CN': '全部书籍暗线',
    'en-US': 'All Book Plot Chains',
  },
  essence_chains_btn_refresh: {
    'zh-CN': '刷新',
    'en-US': 'Refresh',
  },
  essence_chains_btn_create: {
    'zh-CN': '录入伏笔暗线',
    'en-US': 'New Plot Chain',
  },
  essence_chains_empty: {
    'zh-CN': '暂无伏笔暗线数据。点击右上角「录入伏笔暗线」，建立长篇小说的草蛇灰线与回收图谱。',
    'en-US': 'No plot chains found. Click "New Plot Chain" to record foreshadowing loops.',
  },
  essence_chains_plant_ch: {
    'zh-CN': '🌱 埋设：',
    'en-US': '🌱 Plant: ',
  },
  essence_chains_reveal_ch: {
    'zh-CN': '🔍 揭晓：',
    'en-US': '🔍 Reveal: ',
  },
  essence_chains_climax_ch: {
    'zh-CN': '💥 高潮回收：',
    'en-US': '💥 Climax Payoff: ',
  },
  essence_chains_dialog_title: {
    'zh-CN': '录入伏笔暗线与收敛图谱',
    'en-US': 'Record Plot Chain & Foreshadowing Loop',
  },
  essence_chains_form_book: {
    'zh-CN': '所属书籍',
    'en-US': 'Book',
  },
  essence_chains_form_title: {
    'zh-CN': '伏笔暗线名称',
    'en-US': 'Chain Title',
  },
  essence_chains_form_category: {
    'zh-CN': '伏笔类型',
    'en-US': 'Category',
  },
  essence_chains_form_plant: {
    'zh-CN': '埋下章节 (Plant)',
    'en-US': 'Plant Chapter',
  },
  essence_chains_form_reveal: {
    'zh-CN': '显露章节 (Reveal)',
    'en-US': 'Reveal Chapter',
  },
  essence_chains_form_climax: {
    'zh-CN': '高潮章节 (Climax)',
    'en-US': 'Climax Chapter',
  },
  essence_chains_form_status: {
    'zh-CN': '当前状态',
    'en-US': 'Current Status',
  },
  essence_chains_form_desc: {
    'zh-CN': '暗线铺设逻辑与爽点释放机制',
    'en-US': 'Foreshadowing & Payoff Mechanism',
  },
  essence_chains_status_planted: {
    'zh-CN': '🌱 已埋下',
    'en-US': '🌱 Planted',
  },
  essence_chains_status_developing: {
    'zh-CN': '⏳ 推进发酵',
    'en-US': '⏳ Developing',
  },
  essence_chains_status_revealed: {
    'zh-CN': '🔍 已显露',
    'en-US': '🔍 Revealed',
  },
  essence_chains_status_recycled: {
    'zh-CN': '✅ 闭环回收',
    'en-US': '✅ Recycled / Paid Off',
  },

  // 5. 小说宪法正典审查
  essence_const_title: {
    'zh-CN': '小说宪法正典审查 (Canon Guard)',
    'en-US': 'Novel Constitution & Canon Guard',
  },
  essence_const_desc: {
    'zh-CN': '审查世界观底线（严禁修仙/灵气/系统等超自然穿帮、严禁时代脱节科技词、严禁恶俗网文毒点台词），并可校验角色声线禁语（该角色绝不应说的话）。',
    'en-US': 'Audits core canon boundaries (anti-anachronism, supernatural slips, immersion-breaking tropes) and character voice taboo constraints.',
  },
  essence_const_text_label: {
    'zh-CN': '待审查小说正文或章节文本',
    'en-US': 'Draft Text or Chapter to Audit',
  },
  essence_const_text_placeholder: {
    'zh-CN': '粘贴待审查的段落或完整章节内容...',
    'en-US': 'Paste chapter draft or passage to audit...',
  },
  essence_const_voice_label: {
    'zh-CN': '自定义角色声线禁语 (可选，每行一条: 角色名: 禁语1, 禁语2)',
    'en-US': 'Custom Character Voice Taboos (Optional, e.g. Name: taboo1, taboo2)',
  },
  essence_const_voice_helper: {
    'zh-CN': '配置特定角色绝不会说的词汇或口癖，防止人设塌房与语调失真',
    'en-US': 'Defines words that specific characters would never say to prevent OOC voice drift',
  },
  essence_const_btn_check: {
    'zh-CN': '开始宪法正典审查',
    'en-US': 'Run Canon Guard Check',
  },
  essence_const_btn_checking: {
    'zh-CN': '审查中...',
    'en-US': 'Auditing...',
  },
  essence_const_chip_compliant: {
    'zh-CN': '✅ 宪法正典合规',
    'en-US': '✅ Canon Compliant',
  },
  essence_const_chip_violation: {
    'zh-CN': '⚠️ 存在违宪/破格隐患',
    'en-US': '⚠️ Canon Violations Detected',
  },
  essence_const_score_label: {
    'zh-CN': '合规得分: ',
    'en-US': 'Compliance Score: ',
  },
  essence_const_violations_h: {
    'zh-CN': '世界观与底线偏离列表',
    'en-US': 'Canon & Worldbuilding Violations',
  },
  essence_const_no_violations: {
    'zh-CN': '🎉 未发现任何超自然穿帮、时代脱节或毒点台词！',
    'en-US': '🎉 No canon violations or anachronisms found!',
  },
  essence_const_voice_h: {
    'zh-CN': '角色声线禁语冲突',
    'en-US': 'Character Voice Taboo Alerts',
  },
  essence_const_no_voice_alerts: {
    'zh-CN': '✨ 未检测到任何角色人设禁语冲突。',
    'en-US': '✨ No character voice violations detected.',
  },

  // =========================================================================
  // QualityWorkbench 质检工作台双语国际化词典 (Milestone 21)
  // =========================================================================
  // 顶层标签页
  quality_tab_check: {
    'zh-CN': '单章检查',
    'en-US': 'Chapter Check',
  },
  quality_tab_book: {
    'zh-CN': '全书质检',
    'en-US': 'Full Book Inspection',
  },
  quality_tab_qc: {
    'zh-CN': 'QC 综合',
    'en-US': 'Comprehensive QC',
  },
  quality_tab_poison: {
    'zh-CN': '毒点避雷',
    'en-US': 'Poison & Trope Defense',
  },

  // 判定与状态枚举
  quality_verdict_pass: {
    'zh-CN': '通过',
    'en-US': 'PASS',
  },
  quality_verdict_warn: {
    'zh-CN': '警告',
    'en-US': 'WARN',
  },
  quality_verdict_fail: {
    'zh-CN': '不通过',
    'en-US': 'FAIL',
  },
  quality_status_pending: {
    'zh-CN': '等待中',
    'en-US': 'Pending',
  },
  quality_status_running: {
    'zh-CN': '运行中',
    'en-US': 'Running',
  },
  quality_status_done: {
    'zh-CN': '已完成',
    'en-US': 'Completed',
  },
  quality_status_error: {
    'zh-CN': '失败',
    'en-US': 'Failed',
  },

  // 桌面端路径选择
  quality_btn_pick_dir: {
    'zh-CN': '选择目录…',
    'en-US': 'Select Directory…',
  },
  quality_btn_pick_file: {
    'zh-CN': '选择文件…',
    'en-US': 'Select File…',
  },

  // 1. 单章检查
  quality_check_title: {
    'zh-CN': '单章检查',
    'en-US': 'Single Chapter Quality Check',
  },
  quality_check_target_label: {
    'zh-CN': '章节路径（或粘贴文本）',
    'en-US': 'Chapter Path (or Paste Draft)',
  },
  quality_check_voice_label: {
    'zh-CN': 'voice-card（可选）',
    'en-US': 'Voice Card (Optional)',
  },
  quality_check_genre_label: {
    'zh-CN': 'genre-pack（可选）',
    'en-US': 'Genre Pack (Optional)',
  },
  quality_check_option_none: {
    'zh-CN': '无',
    'en-US': 'None',
  },
  quality_check_btn_start: {
    'zh-CN': '检查',
    'en-US': 'Check',
  },
  quality_check_btn_checking: {
    'zh-CN': '检查中...',
    'en-US': 'Checking...',
  },
  quality_check_text_label: {
    'zh-CN': '或粘贴章节正文',
    'en-US': 'Or Paste Chapter Text',
  },
  quality_check_score_quality: {
    'zh-CN': '章节质量：',
    'en-US': 'Chapter Quality: ',
  },
  quality_check_score_consistency: {
    'zh-CN': '一致性：',
    'en-US': 'Consistency: ',
  },
  quality_check_load_asset_failed: {
    'zh-CN': '加载资产失败: ',
    'en-US': 'Failed to load assets: ',
  },

  // 2. 全书质检
  quality_book_title: {
    'zh-CN': '全书质检',
    'en-US': 'Full Book Quality Inspection',
  },
  quality_book_target_label: {
    'zh-CN': '章节目录路径',
    'en-US': 'Chapters Directory Path',
  },
  quality_book_btn_start: {
    'zh-CN': '质检',
    'en-US': 'Inspect',
  },
  quality_book_btn_inspecting: {
    'zh-CN': '质检中...',
    'en-US': 'Inspecting...',
  },
  quality_book_verdict_label: {
    'zh-CN': '判定：',
    'en-US': 'Verdict: ',
  },
  quality_book_collapse: {
    'zh-CN': '收起',
    'en-US': 'Collapse',
  },

  // 3. QC 综合
  quality_qc_title: {
    'zh-CN': 'QC 综合质检（四层十二维）',
    'en-US': 'Comprehensive QC (4-Layer 12-Dimensional)',
  },
  quality_qc_target_label: {
    'zh-CN': '章节目录路径',
    'en-US': 'Chapters Directory Path',
  },
  quality_qc_btn_start: {
    'zh-CN': '开始 QC',
    'en-US': 'Start QC',
  },
  quality_qc_btn_running: {
    'zh-CN': 'QC 运行中...',
    'en-US': 'QC Running...',
  },
  quality_qc_status_label: {
    'zh-CN': '状态：',
    'en-US': 'Status: ',
  },
  quality_qc_verdict_label: {
    'zh-CN': '判定：',
    'en-US': 'Verdict: ',
  },
  quality_qc_score_label: {
    'zh-CN': '总分 ',
    'en-US': 'Total Score: ',
  },
  quality_qc_layer_suffix: {
    'zh-CN': ' 维',
    'en-US': ' Dim',
  },
  quality_qc_score_suffix: {
    'zh-CN': '分',
    'en-US': ' pts',
  },
  quality_qc_report_saved: {
    'zh-CN': '报告已落盘：',
    'en-US': 'Report saved to disk: ',
  },
  quality_qc_history_title: {
    'zh-CN': '历史报告',
    'en-US': 'Historical QC Reports',
  },

  // =========================================================================
  // AssetLibrary 资产库与资产全品类矩阵浏览双语国际化词典 (Milestone 22)
  // =========================================================================
  asset_lib_title: {
    'zh-CN': '资产库',
    'en-US': 'Asset Library & Matrix',
  },
  asset_lib_filter_all: {
    'zh-CN': '全部',
    'en-US': 'All',
  },
  asset_lib_load_failed: {
    'zh-CN': '加载失败：',
    'en-US': 'Failed to load assets: ',
  },
  asset_lib_empty: {
    'zh-CN': '暂无资产',
    'en-US': 'No assets found',
  },
  asset_lib_select_hint: {
    'zh-CN': '从左侧选择一个资产查看详情',
    'en-US': 'Select an asset from the list to view details',
  },
  asset_lib_raw_data: {
    'zh-CN': '高级 · 查看原始数据',
    'en-US': 'Advanced · View Raw Data',
  },

  // 11 大核心资产类型标签
  asset_kind_voice: {
    'zh-CN': '声线卡',
    'en-US': 'Voice Card',
  },
  asset_kind_structure: {
    'zh-CN': '结构观测',
    'en-US': 'Structure Observation',
  },
  asset_kind_commercial: {
    'zh-CN': '商业观测',
    'en-US': 'Commercial Observation',
  },
  asset_kind_craft: {
    'zh-CN': '笔法卡',
    'en-US': 'Craft Card',
  },
  asset_kind_genre_pack: {
    'zh-CN': '题材包',
    'en-US': 'Genre Pack',
  },
  asset_kind_prose_card: {
    'zh-CN': '文风卡',
    'en-US': 'Prose Card',
  },
  asset_kind_distilled: {
    'zh-CN': '蒸馏规则',
    'en-US': 'Distilled Rule',
  },
  asset_kind_prose_card_index: {
    'zh-CN': '题材文风卡索引',
    'en-US': 'Genre Prose Index',
  },
  asset_kind_trope: {
    'zh-CN': '桥段',
    'en-US': 'Trope',
  },
  asset_kind_report: {
    'zh-CN': '报告',
    'en-US': 'Report',
  },
  asset_kind_book: {
    'zh-CN': '语料',
    'en-US': 'Corpus Book',
  },

  // =========================================================================
  // HomeDashboard 首页仪表盘与系统全景矩阵双语国际化词典 (Milestone 23)
  // =========================================================================
  home_empty_title: {
    'zh-CN': '还没有任何书籍数据',
    'en-US': 'No book data yet',
  },
  home_empty_hint: {
    'zh-CN': '从「分析」页导入一本 TXT 开始拆书',
    'en-US': 'Import a TXT file from Deconstruct to begin analysis',
  },
  home_empty_cta: {
    'zh-CN': '去分析拆书',
    'en-US': 'Go to Deconstruct',
  },
  home_brand_title: {
    'zh-CN': '暮冬念春工作台',
    'en-US': 'Exoscribe Studio',
  },
  home_brand_subtitle: {
    'zh-CN': '中文书籍创作辅助系统',
    'en-US': 'Bilingual Narrative Exoskeleton & Writing Engine',
  },
  home_help_tooltip: {
    'zh-CN': '新手上路：从这里开始',
    'en-US': 'Quick Start Guide: Start Here',
  },
  home_help_aria: {
    'zh-CN': '新手上路',
    'en-US': 'Quick Start',
  },
  home_model_configured: {
    'zh-CN': '模型已配置',
    'en-US': 'Model Configured',
  },
  home_model_not_configured: {
    'zh-CN': '模型未配置',
    'en-US': 'Model Unconfigured',
  },
  home_model_alert: {
    'zh-CN': '尚未配置外部模型，请先运行 model_config.py 配置。',
    'en-US': 'External model not configured yet. Please run model_config.py to configure.',
  },

  // KPI 指标卡
  home_kpi_books: {
    'zh-CN': '已拆书',
    'en-US': 'Deconstructed Books',
  },
  home_kpi_genre_packs: {
    'zh-CN': '题材包',
    'en-US': 'Genre Packs',
  },
  home_kpi_reports: {
    'zh-CN': '报告',
    'en-US': 'Analysis Reports',
  },
  home_kpi_assets: {
    'zh-CN': '资产总数',
    'en-US': 'Total Assets',
  },

  // 资产分布
  home_asset_dist_title: {
    'zh-CN': '资产类型分布',
    'en-US': 'Asset Distribution',
  },
  home_asset_dist_empty: {
    'zh-CN': '暂无资产数据',
    'en-US': 'No asset data yet',
  },
  home_asset_dist_empty_sub: {
    'zh-CN': '拆书分析后自动生成',
    'en-US': 'Generated automatically after analysis',
  },

  // 快速操作
  home_quick_start_title: {
    'zh-CN': '开始创作',
    'en-US': 'Start Writing',
  },
  home_quick_action_analysis_title: {
    'zh-CN': '分析拆书',
    'en-US': 'Deconstruct',
  },
  home_quick_action_analysis_desc: {
    'zh-CN': '导入 TXT，全链路拆解',
    'en-US': 'Import TXT & full-pipeline deconstruction',
  },
  home_quick_action_assets_title: {
    'zh-CN': '资产库',
    'en-US': 'Asset Matrix',
  },
  home_quick_action_assets_desc: {
    'zh-CN': '浏览题材包与笔法卡',
    'en-US': 'Browse genre packs & craft cards',
  },
  home_quick_action_writing_title: {
    'zh-CN': '沉浸创作室',
    'en-US': 'Immersion Studio',
  },
  home_quick_action_writing_desc: {
    'zh-CN': '一屏三栏·副驾伴写',
    'en-US': '3-Column Workspace · AI Copilot',
  },
  home_quick_action_enter: {
    'zh-CN': '进入',
    'en-US': 'Enter',
  },
  home_recent_activity_title: {
    'zh-CN': '最近动态',
    'en-US': 'Recent Activity',
  },

  // 拆书分析工坊 (Analysis View / Story Deconstruction)
  analysis_tab_import: {
    'zh-CN': '导入',
    'en-US': 'Import',
  },
  context_help_default: {
    'zh-CN': '查看此功能的使用指南',
    'en-US': 'View guide for this feature',
  },
  analysis_tab_progress: {
    'zh-CN': '进度',
    'en-US': 'Progress',
  },
  analysis_tab_result: {
    'zh-CN': '结果',
    'en-US': 'Results',
  },
  analysis_help_title: {
    'zh-CN': '查看拆书指南',
    'en-US': 'View Deconstruction Guide',
  },
  analysis_status_idle: {
    'zh-CN': '空闲',
    'en-US': 'Idle',
  },
  analysis_status_running: {
    'zh-CN': '运行中',
    'en-US': 'Running',
  },
  analysis_status_paused: {
    'zh-CN': '已暂停',
    'en-US': 'Paused',
  },
  analysis_status_done: {
    'zh-CN': '已完成',
    'en-US': 'Completed',
  },
  analysis_status_error: {
    'zh-CN': '出错',
    'en-US': 'Error',
  },
  analysis_batches_unit: {
    'zh-CN': '批',
    'en-US': 'batches',
  },
  analysis_need_book: {
    'zh-CN': '请先导入书籍',
    'en-US': 'Please import a book first',
  },
  analysis_genre_label: {
    'zh-CN': '题材 *',
    'en-US': 'Genre *',
  },
  analysis_err_load_genres: {
    'zh-CN': '题材列表加载失败，请刷新重试',
    'en-US': 'Failed to load genres, please refresh',
  },
  analysis_err_select_genre: {
    'zh-CN': '请选择题材',
    'en-US': 'Please select a genre',
  },
  analysis_btn_running: {
    'zh-CN': '分析中…',
    'en-US': 'Analyzing...',
  },
  analysis_btn_start: {
    'zh-CN': '一键分析',
    'en-US': 'One-Click Analysis',
  },
  analysis_card_empty: {
    'zh-CN': '暂无数据',
    'en-US': 'No data available',
  },
  analysis_report_load_error: {
    'zh-CN': '报告加载失败',
    'en-US': 'Failed to load report',
  },
  analysis_res_tab_overview: {
    'zh-CN': '资产卡',
    'en-US': 'Asset Cards',
  },
  analysis_res_tab_scores: {
    'zh-CN': '章节打分',
    'en-US': 'Chapter Scores',
  },
  analysis_res_tab_reports: {
    'zh-CN': '报告',
    'en-US': 'Reports',
  },
  analysis_card_voice: {
    'zh-CN': '声线卡',
    'en-US': 'Voice Card',
  },
  analysis_card_structure: {
    'zh-CN': '结构观测',
    'en-US': 'Structure Observation',
  },
  analysis_card_commercial: {
    'zh-CN': '商业观测',
    'en-US': 'Commercial Observation',
  },
  analysis_card_craft: {
    'zh-CN': '笔法卡',
    'en-US': 'Craft Card',
  },
  analysis_chart_consistency: {
    'zh-CN': '一致性',
    'en-US': 'Consistency',
  },
  analysis_chart_quality: {
    'zh-CN': '质量',
    'en-US': 'Quality',
  },
  analysis_chart_avg: {
    'zh-CN': '综合均分',
    'en-US': 'Overall Average',
  },
  analysis_score_bar_title: {
    'zh-CN': '章节打分对比',
    'en-US': 'Chapter Score Comparison',
  },
  analysis_score_radar_title: {
    'zh-CN': '综合能力雷达',
    'en-US': 'Comprehensive Ability Radar',
  },
  analysis_score_empty: {
    'zh-CN': '暂无章节打分数据',
    'en-US': 'No chapter score data',
  },
  analysis_no_book_hint: {
    'zh-CN': '请先在首页/控制栏导入并拆书，完成后在此查看结果',
    'en-US': 'Please import and analyze a book first to view results here',
  },
  analysis_load_failed: {
    'zh-CN': '加载失败',
    'en-US': 'Failed to load',
  },
  analysis_retry: {
    'zh-CN': '重试',
    'en-US': 'Retry',
  },
  analysis_current_book: {
    'zh-CN': '当前书籍',
    'en-US': 'Current Book',
  },
  analysis_not_generated: {
    'zh-CN': '尚未生成拆书结果，请先运行「一键分析」',
    'en-US': 'No analysis results generated yet. Please run "One-Click Analysis" first',
  },
  analysis_result_chip: {
    'zh-CN': '拆书结果',
    'en-US': 'Analysis Result',
  },
  analysis_reports_empty: {
    'zh-CN': '暂无报告',
    'en-US': 'No reports available',
  },
  analysis_report_item: {
    'zh-CN': '报告',
    'en-US': 'Report',
  },
  analysis_import_only_txt: {
    'zh-CN': '仅支持 .txt 文件导入',
    'en-US': 'Only .txt files are supported',
  },
  analysis_import_title: {
    'zh-CN': '导入 .txt 书籍',
    'en-US': 'Import .txt Book',
  },
  analysis_import_drag_hint: {
    'zh-CN': '拖拽到此处，或点击选择文件',
    'en-US': 'Drag & drop here, or click to choose file',
  },
  analysis_import_btn_pick: {
    'zh-CN': '选择文件',
    'en-US': 'Choose File',
  },
  analysis_import_success_prefix: {
    'zh-CN': '已导入《',
    'en-US': 'Imported "',
  },
  analysis_import_success_middle: {
    'zh-CN': '》 · ',
    'en-US': '" · ',
  },
  analysis_import_success_suffix: {
    'zh-CN': ' 章',
    'en-US': ' chapters',
  },
  analysis_sample_title: {
    'zh-CN': '内置示例语料',
    'en-US': 'Built-in Sample Corpus',
  },
  analysis_sample_subtitle: {
    'zh-CN': '（新手试手，一键导入）',
    'en-US': '(Beginner trial, one-click import)',
  },
  analysis_sample_help_title: {
    'zh-CN': '查看导入与拆书指南',
    'en-US': 'View Import & Deconstruction Guide',
  },
  analysis_prog_title: {
    'zh-CN': '分析进度',
    'en-US': 'Analysis Progress',
  },
  analysis_prog_status_current: {
    'zh-CN': '当前状态',
    'en-US': 'Current Status',
  },
  analysis_prog_checkpoint: {
    'zh-CN': '断点',
    'en-US': 'Checkpoint',
  },
  analysis_status_pending: {
    'zh-CN': '等待',
    'en-US': 'Pending',
  },
  analysis_status_success: {
    'zh-CN': '成功',
    'en-US': 'Success',
  },
  analysis_status_failed: {
    'zh-CN': '失败',
    'en-US': 'Failed',
  },
  analysis_status_skipped: {
    'zh-CN': '跳过',
    'en-US': 'Skipped',
  },
  analysis_chap_not_imported: {
    'zh-CN': '尚未导入书籍',
    'en-US': 'No book imported yet',
  },
  analysis_chap_prefix: {
    'zh-CN': '第',
    'en-US': 'Ch.',
  },
  analysis_chap_suffix: {
    'zh-CN': '章',
    'en-US': '',
  },
  analysis_chap_status_failed: {
    'zh-CN': '失败',
    'en-US': 'Failed',
  },
  analysis_chap_status_done: {
    'zh-CN': '完成',
    'en-US': 'Done',
  },
  analysis_chap_status_partial: {
    'zh-CN': '部分',
    'en-US': 'Partial',
  },
  analysis_chap_status_pending: {
    'zh-CN': '待处理',
    'en-US': 'Pending',
  },
  analysis_detail_title: {
    'zh-CN': '分析结果',
    'en-US': 'Analysis Result',
  },
  analysis_detail_need_select: {
    'zh-CN': '请先选择章节查看分析结果',
    'en-US': 'Please select a chapter to view analysis results',
  },
  analysis_detail_batch_label: {
    'zh-CN': '批次',
    'en-US': 'Batch',
  },
  analysis_detail_refresh: {
    'zh-CN': '刷新',
    'en-US': 'Refresh',
  },
  analysis_detail_not_generated: {
    'zh-CN': '该批次尚未生成此 pass 的结果（请先运行分析）',
    'en-US': 'No pass results generated for this batch yet (please run analysis first)',
  },
  analysis_pass_structure: {
    'zh-CN': '结构拆解',
    'en-US': 'Structure Pass',
  },
  analysis_pass_character: {
    'zh-CN': '人物弧光',
    'en-US': 'Character Pass',
  },
  analysis_pass_style: {
    'zh-CN': '文风指纹',
    'en-US': 'Style Pass',
  },
  analysis_pass_commercial: {
    'zh-CN': '商业评估',
    'en-US': 'Commercial Pass',
  },
  help_title: {
    'zh-CN': '帮助中心',
    'en-US': 'Help Center',
  },
  help_subtitle: {
    'zh-CN': '术语解释、操作指南、工作流、常见问题——都在这里。',
    'en-US': 'Terminology, user guides, workflows, and FAQs — all in one place.',
  },
  help_tab_start: {
    'zh-CN': '新手上路',
    'en-US': 'Quick Start',
  },
  help_tab_glossary: {
    'zh-CN': '术语表',
    'en-US': 'Glossary',
  },
  help_tab_guides: {
    'zh-CN': '功能指南',
    'en-US': 'Feature Guides',
  },
  help_tab_faq: {
    'zh-CN': '常见问题',
    'en-US': 'FAQ',
  },
  help_start_eco_title: {
    'zh-CN': '生态全景：数据是怎么流动的',
    'en-US': 'Ecosystem Overview: How Data Flows',
  },
  help_start_eco_summary_1: {
    'zh-CN': '记住这个顺序：',
    'en-US': 'Remember the pipeline order: ',
  },
  help_start_eco_summary_highlight: {
    'zh-CN': '先拆书，再蒸馏，最后用资产辅助写作',
    'en-US': 'Analyze first, Distill next, and then power Assisted Writing with assets',
  },
  help_start_eco_summary_2: {
    'zh-CN': '。质检贯穿全程——写完一章用单章检查，完稿用全书QC。',
    'en-US': '. Quality check is continuous — inspect chapters as you write, and run full book QC on final manuscripts.',
  },
  help_start_workflows_title: {
    'zh-CN': '四个典型工作流',
    'en-US': 'Four Canonical Workflows',
  },
  help_glossary_search: {
    'zh-CN': '搜索术语…',
    'en-US': 'Search terms…',
  },
  help_cat_all: {
    'zh-CN': '全部',
    'en-US': 'All',
  },
  help_cat_concept: {
    'zh-CN': '概念',
    'en-US': 'Concepts',
  },
  help_cat_asset: {
    'zh-CN': '资产',
    'en-US': 'Assets',
  },
  help_cat_feature: {
    'zh-CN': '功能',
    'en-US': 'Features',
  },
  help_glossary_example_prefix: {
    'zh-CN': '举例：',
    'en-US': 'Example: ',
  },
  help_glossary_empty: {
    'zh-CN': '没有找到匹配的术语，换个关键词试试。',
    'en-US': 'No matching terms found. Try another search term.',
  },
  help_guides_subtitle: {
    'zh-CN': '每个功能模块的详细操作步骤。点击展开查看。',
    'en-US': 'Detailed walkthroughs for each module. Click to expand.',
  },
  help_guides_steps_header: {
    'zh-CN': '操作步骤',
    'en-US': 'Step-by-Step Instructions',
  },
  help_guides_tips_header: {
    'zh-CN': '💡 提示',
    'en-US': '💡 Tips',
  },
  help_guides_faq_header: {
    'zh-CN': '常见问题',
    'en-US': 'Frequently Asked Questions',
  },
  help_guides_q_prefix: {
    'zh-CN': 'Q：',
    'en-US': 'Q: ',
  },
  help_guides_a_prefix: {
    'zh-CN': 'A：',
    'en-US': 'A: ',
  },
  advanced_tab_distill: {
    'zh-CN': '蒸馏',
    'en-US': 'Distillation',
  },
  advanced_tab_batch: {
    'zh-CN': '批量状态',
    'en-US': 'Batch Status',
  },
  advanced_tab_edit: {
    'zh-CN': '资产编辑',
    'en-US': 'Asset Editor',
  },
  advanced_tab_platform: {
    'zh-CN': '平台适配',
    'en-US': 'Platform Adaptation',
  },
  distill_title: {
    'zh-CN': '题材蒸馏',
    'en-US': 'Genre Distillation',
  },
  distill_genre_label: {
    'zh-CN': '题材',
    'en-US': 'Genre',
  },
  distill_btn_execute: {
    'zh-CN': '执行蒸馏',
    'en-US': 'Execute Distillation',
  },
  distill_status_available: {
    'zh-CN': '可蒸馏书目：',
    'en-US': 'Available Books: ',
  },
  distill_status_books_unit: {
    'zh-CN': ' 本 — ',
    'en-US': ' books — ',
  },
  distill_status_existing: {
    'zh-CN': '已有蒸馏产物：',
    'en-US': 'Existing Distilled Assets: ',
  },
  distill_status_assets_unit: {
    'zh-CN': ' 个',
    'en-US': ' items',
  },
  distill_chip_ready: {
    'zh-CN': '可蒸馏',
    'en-US': 'Ready to Distill',
  },
  distill_chip_insufficient: {
    'zh-CN': '书目不足（需≥2本）',
    'en-US': 'Insufficient Books (>=2 required)',
  },
  distill_result_success: {
    'zh-CN': '蒸馏完成',
    'en-US': 'Distillation Complete',
  },
  distill_result_books_prefix: {
    'zh-CN': ' 本书目 · ',
    'en-US': ' books · ',
  },
  distill_result_outputs_suffix: {
    'zh-CN': ' 个产出',
    'en-US': ' outputs',
  },
  distill_section_books: {
    'zh-CN': '参与书目',
    'en-US': 'Participating Books',
  },
  distill_section_dims: {
    'zh-CN': '蒸馏维度',
    'en-US': 'Distillation Dimensions',
  },
  distill_section_files: {
    'zh-CN': '产出文件（已入库）',
    'en-US': 'Generated Files (Persisted)',
  },
  distill_btn_hide_raw: {
    'zh-CN': '收起原始 JSON',
    'en-US': 'Hide Raw JSON',
  },
  distill_btn_view_raw: {
    'zh-CN': '查看原始 JSON',
    'en-US': 'View Raw JSON',
  },
  batch_status_title: {
    'zh-CN': '批量拆书状态',
    'en-US': 'Batch Deconstruction Status',
  },
  batch_status_empty: {
    'zh-CN': '暂无拆书数据',
    'en-US': 'No deconstruction data yet',
  },
  batch_chip_has_assets: {
    'zh-CN': '已有资产',
    'en-US': 'Assets Present',
  },
  asset_edit_title: {
    'zh-CN': '资产编辑',
    'en-US': 'Asset Editor',
  },
  asset_edit_select_label: {
    'zh-CN': '选择资产',
    'en-US': 'Select Asset',
  },
  asset_edit_btn_load: {
    'zh-CN': '加载',
    'en-US': 'Load',
  },
  asset_edit_btn_save: {
    'zh-CN': '保存',
    'en-US': 'Save',
  },
  asset_edit_readonly_hint: {
    'zh-CN': '题材文风卡索引（prose_card_index）为只读寻址表，不在可编辑列表中，请在「资产库」中查看。',
    'en-US': 'Genre style card index (prose_card_index) is a read-only index table and not editable; view in Asset Library.',
  },
  asset_edit_chip_json_valid: {
    'zh-CN': '✓ JSON 合法',
    'en-US': '✓ Valid JSON',
  },
  asset_edit_chip_json_invalid: {
    'zh-CN': '✗ JSON 错误',
    'en-US': '✗ JSON Error',
  },
  asset_edit_chip_unsaved: {
    'zh-CN': '未保存修改',
    'en-US': 'Unsaved Changes',
  },
  asset_edit_json_empty: {
    'zh-CN': '内容为空',
    'en-US': 'Content is empty',
  },
  asset_edit_json_top_object: {
    'zh-CN': '顶层必须是 JSON 对象',
    'en-US': 'Top level must be a JSON object',
  },
  asset_edit_json_error_prefix: {
    'zh-CN': 'JSON 错误：',
    'en-US': 'JSON Error: ',
  },
  asset_edit_json_valid: {
    'zh-CN': 'JSON 合法',
    'en-US': 'Valid JSON',
  },
  asset_edit_save_success: {
    'zh-CN': '保存成功',
    'en-US': 'Saved successfully',
  },
  asset_edit_content_label: {
    'zh-CN': '资产 JSON 内容',
    'en-US': 'Asset JSON Content',
  },
}



