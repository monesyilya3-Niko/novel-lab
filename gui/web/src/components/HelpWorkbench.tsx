// 应用内帮助中心：术语表 / 新手上路 / 功能指南 / 常见问题。
// 取代独立手册文档，所有帮助内容完整融入应用。
import React, { useState, useMemo } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import TextField from '@mui/material/TextField'
import InputAdornment from '@mui/material/InputAdornment'
import SearchIcon from '@mui/icons-material/Search'
import Chip from '@mui/material/Chip'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Stepper from '@mui/material/Stepper'
import Step from '@mui/material/Step'
import StepLabel from '@mui/material/StepLabel'
import StepContent from '@mui/material/StepContent'
import Paper from '@mui/material/Paper'
import Divider from '@mui/material/Divider'
import { ink, fontStack } from '../ink'

export type HelpSection = 'start' | 'glossary' | 'guides' | 'faq'
export type HelpAnchor = string | null

interface HelpWorkbenchProps {
  initialTab?: HelpSection
  initialAnchor?: HelpAnchor
}

// ---------------------------------------------------------------------------
// 数据：术语表
// ---------------------------------------------------------------------------

interface GlossaryTerm {
  term: string
  pinyin?: string
  category: '资产' | '功能' | '概念'
  definition: string
  example?: string
}

