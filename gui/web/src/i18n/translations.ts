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
}