const GLOSSARY: GlossaryTerm[] = [
  {
    term: '资产',
    category: '概念',
    definition: '暮冬念春对小说进行拆解分析后，沉淀下来的结构化知识卡片。每一本书拆完，会产生一组资产，存放在资产库中。就像把一栋房子拆成"户型图、装修方案、水电图纸"，资产就是小说的"设计图纸"。',
    example: '拆完《暮冬念春》，得到声线卡、结构观测、笔法卡、商业观测共 4 张资产卡。',
  },
  {
    term: '声线卡',
    category: '资产',
    definition: '记录某本书（或某个人物）的语言风格特征：句式长短、用词偏好、对话节奏、语气词习惯、叙述视角等。它是"这本书说话像谁"的数字化描述。',
    example: '温霜禾的声线：短句多、爱用"随便吧"、对话带撒娇尾音。',
  },
  {
    term: '结构观测',
    category: '资产',
    definition: '章节结构分析：开篇方式、冲突设置、节奏曲线、高潮位置、结尾手法、视角切换规律等。它回答"这本书的结构是怎么搭的"。',
    example: '第一章用"倒叙+悬念"开篇，第10章第一次大冲突，每8-10章一个小高潮。',
  },
  {
    term: '商业观测',
    category: '资产',
    definition: '从市场角度分析：目标读者画像、爽点/虐点分布、题材热度、商业化潜力、平台适配性。它回答"这本书为什么能卖"。',
    example: '校园救赎题材，爽点集中在"误会解除"章节，目标读者为18-25岁女性。',
  },
  {
    term: '笔法卡',
    category: '资产',
    definition: '具体写作技巧：修辞手法、描写技巧、视角运用、伏笔埋设、转场方式等。它是"这本书的写作手法清单"。',
    example: '用"器物特写"推进情绪，如反复出现的粉色发圈；转场善用"空镜头"。',
  },
  {
    term: '题材包',
    category: '资产',
    definition: '某一题材的完整资产集合：包含该题材的声线、结构、笔法等全部卡片，打包成一个可复用的"题材模板"。写同题材新书时可直接参考。',
    example: '"校园救赎"题材包：含3本书的全部资产，以及该题材的结构规范。',
  },
  {
    term: '文风卡',
    category: '资产',
    definition: '整本书的文风特征描述：语言密度、意象系统、叙事语调、节奏感。它比声线卡更宏观，描述"这本书读起来是什么感觉"。',
    example: '文风：细腻、意象密集、善用通感，读来如江南烟雨。',
  },
  {
    term: '蒸馏规则',
    category: '资产',
    definition: '从多本同题材书中提炼出的通用写作规律。像蒸馏酒一样，把多本书的"精华"提炼出来，去掉每本书特有的"杂质"（具体情节、人物名），留下通用的写作规律。',
    example: '"校园救赎文对话规律：短句为主、每段对话不超过3轮、情绪转折用动作描写间隔"。',
  },
  {
    term: '桥段',
    category: '资产',
    definition: '经典情节套路的结构化描述：包含搭建（setup）、发展、引爆点的骨架，以及多个变体写法。不是抄袭情节，而是学习"这类情节怎么写才好看"。',
    example: '"雨夜共伞"桥段：5种变体写法，核心是"被迫接近→心跳加速→欲言又止"。',
  },
  {
    term: '报告',
    category: '资产',
    definition: '完整的分析报告文档（Markdown格式）：拆书报告、笔法分析等。可导出、可打印。',
    example: '《暮冬念春-拆书报告.md》：全文结构分析、人物分析、主题分析。',
  },
  {
    term: '语料',
    category: '资产',
    definition: '原始文本：导入的 .txt 小说原文，分章节存储。语料是资产的"原材料"，拆书就是从语料中提取资产。',
    example: '《暮冬念春》157章原文，275,379字。',
  },
  {
    term: '蒸馏',
    pinyin: 'zhēng liú',
    category: '功能',
    definition: '一种跨书聚合技术。把同一题材的多本书的资产放在一起，找出它们的共同规律，提炼成"蒸馏规则"。需要同一题材至少2本已拆解的书。蒸馏是本地规则聚合，不需要联网、不需要 AI 模型。',
    example: '输入3本校园文的声线卡 → 输出"校园文开篇三要素：场景+人物+悬念钩子"。',
  },
  {
    term: '题材',
    category: '概念',
    definition: '小说的类别标签，用于组织资产和蒸馏。题材名用英文小写+中划线，如 campus-redemption（校园救赎）。同一题材的书才能一起蒸馏。',
    example: 'campus-redemption、dushi-gaowu、xuanhuan、xianxia。',
  },
  {
    term: '拆书',
    category: '功能',
    definition: '把一本完整小说输入系统，自动进行多维度分析，输出报告+资产卡片的全过程。包含章节切分、质量检测、一致性检测、资产提取四个步骤。',
    example: '导入《暮冬念春》.txt → 得到4张资产卡+2份报告（耗时视章节数和机器性能而定）。',
  },
  {
    term: 'QC',
    pinyin: 'Quality Check',
    category: '功能',
    definition: '质量检验：对文本进行出版级质量检测。分为单章检查（写完一章快速检查，质量12维+一致性5维）和全书QC（完稿后全面检测，四层十二维）。',
    example: '全书QC输出百分制总分和问题列表，标出每处待修改。',
  },
  {
    term: '题材文风卡索引',
    category: '资产',
    definition: '题材到文风卡的映射表：告诉你某个题材有哪些文风卡可用。查询"都市"题材 → 返回该题材下所有文风卡。',
  },
]

// ---------------------------------------------------------------------------
// 数据：功能指南
// ---------------------------------------------------------------------------

interface GuideStep {
  title: string
  detail: string
}

interface FeatureGuide {
  key: string
  title: string
  icon: string
  intro: string
  steps: GuideStep[]
  tips: string[]
  faq: { q: string; a: string }[]
}

const GUIDES: FeatureGuide[] = [
  {
    key: 'analysis',
    title: '分析拆书',
    icon: '📖',
    intro: '把一本完整小说导入系统，自动拆解成资产卡片和报告。这是整个生态的起点：没有拆书，就没有资产；没有资产，蒸馏和辅助写作都无从谈起。注意：拆书需要先配置外部 AI 模型（系统页 → 模型配置），未配置时会直接报错。',
    steps: [
      { title: '配置模型（首次）', detail: '左侧导航 → 系统 → 模型配置，配好外部 AI 模型。拆书、辅助写作都依赖它；蒸馏和 QC 不需要模型。' },
      { title: '点击「选择文件」', detail: '在分析拆书页面，点击「选择文件」按钮（或直接把 .txt 文件拖到虚线框内）。' },
      { title: '选择文件', detail: '在文件选择器中找到你的小说 .txt 文件。要求：① .txt 格式 ② 建议 UTF-8 编码（非 UTF-8 会尝试 GBK 解码）③ 100MB 以内 ④ 章节标题含"第X章"字样（如"第001章 暮冬未尽时"）。' },
      { title: '等待解析', detail: '进度条显示"正在切分章节..." → "正在分析..."。耗时视章节数、字数和机器性能而定，期间不要关闭窗口。' },
      { title: '查看结果', detail: '完成后显示三个页签：① 资产卡（生成的资产预览）② 章节打分 ③ 报告（拆书报告、笔法分析等 Markdown）。' },
      { title: '确认入库', detail: '生成的声线卡、结构观测、笔法卡、商业观测已自动存入「资产库」，可随时查看、引用。' },
    ],
    tips: ['章节标题格式决定切分准确率，务必用"第X章 标题"格式', 'UTF-8编码：用记事本打开→另存为→编码选UTF-8', '首次拆书建议先用语料库中的示例文件试手'],
    faq: [
      { q: '提示"首版仅支持 .txt 导入"？', a: '文件扩展名必须是 .txt，不支持 .doc/.pdf。请先转换为纯文本。' },
      { q: '提示"不允许导入符号链接"？', a: '你选的是快捷方式，请选择源文件本身。' },
      { q: '解析卡住不动？', a: '大文件需要较长时间，看进度条百分比；若长时间无变化，刷新重试。' },
    ],
  },
  {
    key: 'distill',
    title: '蒸馏（高级功能）',
    icon: '⚗️',
    intro: '把同一题材的多本书的资产聚合起来，提炼出这个题材的通用写作规律。这是"从多本书里学一类书怎么写"的核心功能。',
    steps: [
      { title: '确认前置条件', detail: '同一题材至少有2本已拆解的书（在资产库中确认）。比如3本校园文都已拆完。' },
      { title: '进入蒸馏页', detail: '左侧导航 → 高级功能 → 顶部页签点「蒸馏」。' },
      { title: '输入题材名', detail: '在题材输入框填题材名，如 campus-redemption。只能用英文字母、数字、下划线、中划线。' },
      { title: '确认可蒸馏', detail: '页面自动显示"可蒸馏书目：3本"和绿色"可蒸馏"标识。书不足会显示黄色"书目不足"。' },
      { title: '执行蒸馏', detail: '点击「执行蒸馏」，等待结果返回。结果区显示参与书目数、产出数、蒸馏维度。' },
      { title: '查看产物', detail: '去资产库 → 筛选「蒸馏规则」，可看到新生成的 distilled 文件。' },
    ],
    tips: ['蒸馏是本地规则聚合，不联网、不用AI模型', '书越多，提炼出的规律越可靠', '蒸馏产物可直接用于辅助写作的参考'],
    faq: [
      { q: '提示"蒸馏需要 ≥2 本"？', a: '同一题材的书不够。去资产库确认该题材下有几本书，先拆够2本。' },
      { q: '题材名填中文可以吗？', a: '不可以，只能用英文小写+中划线，如 campus-redemption。' },
    ],
  },
  {
    key: 'quality',
    title: '质量检验',
    icon: '🔍',
    intro: '对文本进行出版级质量检测。单章检查用于写完一章后快速把关；全书QC用于完稿后的全面体检。',
    steps: [
      { title: '选择模式', detail: '质量检验页顶部有三个页签：单章检查 / 全书质检 / QC 综合。' },
      { title: '单章检查', detail: '在"章节路径（或粘贴文本）"输入框粘贴章节文本或填路径 → 可选一张 voice-card（选了才有人物一致性5维检测）→ 点击检查。' },
      { title: '全书质检', detail: '在"章节目录路径"输入框填写路径 → 点击「质检」。外部路径仅支持单个 .txt 文件；整本书的章节目录请先放入 novel/ 或 corpus/ 下。' },
      { title: '等待检测', detail: '进度条实时显示当前章节。耗时视章节数和机器性能而定。' },
      { title: '查看报告', detail: '全书质检结果区显示判定结论 + 问题列表。百分制总分、历史报告在「QC 综合」页签查看。' },
    ],
    tips: ['QC 综合页签可回看历史质检记录', '单章检查选上 voice-card，人物一致性检测更准确'],
    faq: [
      { q: '输入路径后报错？', a: '检查三点：① 路径是否正确（从资源管理器地址栏复制）② 文件是否存在 ③ 是否为 .txt 文件。外部目录不支持，请放进 novel/ 或 corpus/。' },
      { q: 'QC要多久？', a: '视章节数和机器性能而定，章节越多越久。单章检查通常很快出结果。' },
    ],
  },
  {
    key: 'writing',
    title: '辅助写作',
    icon: '✍️',
    intro: '调用已配置的外部 AI 模型，参考已拆解书籍的资产生成新内容。注意：必须先在系统页 → 模型配置中配好模型，否则无法生成；无模型时可手动入库正文。',
    steps: [
      { title: '进入写作页签', detail: '辅助写作页顶部有五个页签：注入 / 写作 / 打分 / 组装 / 文风。生成新内容用「写作」页签。' },
      { title: '填写写作信息', detail: '选择项目 → 填章节号 → 选一张 voice-card（决定参考哪本书的风格）→ 在「写作要点」里描述需求，如"写一个校园重逢的开篇，女主在图书馆遇到男主"。' },
      { title: '开始写作', detail: '点击「开始写作」，等待模型返回。耗时取决于模型服务。' },
      { title: '入库', detail: '对结果满意后点击「入库并打分」，正文存入项目并自动打分。不满意可修改写作要点重新生成。' },
    ],
    tips: ['voice-card 决定生成风格，选对参考书很重要', '生成内容是初稿，一定要人工修改润色', '无模型时可用「手动入库」把正文贴回项目'],
    faq: [
      { q: '生成的内容能直接用吗？', a: '不建议。这是初稿辅助，需要你修改润色后才能用。' },
      { q: '为什么生成风格不对？', a: '检查 voice-card 是否选对，它的声线决定了风格。' },
      { q: '点击开始写作报错？', a: '先去系统页 → 模型配置，确认已配置可用模型。' },
    ],
  },
  {
    key: 'assets',
    title: '资产库',
    icon: '📚',
    intro: '所有资产的家。11种资产类型可筛选、可搜索、可查看详情。内置 60+ 项资产卡，开箱即用。',
    steps: [
      { title: '筛选类型', detail: '顶部点击资产类型 Chip（或"全部"）。11种：声线卡、结构观测、商业观测、笔法卡、题材包、文风卡、蒸馏规则、桥段、报告、语料、题材文风卡索引。' },
      { title: '搜索', detail: '搜索框输入关键词过滤，如"校园"。' },
      { title: '查看详情', detail: '点击任意资产 → 右侧滑出详情面板，显示完整JSON内容、关联书籍、生成时间。' },
    ],
    tips: ['不确定术语含义？点本帮助中心的「术语表」', '蒸馏产物在这里筛选「蒸馏规则」查看'],
    faq: [],
  },
  {
    key: 'advanced',
    title: '高级功能（其他）',
    icon: '⚙️',
    intro: '蒸馏之外，还有批量状态、资产编辑、平台适配三个页签。',
    steps: [
      { title: '批量状态', detail: '查看批量拆书任务的进度和状态。' },
      { title: '资产编辑', detail: '选择一个资产手动编辑，修改后保存（创建新版本，保留历史）。' },
      { title: '平台适配', detail: '按目标发布平台的规范检查内容适配情况。' },
    ],
    tips: [],
    faq: [],
  },
  {
    key: 'system',
    title: '系统',
    icon: '🖥️',
    intro: '状态监控、模型配置、应用设置。四个页签：系统状态 / 版权合规 / 模型配置 / 设置。',
    steps: [
      { title: '系统状态', detail: '查看后端服务状态、数据库状态、磁盘使用。' },
      { title: '模型配置', detail: '配置外部 AI 模型。拆书和辅助写作必须先配好模型，否则会报错。' },
      { title: '数据备份', detail: '程序每次启动时自动备份一次数据库（保留最近 3 个），无需手动操作。重要操作前建议自行复制一份数据目录。' },
    ],
    tips: ['每次启动自动备份一次', '重要操作前手动复制一份数据目录更保险'],
    faq: [
      { q: '数据存在哪里？', a: 'Windows: C:\\Users\\你的用户名\\AppData\\Local\\暮冬念春\\' },
      { q: '如何彻底重装？', a: '关闭程序→删除数据目录→用新版安装包重新安装，内置资产会自动恢复。' },
    ],
  },
  {
    key: 'settings',
    title: '设置',
    icon: '🎨',
    intro: '主题、分析参数。改完即时生效。',
    steps: [
      { title: '主题模式', detail: '浅色 / 深色 / 跟随系统，即时生效。' },
      { title: '分析批次大小', detail: '默认4000。单批处理的字符数，越大越快但内存占用高。' },
    ],
    tips: [],
    faq: [],
  },
  {
    key: 'admin',
    title: '管理后台',
    icon: '🔐',
    intro: '审计日志、密码管理。首次登录的初始密码见数据目录下的 admin-初始密码.txt。',
    steps: [
      { title: '获取初始密码', detail: '首次启动时，程序会在数据目录（见下方问答）生成 admin-初始密码.txt，内有管理员初始账号：用户名 admin / 初始密码（仅生成一次）。桌面端无控制台窗口，无黑色终端可看。' },
      { title: '登录', detail: '输入用户名 admin + 初始密码，系统强制要求修改密码。' },
      { title: '使用功能', detail: '六个页签：仪表盘（总览）、书库管理、资产管理、操作日志（查看所有管理操作记录）、会话管理、安全设置（含修改密码）。' },
    ],
    tips: ['初始密码只生成一次，登录后务必立即修改；改密成功后指引文件自动删除', '忘记密码：关闭程序→删除数据目录下的 admin.json→重启'],
    faq: [
      { q: '没看到初始密码？', a: '桌面端没有控制台窗口。去数据目录找 admin-初始密码.txt：Windows 为 C:\\Users\\你的用户名\\AppData\\Local\\暮冬念春\\admin-初始密码.txt。如果文件不在（已改过密码），删 admin.json 重启会重新生成。' },
      { q: '忘记密码怎么办？', a: '关闭程序，删除 C:\\Users\\你的用户名\\AppData\\Local\\暮冬念春\\admin.json，重启会生成新密码。' },
    ],
  },
]

// ---------------------------------------------------------------------------
// 数据：新手上路工作流
// ---------------------------------------------------------------------------

const WORKFLOWS = [
  {
    title: '工作流 A：拆一本书',
    desc: '把《暮冬念春》拆解成资产——整个生态的起点',
    steps: ['系统页 → 模型配置，先配好外部 AI 模型', '分析拆书页点击「选择文件」', '选择 .txt 文件（建议 UTF-8，含"第X章"标题）', '等待解析完成（耗时视章节数和机器性能而定）', '查看资产卡 / 章节打分 / 报告三个页签', '资产已自动存入资产库'],
  },
  {
    title: '工作流 B：蒸馏一个题材',
    desc: '从3本校园文中提炼通用写作规律',
    steps: ['确认同一题材有≥2本已拆解的书', '高级功能 → 蒸馏页签', '输入题材名（如 campus-redemption）', '确认"可蒸馏" → 点击「执行蒸馏」', '去资产库筛选「蒸馏规则」查看产物'],
  },
  {
    title: '工作流 C：质检全书',
    desc: '对完稿小说做出版级质检',
    steps: ['质量检验 → 全书质检页签', '填写章节目录路径（外部单文件也支持）', '点击「质检」，等待检测完成', '查看判定结论和问题列表；总分与历史记录在「QC 综合」页签'],
  },
  {
    title: '工作流 D：辅助写作',
    desc: '参考已拆解的书，生成新内容（需先配置模型）',
    steps: ['系统页 → 模型配置，确认模型可用', '辅助写作 → 写作页签', '选项目、填章节号、选 voice-card', '在「写作要点」填写需求描述', '点击「开始写作」→ 满意后「入库并打分」'],
  },
]

const FAQS = [
  { q: '导入 .txt 后没反应？', a: '检查三点：① 扩展名是否为 .txt ② 是否为 UTF-8 编码（记事本另存为时选 UTF-8；非 UTF-8 会尝试 GBK 解码）③ 文件是否超过 100MB。' },
  { q: '程序启动后窗口没出来？', a: '① 看任务管理器有没有"暮冬念春"进程，有则稍等片刻（首次启动较慢）② 检查端口8000-8099是否被占用。' },
  { q: '杀毒软件报毒？', a: 'Python 打包程序常见误报，添加白名单即可。程序默认不联网；只有当你配置并使用了在线模型功能（拆书、辅助写作）时，相关文本才会发往你配置的模型服务商。' },
  { q: '如何更新到新版本？', a: '运行新版安装包重新安装即可（安装到同一目录）。用户数据在 %LOCALAPPDATA%\\暮冬念春\\，不受影响。' },
  { q: '蒸馏和拆书是什么关系？', a: '拆书是把一本书变成资产；蒸馏是把多本书的资产变成规律。先拆书，后蒸馏。' },
  { q: '资产库里的东西能删除吗？', a: '内置资产建议保留。你生成的资产可在资产库中管理。误删后可从数据目录的自动备份（index.db 的启动备份，保留最近 3 个）中找回，操作前建议先复制一份数据目录。' },
]

// ---------------------------------------------------------------------------
// 组件
// ---------------------------------------------------------------------------

function GlossaryPanel() {
  const [query, setQuery] = useState('')
  const [catFilter, setCatFilter] = useState<string>('全部')
  const filtered = useMemo(() => {
    return GLOSSARY.filter(t => {
      const matchQ = !query || t.term.includes(query) || t.definition.includes(query)
      const matchC = catFilter === '全部' || t.category === catFilter
      return matchQ && matchC
    })
  }, [query, catFilter])

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder="搜索术语…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
          }}
          sx={{ minWidth: 240 }}
        />
        {['全部', '概念', '资产', '功能'].map(c => (
          <Chip
            key={c}
            label={c}
            clickable
            onClick={() => setCatFilter(c)}
            color={catFilter === c ? 'primary' : 'default'}
            variant={catFilter === c ? 'filled' : 'outlined'}
          />
        ))}
      </Box>
      {filtered.map(t => (
        <Card key={t.term} sx={{ mb: 2, border: `1px solid ${ink.line}` }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
              <Typography variant="h6" sx={{ fontFamily: fontStack.serif, color: ink.primary }}>
                {t.term}
              </Typography>
              <Chip label={t.category} size="small" sx={{ bgcolor: ink.primarySoft, color: ink.primary }} />
              {t.pinyin && (
                <Typography variant="caption" color="text.secondary">{t.pinyin}</Typography>
              )}
            </Box>
            <Typography variant="body2" sx={{ mb: t.example ? 1 : 0, lineHeight: 1.8 }}>
              {t.definition}
            </Typography>
            {t.example && (
              <Paper sx={{ p: 1.5, bgcolor: ink.goldSoft, border: `1px dashed ${ink.gold}` }} elevation={0}>
                <Typography variant="body2" sx={{ lineHeight: 1.8 }}>
                  <strong>举例：</strong>{t.example}
                </Typography>
              </Paper>
            )}
          </CardContent>
        </Card>
      ))}
      {filtered.length === 0 && (
        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
          没有找到匹配的术语，换个关键词试试。
        </Typography>
      )}
    </Box>
  )
}

function StartPanel() {
  return (
    <Box>
      <Typography variant="h6" sx={{ fontFamily: fontStack.serif, mb: 2, color: ink.primary }}>
        生态全景：数据是怎么流动的
      </Typography>
      <Paper sx={{ p: 3, mb: 4, bgcolor: ink.primarySoft, border: `1px solid ${ink.line}` }} elevation={0}>
        <Typography variant="body2" sx={{ lineHeight: 2.2, fontFamily: fontStack.mono, whiteSpace: 'pre-wrap' }}>
{`小说 .txt ──▶ 拆书 ──▶ 资产库（11种资产）
                    │
                    ├──▶ 质检报告（QC）
                    │
                    └──▶ 蒸馏 ──▶ 题材规律
                                    │
                                    ▼
                              辅助写作 ──▶ 新内容 ──▶ 质检 ──▶ 闭环`}
        </Typography>
        <Divider sx={{ my: 2 }} />
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>
          记住这个顺序：<strong>先拆书，再蒸馏，最后用资产辅助写作</strong>。
          质检贯穿全程——写完一章用单章检查，完稿用全书QC。
        </Typography>
      </Paper>

      <Typography variant="h6" sx={{ fontFamily: fontStack.serif, mb: 2, color: ink.primary }}>
        四个典型工作流
      </Typography>
      {WORKFLOWS.map((w, i) => (
        <Accordion key={w.title} defaultExpanded={i === 0} sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{w.title}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{w.desc}</Typography>
            <Stepper orientation="vertical">
              {w.steps.map(s => (
                <Step key={s} active>
                  <StepLabel><Typography variant="body2">{s}</Typography></StepLabel>
                </Step>
              ))}
            </Stepper>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  )
}

function GuidesPanel({ anchor }: { anchor: HelpAnchor }) {
  const [expanded, setExpanded] = useState<string | null>(anchor || null)
  React.useEffect(() => {
    if (anchor) setExpanded(anchor)
  }, [anchor])

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.8 }}>
        每个功能模块的详细操作步骤。点击展开查看。
      </Typography>
      {GUIDES.map(g => (
        <Accordion
          key={g.key}
          expanded={expanded === g.key}
          onChange={(_, isExp) => setExpanded(isExp ? g.key : null)}
          sx={{ mb: 1 }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography sx={{ mr: 1.5, fontSize: '1.3em' }}>{g.icon}</Typography>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{g.title}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2, lineHeight: 1.8 }}>
              {g.intro}
            </Typography>
            <Typography variant="subtitle2" sx={{ mb: 1, color: ink.primary }}>操作步骤</Typography>
            <Stepper orientation="vertical" sx={{ mb: 2 }}>
              {g.steps.map(s => (
                <Step key={s.title} active>
                  <StepLabel>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{s.title}</Typography>
                  </StepLabel>
                  <StepContent>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>
                      {s.detail}
                    </Typography>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
            {g.tips.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1, color: ink.goldDeep }}>💡 提示</Typography>
                {g.tips.map(t => (
                  <Typography key={t} variant="body2" color="text.secondary" sx={{ mb: 0.5, lineHeight: 1.8 }}>
                    • {t}
                  </Typography>
                ))}
              </Box>
            )}
            {g.faq.length > 0 && (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, color: ink.primary }}>常见问题</Typography>
                {g.faq.map(f => (
                  <Box key={f.q} sx={{ mb: 1.5 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>Q：{f.q}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>A：{f.a}</Typography>
                  </Box>
                ))}
              </Box>
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  )
}

function FaqPanel() {
  return (
    <Box>
      {FAQS.map(f => (
        <Accordion key={f.q} sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{f.q}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>{f.a}</Typography>
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  )
}

export default function HelpWorkbench({ initialTab = 'start', initialAnchor = null }: HelpWorkbenchProps) {
  const [tab, setTab] = useState<HelpSection>(initialTab)
  React.useEffect(() => {
    setTab(initialTab)
  }, [initialTab])

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ fontFamily: fontStack.serif, mb: 1, color: ink.ink }}>
        帮助中心
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        术语解释、操作指南、工作流、常见问题——都在这里。
      </Typography>
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 3, borderBottom: `1px solid ${ink.line}` }}
      >
        <Tab value="start" label="新手上路" />
        <Tab value="glossary" label="术语表" />
        <Tab value="guides" label="功能指南" />
        <Tab value="faq" label="常见问题" />
      </Tabs>
      {tab === 'start' && <StartPanel />}
      {tab === 'glossary' && <GlossaryPanel />}
      {tab === 'guides' && <GuidesPanel anchor={initialAnchor} />}
      {tab === 'faq' && <FaqPanel />}
    </Box>
  )
}
