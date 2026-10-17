// 应用内帮助中心：术语表 / 新手上路 / 功能指南 / 常见问题。
// 取代独立手册文档，所有帮助内容完整融入应用并全量支持中英文双语国际化。
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
import { useI18n, Locale } from '../state/I18nContext'

export type HelpSection = 'start' | 'glossary' | 'guides' | 'faq'
export type HelpAnchor = string | null

export interface HelpWorkbenchProps {
  initialTab?: HelpSection
  initialAnchor?: HelpAnchor
}

// ---------------------------------------------------------------------------
// 数据：术语表 (双语国际化)
// ---------------------------------------------------------------------------

type TermCategory = 'concept' | 'asset' | 'feature'

interface GlossaryTerm {
  term: Record<Locale, string>
  pinyin?: string
  category: TermCategory
  definition: Record<Locale, string>
  example?: Record<Locale, string>
}

const GLOSSARY: GlossaryTerm[] = [
  {
    term: {
      'zh-CN': '资产',
      'en-US': 'Asset',
    },
    category: 'concept',
    definition: {
      'zh-CN': '系统对小说进行拆解分析后，沉淀下来的结构化知识卡片。每一本书拆完，会产生一组资产，存放在资产库中。就像把一栋房子拆成"户型图、装修方案、水电图纸"，资产就是小说的"设计图纸与叙事构件"。',
      'en-US': 'Structured knowledge cards crystallized after the deconstruction and analysis of a novel. Each analyzed novel generates a set of assets stored in the Asset Library — functioning as architectural blueprints and narrative blueprints.',
    },
    example: {
      'zh-CN': '拆完《暮冬念春》，得到声线卡、结构观测、笔法卡、商业观测共 4 张核心资产卡。',
      'en-US': 'Analyzing a novel produces 4 core asset cards: Voice Card, Structure Observation, Craft Card, and Commercial Observation.',
    },
  },
  {
    term: {
      'zh-CN': '声线卡',
      'en-US': 'Voice Card',
    },
    category: 'asset',
    definition: {
      'zh-CN': '记录某本书（或某个人物）的语言风格特征：句式长短、用词偏好、对话节奏、语气词习惯、叙述视角等。它是"这本书说话像谁"的数字化描述。',
      'en-US': 'Digital profile capturing language style traits of a book or character: sentence length, diction patterns, dialogue cadence, modal particle habits, and narrative point of view.',
    },
    example: {
      'zh-CN': '温霜禾的声线：短句多、爱用"随便吧"、对话带撒娇尾音。',
      'en-US': 'Protagonist voice: predominantly short sentences, distinctive signature phrasing, and lively trailing dialogue tones.',
    },
  },
  {
    term: {
      'zh-CN': '结构观测',
      'en-US': 'Structure Observation',
    },
    category: 'asset',
    definition: {
      'zh-CN': '章节结构分析：开篇方式、冲突设置、节奏曲线、高潮位置、结尾手法、视角切换规律等。它回答"这本书的结构是怎么搭的"。',
      'en-US': 'Chapter macro-structural analysis: hook style, conflict escalation, rhythm curve, climax placement, cliffhanger techniques, and POV switching patterns.',
    },
    example: {
      'zh-CN': '第一章用"倒叙+悬念"开篇，第10章第一次大冲突，每8-10章一个小高潮。',
      'en-US': 'Chapter 1 opens with flashback suspense, Chapter 10 introduces the first major conflict, with micro-climaxes every 8-10 chapters.',
    },
  },
  {
    term: {
      'zh-CN': '商业观测',
      'en-US': 'Commercial Observation',
    },
    category: 'asset',
    definition: {
      'zh-CN': '从市场角度分析：目标读者画像、爽点/虐点分布、题材热度、商业化潜力、平台适配性。它回答"这本书为什么能卖"。',
      'en-US': 'Market-oriented analysis: target audience persona, payoff/angst distribution, genre market warmth, monetization potential, and platform fit.',
    },
    example: {
      'zh-CN': '校园救赎题材，爽点集中在"误会解除"章节，目标读者为18-25岁女性。',
      'en-US': 'Campus redemption genre: emotional payoffs concentrated in misunderstanding resolution chapters; core audience female ages 18-25.',
    },
  },
  {
    term: {
      'zh-CN': '笔法卡',
      'en-US': 'Craft Card',
    },
    category: 'asset',
    definition: {
      'zh-CN': '具体写作技巧：修辞手法、描写技巧、视角运用、伏笔埋设、转场方式等。它是"这本书的写作手法清单"。',
      'en-US': 'Concrete prose techniques: rhetorical devices, sensory description, POV handling, foreshadowing placement, and scene transition mechanics.',
    },
    example: {
      'zh-CN': '用"器物特写"推进情绪，如反复出现的粉色发圈；转场善用"空镜头"。',
      'en-US': 'Prop close-ups driving emotional arcs (recurring keepsake); scene transitions utilizing empty space cutaways.',
    },
  },
  {
    term: {
      'zh-CN': '题材包',
      'en-US': 'Genre Pack',
    },
    category: 'asset',
    definition: {
      'zh-CN': '某一题材的完整资产集合：包含该题材的声线、结构、笔法等全部卡片，打包成一个可复用的"题材模板"。写同题材新书时可直接参考。',
      'en-US': 'Comprehensive asset bundle for a genre: aggregates voice, structure, and craft cards into a reusable narrative template for direct reference in new projects.',
    },
    example: {
      'zh-CN': '"校园救赎"题材包：含3本书的全部资产，以及该题材的结构规范。',
      'en-US': '"Campus Redemption" pack: bundles assets from 3 benchmark novels along with standardized structural conventions.',
    },
  },
  {
    term: {
      'zh-CN': '文风卡',
      'en-US': 'Style Card',
    },
    category: 'asset',
    definition: {
      'zh-CN': '整本书的文风特征描述：语言密度、意象系统、叙事语调、节奏感。它比声线卡更宏观，描述"这本书读起来是什么感觉"。',
      'en-US': 'Holistic prose fingerprint description: linguistic density, sensory imagery, narrative tone, and overall rhythm — capturing the subjective reading experience.',
    },
    example: {
      'zh-CN': '文风：细腻、意象密集、善用通感，读来如江南烟雨。',
      'en-US': 'Prose tone: nuanced, dense sensory imagery, synesthesia, evocative and immersive cadence.',
    },
  },
  {
    term: {
      'zh-CN': '蒸馏规则',
      'en-US': 'Distilled Rule',
    },
    category: 'asset',
    definition: {
      'zh-CN': '从多本同题材书中提炼出的通用写作规律。像蒸馏酒一样，把多本书的"精华"提炼出来，去掉每本书特有的"杂质"（具体情节、人物名），留下通用的写作规律。',
      'en-US': 'Universal writing heuristics extracted across multiple books of the same genre, abstracting away novel-specific entities while preserving invariant craft mechanics.',
    },
    example: {
      'zh-CN': '"校园救赎文对话规律：短句为主、每段对话不超过3轮、情绪转折用动作描写间隔"。',
      'en-US': '"Dialogue rule: brief exchanges under 3 beats, emotional shifts punctuated by physical action beats".',
    },
  },
  {
    term: {
      'zh-CN': '桥段',
      'en-US': 'Trope',
    },
    category: 'asset',
    definition: {
      'zh-CN': '经典情节套路的结构化描述：包含搭建（setup）、发展、引爆点的骨架，以及多个变体写法。不是抄袭情节，而是学习"这类情节怎么写才好看"。',
      'en-US': 'Structured anatomy of classic plot conventions: setup, escalation, and climax payoff skeletons along with stylistic variations.',
    },
    example: {
      'zh-CN': '"雨夜共伞"桥段：5种变体写法，核心是"被迫接近→心跳加速→欲言又止"。',
      'en-US': '"Sharing an Umbrella in the Rain" trope: 5 variations centered on forced proximity, racing heartbeat, and hesitation to speak.',
    },
  },
  {
    term: {
      'zh-CN': '报告',
      'en-US': 'Report',
    },
    category: 'asset',
    definition: {
      'zh-CN': '完整的分析报告文档（Markdown格式）：拆书报告、笔法分析等。可导出、可打印。',
      'en-US': 'Comprehensive analytical documents in Markdown format: deconstruction reports, prose craft evaluations, exportable and printable.',
    },
    example: {
      'zh-CN': '《暮冬念春-拆书报告.md》：全文结构分析、人物分析、主题分析。',
      'en-US': '"Late-Winter-Analysis-Report.md": full structural analysis, character breakdown, and thematic breakdown.',
    },
  },
  {
    term: {
      'zh-CN': '语料',
      'en-US': 'Corpus',
    },
    category: 'asset',
    definition: {
      'zh-CN': '原始文本：导入的 .txt 小说原文，分章节存储。语料是资产的"原材料"，拆书就是从语料中提取资产。',
      'en-US': 'Raw source manuscripts: imported .txt novel texts segmented by chapter. Corpus acts as the foundational raw material for asset extraction.',
    },
    example: {
      'zh-CN': '《暮冬念春》157章原文，275,379字。',
      'en-US': 'Raw novel text: 157 chapters, 275,379 words/characters.',
    },
  },
  {
    term: {
      'zh-CN': '蒸馏',
      'en-US': 'Distillation',
    },
    pinyin: 'zhēng liú',
    category: 'feature',
    definition: {
      'zh-CN': '一种跨书聚合技术。把同一题材的多本书的资产放在一起，找出它们的共同规律，提炼成"蒸馏规则"。需要同一题材至少2本已拆解的书。蒸馏是本地规则聚合，不需要联网、不需要 AI 模型。',
      'en-US': 'Cross-book aggregation engine. Synthesizes assets across multiple novels in the same genre to extract common conventions into Distilled Rules (requires >= 2 analyzed books; 100% offline rule aggregation, no AI model required).',
    },
    example: {
      'zh-CN': '输入3本校园文的声线卡 → 输出"校园文开篇三要素：场景+人物+悬念钩子"。',
      'en-US': 'Input 3 campus voice cards -> Output "Campus opening trifecta: setting + character introduction + suspense hook".',
    },
  },
  {
    term: {
      'zh-CN': '题材',
      'en-US': 'Genre',
    },
    category: 'concept',
    definition: {
      'zh-CN': '小说的类别标签，用于组织资产和蒸馏。题材名用英文小写+中划线，如 campus-redemption（校园救赎）。同一题材的书才能一起蒸馏。',
      'en-US': 'Novel taxonomy identifier used to categorize assets and govern distillation pipelines. Formatted as lowercase alphanumeric with hyphens (e.g., campus-redemption).',
    },
    example: {
      'zh-CN': 'campus-redemption、dushi-gaowu、xuanhuan、xianxia。',
      'en-US': 'campus-redemption, litrpg, western-fantasy, progression-fantasy.',
    },
  },
  {
    term: {
      'zh-CN': '拆书',
      'en-US': 'Book Analysis',
    },
    category: 'feature',
    definition: {
      'zh-CN': '把一本完整小说输入系统，自动进行多维度分析，输出报告+资产卡片的全过程。包含章节切分、质量检测、一致性检测、资产提取四个步骤。',
      'en-US': 'End-to-end multi-dimensional deconstruction pipeline: chapter segmentation, quality audit, consistency check, and structured asset extraction.',
    },
    example: {
      'zh-CN': '导入《暮冬念春》.txt → 得到4张资产卡+2份报告（耗时视章节数和机器性能而定）。',
      'en-US': 'Import novel .txt -> Generate 4 asset cards + 2 analytical reports.',
    },
  },
  {
    term: {
      'zh-CN': 'QC',
      'en-US': 'QC (Quality Check)',
    },
    pinyin: 'Quality Check',
    category: 'feature',
    definition: {
      'zh-CN': '质量检验：对文本进行出版级质量检测。分为单章检查（写完一章快速检查，质量12维+一致性5维）和全书QC（完稿后全面检测，四层十二维）。',
      'en-US': 'Quality Control: publication-grade manuscript audit. Spans Chapter Inspection (12 quality metrics + 5 consistency checks) and Full Book QC (4 layers, 12 dimensions).',
    },
    example: {
      'zh-CN': '全书QC输出百分制总分和问题列表，标出每处待修改。',
      'en-US': 'Full Book QC outputs 100-point composite score and itemized revision checklist.',
    },
  },
  {
    term: {
      'zh-CN': '题材文风卡索引',
      'en-US': 'Genre Style Index',
    },
    category: 'asset',
    definition: {
      'zh-CN': '题材到文风卡的映射表：告诉你某个题材有哪些文风卡可用。查询"都市"题材 → 返回该题材下所有文风卡。',
      'en-US': 'Mapping directory linking genres to available style cards, enabling instant lookup of prose benchmarks within any selected genre.',
    },
    example: {
      'zh-CN': '查询 "dushi" 题材 → 返回都市题材下关联的所有文风指纹与声线卡。',
      'en-US': 'Querying "dushi" genre -> retrieves all associated style fingerprints and voice cards.',
    },
  },
]

// ---------------------------------------------------------------------------
// 数据：功能指南 (双语国际化)
// ---------------------------------------------------------------------------

interface GuideStep {
  title: Record<Locale, string>
  detail: Record<Locale, string>
}

interface FeatureGuide {
  key: string
  title: Record<Locale, string>
  icon: string
  intro: Record<Locale, string>
  steps: GuideStep[]
  tips: Array<Record<Locale, string>>
  faq: Array<{ q: Record<Locale, string>; a: Record<Locale, string> }>
}

const GUIDES: FeatureGuide[] = [
  {
    key: 'analysis',
    title: {
      'zh-CN': '分析拆书',
      'en-US': 'Book Analysis',
    },
    icon: '📖',
    intro: {
      'zh-CN': '把一本完整小说导入系统，自动拆解成资产卡片和报告。这是整个生态的起点：没有拆书，就没有资产；没有资产，蒸馏和辅助写作都无从谈起。注意：拆书需要先配置外部 AI 模型（系统页 → 模型配置），未配置时会直接报错。',
      'en-US': 'Imports a full novel manuscript into the system, automatically deconstructing it into structured asset cards and analytical reports. Note: Book analysis requires a configured external AI model (System -> Model Config).',
    },
    steps: [
      {
        title: { 'zh-CN': '配置模型（首次）', 'en-US': 'Configure Model (First-time)' },
        detail: { 'zh-CN': '左侧导航 → 系统 → 模型配置，配好外部 AI 模型。拆书、辅助写作都依赖它；蒸馏和 QC 不需要模型。', 'en-US': 'Left Nav -> System -> Model Config: set up external AI model. Distillation and QC run 100% offline without models.' },
      },
      {
        title: { 'zh-CN': '点击「选择文件」', 'en-US': 'Click "Select File"' },
        detail: { 'zh-CN': '在分析拆书页面，点击「选择文件」按钮（或直接把 .txt 文件拖到虚线框内）。', 'en-US': 'On the Book Analysis page, click "Select File" or drag and drop a .txt file into the dropzone.' },
      },
      {
        title: { 'zh-CN': '选择文件', 'en-US': 'Select File' },
        detail: { 'zh-CN': '在文件选择器中找到你的小说 .txt 文件。要求：① .txt 格式 ② 建议 UTF-8 编码（非 UTF-8 会尝试 GBK 解码）③ 100MB 以内 ④ 章节标题含"第X章"字样（如"第001章 暮冬未尽时"）。', 'en-US': 'Choose your novel .txt file. Requirements: 1) .txt format, 2) UTF-8 encoding (GBK fallback supported), 3) Under 100MB, 4) Standard chapter title headers.' },
      },
      {
        title: { 'zh-CN': '等待解析', 'en-US': 'Wait for Processing' },
        detail: { 'zh-CN': '进度条显示"正在切分章节..." → "正在分析..."。耗时视章节数、字数和机器性能而定，期间不要关闭窗口。', 'en-US': 'Progress bar tracks segmentation and multi-pass analysis. Time required depends on length and system specs.' },
      },
      {
        title: { 'zh-CN': '查看结果', 'en-US': 'Review Results' },
        detail: { 'zh-CN': '完成后显示三个页签：① 资产卡（生成的资产预览）② 章节打分 ③ 报告（拆书报告、笔法分析等 Markdown）。', 'en-US': 'Three sub-tabs display results upon completion: 1) Asset Cards, 2) Chapter Scores, 3) Markdown Reports.' },
      },
      {
        title: { 'zh-CN': '确认入库', 'en-US': 'Confirm Storage' },
        detail: { 'zh-CN': '生成的声线卡、结构观测、笔法卡、商业观测已自动存入「资产库」，可随时查看、引用。', 'en-US': 'Generated voice, structure, craft, and commercial observation cards are automatically stored in the Asset Library.' },
      },
    ],
    tips: [
      { 'zh-CN': '章节标题格式决定切分准确率，务必用"第X章 标题"或"Chapter X"格式', 'en-US': 'Standard chapter headers govern segmentation accuracy (e.g., "Chapter 1 Title")' },
      { 'zh-CN': 'UTF-8编码：用记事本打开→另存为→编码选UTF-8', 'en-US': 'Save as UTF-8 in your text editor for optimal compatibility' },
      { 'zh-CN': '首次拆书建议先用语料库中的示例文件试手', 'en-US': 'Try sample manuscripts from the corpus to test-drive the workflow first' },
    ],
    faq: [
      {
        q: { 'zh-CN': '提示"首版仅支持 .txt 导入"？', 'en-US': 'Error: "Only .txt import supported"?' },
        a: { 'zh-CN': '文件扩展名必须是 .txt，不支持 .doc/.pdf。请先转换为纯文本。', 'en-US': 'File extension must be .txt (.doc/.pdf not supported directly). Please convert to plain text first.' },
      },
      {
        q: { 'zh-CN': '提示"不允许导入符号链接"？', 'en-US': 'Error: "Symlinks not allowed"?' },
        a: { 'zh-CN': '你选的是快捷方式或符号链接，请选择源文件本身。', 'en-US': 'A symlink or shortcut was chosen. Please select the actual source file.' },
      },
      {
        q: { 'zh-CN': '解析卡住不动？', 'en-US': 'Analysis appears frozen?' },
        a: { 'zh-CN': '大文件需要较长时间，看进度条百分比；若长时间无变化，刷新重试。', 'en-US': 'Large manuscripts take longer. Monitor the progress percentage; refresh if stalled.' },
      },
    ],
  },
  {
    key: 'distill',
    title: {
      'zh-CN': '蒸馏（高级功能）',
      'en-US': 'Distillation (Advanced)',
    },
    icon: '⚗️',
    intro: {
      'zh-CN': '把同一题材的多本书的资产聚合起来，提炼出这个题材的通用写作规律。这是"从多本书里学一类书怎么写"的核心功能。',
      'en-US': 'Aggregates assets across multiple novels in the same genre to synthesize universal writing rules and conventions.',
    },
    steps: [
      {
        title: { 'zh-CN': '确认前置条件', 'en-US': 'Verify Prerequisites' },
        detail: { 'zh-CN': '同一题材至少有2本已拆解的书（在资产库中确认）。比如3本校园文都已拆完。', 'en-US': 'Ensure at least 2 analyzed novels exist under the target genre in the Asset Library.' },
      },
      {
        title: { 'zh-CN': '进入蒸馏页', 'en-US': 'Open Distillation Tab' },
        detail: { 'zh-CN': '左侧导航 → 高级功能 → 顶部页签点「蒸馏」。', 'en-US': 'Left Nav -> Advanced Features -> click the "Distillation" tab.' },
      },
      {
        title: { 'zh-CN': '输入题材名', 'en-US': 'Enter Genre Slug' },
        detail: { 'zh-CN': '在题材输入框填题材名，如 campus-redemption。只能用英文字母、数字、下划线、中划线。', 'en-US': 'Enter genre identifier (e.g. campus-redemption or litrpg) using alphanumeric and hyphens.' },
      },
      {
        title: { 'zh-CN': '确认可蒸馏', 'en-US': 'Verify Distillability' },
        detail: { 'zh-CN': '页面自动显示"可蒸馏书目：3本"和绿色"可蒸馏"标识。书不足会显示黄色"书目不足"。', 'en-US': 'Status shows "Available Books: N" and green "Ready to Distill" chip. Yellow warns if fewer than 2 books.' },
      },
      {
        title: { 'zh-CN': '执行蒸馏', 'en-US': 'Execute Distillation' },
        detail: { 'zh-CN': '点击「执行蒸馏」，等待结果返回。结果区显示参与书目数、产出数、蒸馏维度。', 'en-US': 'Click "Execute Distillation". Results display participant book count, output count, and extracted dimensions.' },
      },
      {
        title: { 'zh-CN': '查看产物', 'en-US': 'Inspect Distilled Rules' },
        detail: { 'zh-CN': '去资产库 → 筛选「蒸馏规则」，可看到新生成的 distilled 文件。', 'en-US': 'Go to Asset Library -> filter by "Distilled Rule" to view newly generated rules.' },
      },
    ],
    tips: [
      { 'zh-CN': '蒸馏是本地规则聚合，不联网、不用AI模型', 'en-US': 'Distillation is 100% offline rule aggregation, no AI model or network required' },
      { 'zh-CN': '书越多，提炼出的规律越可靠', 'en-US': 'The more books analyzed in the genre, the higher the statistical reliability' },
      { 'zh-CN': '蒸馏产物可直接用于辅助写作的参考', 'en-US': 'Distilled rules directly guide assisted writing prompts and constraints' },
    ],
    faq: [
      {
        q: { 'zh-CN': '提示"蒸馏需要 ≥2 本"？', 'en-US': 'Error: "Distillation requires >= 2 books"?' },
        a: { 'zh-CN': '同一题材的书不够。去资产库确认该题材下有几本书，先拆够2本。', 'en-US': 'Insufficient books under this genre. Analyze at least 2 books for this genre first.' },
      },
      {
        q: { 'zh-CN': '题材名填中文可以吗？', 'en-US': 'Can genre names be Chinese?' },
        a: { 'zh-CN': '不可以，只能用英文小写+中划线，如 campus-redemption。', 'en-US': 'No, please use lowercase English letters, numbers, and hyphens (e.g., campus-redemption).' },
      },
    ],
  },
  {
    key: 'quality',
    title: {
      'zh-CN': '质量检验',
      'en-US': 'Quality Inspection',
    },
    icon: '🔍',
    intro: {
      'zh-CN': '对文本进行出版级质量检测。单章检查用于写完一章后快速把关；全书QC用于完稿后的全面体检。',
      'en-US': 'Executes publication-grade manuscript audits. Chapter Inspection audits single chapters; Full Book QC audits entire novel corpora.',
    },
    steps: [
      {
        title: { 'zh-CN': '选择模式', 'en-US': 'Select Inspection Mode' },
        detail: { 'zh-CN': '质量检验页顶部有四个页签：单章检查 / 全书质检 / QC 综合 / 毒点避雷。', 'en-US': 'Quality Workbench has 4 sub-tabs: Chapter Check, Full Book QC, QC Overview, and Poison Check.' },
      },
      {
        title: { 'zh-CN': '单章检查', 'en-US': 'Chapter Check' },
        detail: { 'zh-CN': '在"章节路径（或粘贴文本）"输入框粘贴章节文本或填路径（桌面版可直接点「选择文件…」）→ 可选一张 voice-card（选了才有人物一致性5维检测）→ 点击检查。', 'en-US': 'Paste text or provide chapter path (desktop provides native "Pick File..."), optionally select a voice card for 5D character consistency checks, then click Check.' },
      },
      {
        title: { 'zh-CN': '全书质检', 'en-US': 'Full Book QC' },
        detail: { 'zh-CN': '在"章节目录路径"输入框填写路径（桌面版可点「选择目录…」）→ 点击「质检」。任意外部路径均支持：自动按 .txt 采集（上限 2000 章 / 200MB）。', 'en-US': 'Enter chapter folder path (desktop provides "Pick Directory...") -> Click "Inspect". Supports arbitrary filesystem folders (up to 2000 chapters / 200MB).' },
      },
      {
        title: { 'zh-CN': '等待检测', 'en-US': 'Wait for Audit' },
        detail: { 'zh-CN': '进度条实时显示当前章节。耗时视章节数和机器性能而定。', 'en-US': 'Real-time progress tracks current chapter processing.' },
      },
      {
        title: { 'zh-CN': '查看报告', 'en-US': 'View QC Reports' },
        detail: { 'zh-CN': '全书质检结果区显示判定结论 + 问题列表。百分制总分、历史报告在「QC 综合」页签查看。', 'en-US': 'Inspect verdicts and itemized defect lists; view 100-point composite score and historical audits in "QC Overview".' },
      },
    ],
    tips: [
      { 'zh-CN': 'QC 综合页签可回看历史质检记录与落盘报告', 'en-US': 'QC Overview tab stores all historical audit runs and saved Markdown reports' },
      { 'zh-CN': '单章检查选上 voice-card，人物一致性检测更准确', 'en-US': 'Linking a reference Voice Card enables strict character dialogue consistency checks' },
    ],
    faq: [
      {
        q: { 'zh-CN': '输入路径后报错？', 'en-US': 'Error after specifying folder path?' },
        a: { 'zh-CN': '检查四点：① 路径是否正确 ② 目录是否存在 ③ 章节是否为 .txt ④ 是否超限（单章 50MB、单目录 2000 个 .txt / 200MB）。', 'en-US': 'Check 4 factors: 1) Path validity, 2) Directory existence, 3) Chapters are .txt, 4) Limits respected (50MB/chapter, 2000 files/folder).' },
      },
      {
        q: { 'zh-CN': 'QC要多久？', 'en-US': 'How long does QC take?' },
        a: { 'zh-CN': '视章节数和机器性能而定。单章检查通常秒级出结果，百章全书约需数秒到一分钟。', 'en-US': 'Depends on chapter count. Single chapters audit in under a second; 100 chapters take a few seconds.' },
      },
    ],
  },
  {
    key: 'writing',
    title: {
      'zh-CN': '辅助写作',
      'en-US': 'Assisted Writing',
    },
    icon: '✍️',
    intro: {
      'zh-CN': '调用已配置的外部 AI 模型，参考已拆解书籍的资产生成新内容。注意：必须先在系统页 → 模型配置中配好模型，否则无法生成；无模型时可手动入库正文。',
      'en-US': 'Drafts new chapters powered by deconstructed assets and configured AI models. If no model is configured, manual chapter entry is available.',
    },
    steps: [
      {
        title: { 'zh-CN': '进入写作工坊', 'en-US': 'Open Writing Studio' },
        detail: { 'zh-CN': '辅助写作提供沉浸式创作室（Studio）与工坊流水线（Pipeline）双模式，并集成大纲/人物卡/便签/统计。', 'en-US': 'Writing Workbench offers Studio and Pipeline modes, integrating Outlines, Characters, Notes, and Word Count stats.' },
      },
      {
        title: { 'zh-CN': '填写写作信息', 'en-US': 'Specify Chapter Parameters' },
        detail: { 'zh-CN': '选择项目 → 填章节号 → 选一张 voice-card（决定参考哪本书的风格）→ 在「写作要点」里描述需求。', 'en-US': 'Select project, set chapter index, link reference Voice Card, and enter scene outline requirements.' },
      },
      {
        title: { 'zh-CN': '开始写作', 'en-US': 'Generate Draft' },
        detail: { 'zh-CN': '点击「开始写作」，等待模型流式或异步返回。耗时取决于模型服务响应速度。', 'en-US': 'Click "Start Writing" and stream output from your configured AI model.' },
      },
      {
        title: { 'zh-CN': '入库与排毒', 'en-US': 'Save and Audit' },
        detail: { 'zh-CN': '对结果满意后点击「入库并打分」，并可通过一键毒点避雷与去 AI 味排查确保稿件品质。', 'en-US': 'Click "Save & Score", then run one-click Poison Check and Anti-Slop audits to guarantee manuscript quality.' },
      },
    ],
    tips: [
      { 'zh-CN': 'voice-card 决定生成风格，选对参考书很重要', 'en-US': 'The Voice Card dictates character phrasing and narrative cadence' },
      { 'zh-CN': '生成内容是初稿，建议配合去 AI 味工具人工润色', 'en-US': 'AI-generated drafts serve as scaffolds; polish with Anti-Slop and Diff Review tools' },
      { 'zh-CN': '无模型时可用「手动入库」把正文贴回项目并打分', 'en-US': 'Manual Chapter Entry allows saving and scoring human-written chapters without AI' },
    ],
    faq: [
      {
        q: { 'zh-CN': '生成的内容能直接发布吗？', 'en-US': 'Can generated prose be published directly?' },
        a: { 'zh-CN': '不建议。这是初稿外骨骼辅助，需要人工润色、把控核心爽点与情绪节奏。', 'en-US': 'Not recommended. Exoscribe serves as a creative exoskeleton; refine prose and pacing manually.' },
      },
      {
        q: { 'zh-CN': '为什么生成风格不对？', 'en-US': 'Why does the generated voice feel off?' },
        a: { 'zh-CN': '检查 voice-card 是否选对，并确认写作要点中是否添加了明确的情绪与视角约束。', 'en-US': 'Verify that the correct Voice Card is selected and emotional constraints are explicitly outlined.' },
      },
    ],
  },
  {
    key: 'assets',
    title: {
      'zh-CN': '资产库',
      'en-US': 'Asset Library',
    },
    icon: '📚',
    intro: {
      'zh-CN': '所有资产的家。11种资产类型可筛选、可搜索、可查看详情。内置 100+ 项资产卡，开箱即用。',
      'en-US': 'The home for all crystallized assets. Filter, search, and inspect 11 asset kinds, with 100+ production assets ready out of the box.',
    },
    steps: [
      {
        title: { 'zh-CN': '筛选类型', 'en-US': 'Filter by Kind' },
        detail: { 'zh-CN': '顶部点击资产类型 Chip（或"全部"）。涵盖声线卡、结构、商业、笔法、题材包、文风卡、蒸馏规则、桥段、报告、语料与索引。', 'en-US': 'Filter across 11 kinds: Voice, Structure, Commercial, Craft, Genre Pack, Style, Distilled Rules, Tropes, Reports, Corpus, and Index.' },
      },
      {
        title: { 'zh-CN': '搜索与筛选', 'en-US': 'Search and Filter' },
        detail: { 'zh-CN': '搜索框输入关键词过滤，或点击左侧分类树快速定位指定题材资产。', 'en-US': 'Search keywords or use the category sidebar to instantly navigate genre assets.' },
      },
      {
        title: { 'zh-CN': '查看详情', 'en-US': 'Inspect Details' },
        detail: { 'zh-CN': '点击任意资产 → 右侧展示结构化中文/英文可读摘要，高级用户可展开原始 JSON 数据。', 'en-US': 'Click any asset card to view human-readable summaries or expand the raw JSON inspector.' },
      },
    ],
    tips: [
      { 'zh-CN': '不确定术语含义？点击本帮助中心的「术语表」查询', 'en-US': 'Unsure about an asset concept? Check the Glossary tab in this Help Center' },
      { 'zh-CN': '蒸馏产物可在资产库筛选「蒸馏规则」直接查看', 'en-US': 'Distilled rules can be reviewed under the "Distilled Rule" asset filter' },
    ],
    faq: [],
  },
  {
    key: 'advanced',
    title: {
      'zh-CN': '高级功能（其他）',
      'en-US': 'Advanced Features',
    },
    icon: '⚙️',
    intro: {
      'zh-CN': '蒸馏之外，还提供批量状态、资产编辑、平台适配等高阶工坊模块。',
      'en-US': 'Beyond distillation, includes batch task monitoring, asset JSON editing, and target publishing platform adaptation.',
    },
    steps: [
      {
        title: { 'zh-CN': '批量状态', 'en-US': 'Batch Tasks' },
        detail: { 'zh-CN': '查看批量拆书任务的进度与状态，支持实时刷新与错误追踪。', 'en-US': 'Monitor batch deconstruction tasks with real-time SSE progress.' },
      },
      {
        title: { 'zh-CN': '资产编辑', 'en-US': 'Asset Editing' },
        detail: { 'zh-CN': '选择一个资产手动编辑，保存时自动创建安全版本镜像并保留历史。', 'en-US': 'Manually edit asset JSON schemas with automatic version archiving.' },
      },
      {
        title: { 'zh-CN': '平台适配', 'en-US': 'Platform Adaptation' },
        detail: { 'zh-CN': '按目标主流发布平台（番茄、起点、晋江、Royal Road、Webnovel 等）的签约规范做针对性适配。', 'en-US': 'Audit manuscripts against editorial rules for Fanqie, Qidian, Jinjiang, Royal Road, and Webnovel.' },
      },
    ],
    tips: [],
    faq: [],
  },
  {
    key: 'system',
    title: {
      'zh-CN': '系统',
      'en-US': 'System',
    },
    icon: '🖥️',
    intro: {
      'zh-CN': '状态监控、模型配置、应用设置。涵盖系统状态 / 版权合规 / 模型配置 / 存储维护。',
      'en-US': 'Health telemetry, external AI model configuration, and environment setup across System Status, Compliance, and Models.',
    },
    steps: [
      {
        title: { 'zh-CN': '系统状态', 'en-US': 'System Telemetry' },
        detail: { 'zh-CN': '查看后端服务状态、数据库健康指标与磁盘使用情况。', 'en-US': 'Monitor backend services, SQLite health metrics, and disk allocation.' },
      },
      {
        title: { 'zh-CN': '模型配置', 'en-US': 'Model Configuration' },
        detail: { 'zh-CN': '配置外部 AI 模型。拆书和辅助写作需要配置可用模型。', 'en-US': 'Configure external AI endpoints and API keys for analysis and drafting.' },
      },
      {
        title: { 'zh-CN': '数据备份', 'en-US': 'Data Backups' },
        detail: { 'zh-CN': '程序每次启动时自动备份一次 SQLite 数据库（保留最近 3 个备份），无需手动操作。', 'en-US': 'Database is automatically snapshotted on launch (retains latest 3 backups).' },
      },
    ],
    tips: [
      { 'zh-CN': '每次启动自动备份一次数据库，防止误操作数据丢失', 'en-US': 'Automatic backup on launch guarantees disaster recovery' },
      { 'zh-CN': '重大版本迁移前手动复制一份数据目录更保险', 'en-US': 'Manual copies of your data directory provide extra redundancy before migrations' },
    ],
    faq: [
      {
        q: { 'zh-CN': '数据存在哪里？', 'en-US': 'Where is data stored?' },
        a: { 'zh-CN': 'Windows: %LOCALAPPDATA%\\暮冬念春\\（或当前数据目录下的 gui_state/index.db）', 'en-US': 'Windows: %LOCALAPPDATA%\\暮冬念春\\ (or gui_state/index.db in your project data root).' },
      },
      {
        q: { 'zh-CN': '如何彻底重装？', 'en-US': 'How to perform a clean reinstall?' },
        a: { 'zh-CN': '关闭程序 → 备份/删除数据目录 → 用新版安装包重新安装，内置资产会自动恢复。', 'en-US': 'Close app -> clean data directory -> install with latest installer. Built-in assets auto-restore.' },
      },
    ],
  },
  {
    key: 'settings',
    title: {
      'zh-CN': '设置',
      'en-US': 'Settings',
    },
    icon: '🎨',
    intro: {
      'zh-CN': '主题模式、双语国际化切换与分析参数配置，改完即时生效。',
      'en-US': 'Theme mode, bilingual language switching, and analysis batch parameters with real-time effect.',
    },
    steps: [
      {
        title: { 'zh-CN': '主题模式', 'en-US': 'Theme Mode' },
        detail: { 'zh-CN': '浅色 / 深色 / 跟随系统，切换后界面实时更新。', 'en-US': 'Toggle between Light, Dark, or System mode with instant UI re-rendering.' },
      },
      {
        title: { 'zh-CN': '双语国际化', 'en-US': 'Language / i18n' },
        detail: { 'zh-CN': '支持简体中文 (zh-CN) 与英文 (en-US) 一键切换，全应用双语贯通。', 'en-US': 'Switch between Simplified Chinese (zh-CN) and English (en-US) across all workbenches.' },
      },
      {
        title: { 'zh-CN': '分析批次大小', 'en-US': 'Analysis Batch Size' },
        detail: { 'zh-CN': '默认 4000 字符。单批处理字符数越大越快，但对模型上下文与内存要求更高。', 'en-US': 'Default 4000 characters per batch. Larger batches process faster with higher memory usage.' },
      },
    ],
    tips: [],
    faq: [],
  },
  {
    key: 'admin',
    title: {
      'zh-CN': '管理后台',
      'en-US': 'Admin Portal',
    },
    icon: '🔐',
    intro: {
      'zh-CN': '审计日志、会话管控与管理员密码安全管理。首次登录的初始密码见数据目录下的指引文件。',
      'en-US': 'Audit logging, credential rotation, and session management. First-time admin credentials are saved in data directory.',
    },
    steps: [
      {
        title: { 'zh-CN': '获取初始密码', 'en-US': 'Obtain Initial Password' },
        detail: { 'zh-CN': '首次启动时，程序会在数据目录生成 admin-初始密码.txt，内含管理员初始账号及随机初始密码。', 'en-US': 'On first launch, admin-初始密码.txt is created in the data directory with the initial password.' },
      },
      {
        title: { 'zh-CN': '登录后台', 'en-US': 'Sign In' },
        detail: { 'zh-CN': '输入用户名 admin + 初始密码，系统强制要求修改为安全密码。', 'en-US': 'Sign in with admin credentials; the system mandates an immediate password change.' },
      },
      {
        title: { 'zh-CN': '管理与审计', 'en-US': 'Governance & Audit' },
        detail: { 'zh-CN': '包含仪表盘、书库管理、资产管理、操作日志、会话管理与安全设置六大板块。', 'en-US': 'Access Dashboard, Books, Assets, Audit Logs, Sessions, and Security Settings.' },
      },
    ],
    tips: [
      { 'zh-CN': '初始密码仅生成一次，登录后务必立即修改；改密成功后指引文件自动销毁', 'en-US': 'Initial password generates once; hint file auto-deletes upon successful password change' },
      { 'zh-CN': '忘记密码：关闭程序 → 删除数据目录下的 admin.json → 重启即可重新生成', 'en-US': 'Forgot password: shut down app -> delete admin.json in data folder -> relaunch' },
    ],
    faq: [
      {
        q: { 'zh-CN': '没看到初始密码？', 'en-US': 'Cannot find initial password?' },
        a: { 'zh-CN': '桌面端没有黑色控制台窗口。请到数据目录找 admin-初始密码.txt。', 'en-US': 'Desktop has no terminal window. Check your local data directory for admin-初始密码.txt.' },
      },
    ],
  },
]

// ---------------------------------------------------------------------------
// 数据：新手上路工作流 (双语国际化)
// ---------------------------------------------------------------------------

interface Workflow {
  title: Record<Locale, string>
  desc: Record<Locale, string>
  steps: Array<Record<Locale, string>>
}

const WORKFLOWS: Workflow[] = [
  {
    title: {
      'zh-CN': '工作流 A：拆一本书',
      'en-US': 'Workflow A: Analyze a Book',
    },
    desc: {
      'zh-CN': '把小说拆解成资产——整个生态的起点',
      'en-US': 'Deconstruct a novel into structured assets — the starting point of the ecosystem',
    },
    steps: [
      { 'zh-CN': '系统页 → 模型配置，先配好外部 AI 模型', 'en-US': 'System -> Model Config: configure external AI model first' },
      { 'zh-CN': '分析拆书页点击「选择文件」或拖入 .txt', 'en-US': 'Analysis Workbench: click "Select File" or drop .txt manuscript' },
      { 'zh-CN': '选择 .txt 文件（建议 UTF-8，含标准章节标题）', 'en-US': 'Pick .txt file (UTF-8 recommended, standard chapter headers)' },
      { 'zh-CN': '等待解析完成（耗时视章节数和机器性能而定）', 'en-US': 'Wait for analysis to finish (depends on chapter count and specs)' },
      { 'zh-CN': '查看资产卡 / 章节打分 / 报告三个页签', 'en-US': 'Review Asset Cards, Chapter Scores, and Markdown Reports' },
      { 'zh-CN': '资产已自动存入资产库并支持一键反哺', 'en-US': 'Assets are automatically persisted in Asset Library ready for writing' },
    ],
  },
  {
    title: {
      'zh-CN': '工作流 B：蒸馏一个题材',
      'en-US': 'Workflow B: Distill a Genre',
    },
    desc: {
      'zh-CN': '从多本同题材小说中提炼通用写作规律',
      'en-US': 'Extract invariant writing rules and patterns across novels of the same genre',
    },
    steps: [
      { 'zh-CN': '确认同一题材有≥2本已拆解的书', 'en-US': 'Ensure at least 2 analyzed books exist under the target genre' },
      { 'zh-CN': '高级功能 → 蒸馏页签', 'en-US': 'Navigate to Advanced Features -> Distillation tab' },
      { 'zh-CN': '输入题材名（如 campus-redemption）', 'en-US': 'Enter genre slug (e.g., campus-redemption or litrpg)' },
      { 'zh-CN': '确认"可蒸馏"标识 → 点击「执行蒸馏」', 'en-US': 'Confirm "Ready to Distill" indicator -> Click "Execute Distillation"' },
      { 'zh-CN': '去资产库筛选「蒸馏规则」查看产物', 'en-US': 'Check Asset Library filtered by "Distilled Rule" for results' },
    ],
  },
  {
    title: {
      'zh-CN': '工作流 C：质检全书',
      'en-US': 'Workflow C: Full Book Quality Check',
    },
    desc: {
      'zh-CN': '对完稿小说做出版级质检与四层十二维体检',
      'en-US': 'Perform publication-grade QC and consistency audits on finished drafts',
    },
    steps: [
      { 'zh-CN': '质量检验 → 全书质检页签', 'en-US': 'Navigate to Quality Workbench -> Full Book QC tab' },
      { 'zh-CN': '填写章节目录路径（外部任意目录均可）', 'en-US': 'Specify chapter folder path or pick file (supports arbitrary external paths)' },
      { 'zh-CN': '点击「质检」，等待多维度检测完成', 'en-US': 'Click "Inspect" and wait for multi-pass checks to finish' },
      { 'zh-CN': '查看判定结论和问题列表；总分在「QC 综合」查看', 'en-US': 'Review verdict and issue logs; inspect scores and reports in "QC Overview"' },
    ],
  },
  {
    title: {
      'zh-CN': '工作流 D：辅助写作',
      'en-US': 'Workflow D: Assisted Writing',
    },
    desc: {
      'zh-CN': '参考已拆解的书，生成新内容并闭环排毒',
      'en-US': 'Generate draft chapters guided by analyzed voice cards and audit with anti-slop',
    },
    steps: [
      { 'zh-CN': '系统页 → 模型配置，确认模型可用', 'en-US': 'System -> Model Config: ensure model connection is healthy' },
      { 'zh-CN': '辅助写作 → 写作工坊', 'en-US': 'Navigate to Writing Workbench -> Studio' },
      { 'zh-CN': '选项目、填章节号、选 voice-card', 'en-US': 'Select project, set chapter index, and link reference Voice Card' },
      { 'zh-CN': '在「写作要点」填写需求描述', 'en-US': 'Outline scene beats, character conflict, and emotional goals in Brief' },
      { 'zh-CN': '点击「开始写作」→ 满意后「入库并打分」', 'en-US': 'Click "Start Writing" -> Save to Project & Score when satisfied' },
    ],
  },
]

// ---------------------------------------------------------------------------
// 数据：常见问题 (双语国际化)
// ---------------------------------------------------------------------------

interface FaqItem {
  q: Record<Locale, string>
  a: Record<Locale, string>
}

const FAQS: FaqItem[] = [
  {
    q: {
      'zh-CN': '导入 .txt 后没反应？',
      'en-US': 'Nothing happens after selecting .txt file?',
    },
    a: {
      'zh-CN': '检查三点：① 扩展名是否为 .txt ② 是否为 UTF-8 编码（记事本另存为时选 UTF-8；非 UTF-8 会尝试 GBK 解码）③ 文件是否超过 100MB。',
      'en-US': 'Check 3 items: 1) Extension must be .txt, 2) UTF-8 encoding (GBK fallback supported), 3) File size is within 100MB limit.',
    },
  },
  {
    q: {
      'zh-CN': '程序启动后窗口没出来？',
      'en-US': 'Application window does not appear upon launch?',
    },
    a: {
      'zh-CN': '① 查看任务管理器是否有运行中的进程，首次启动初始化数据较慢请稍候片刻 ② 检查端口 8000-8099 是否被其它服务占用。',
      'en-US': '1) Check Task Manager to confirm process is initializing on first launch, 2) Verify ports 8000-8099 are not blocked.',
    },
  },
  {
    q: {
      'zh-CN': '杀毒软件误报？',
      'en-US': 'Antivirus flags the application as a threat?',
    },
    a: {
      'zh-CN': '纯本地运行的 Python 独立打包常见误报，添加白名单信任即可。程序默认完全离线运行；仅当你主动使用在线模型时，文本才会发送到配置的模型服务商。',
      'en-US': 'Packaged Python binaries occasionally trigger false positives; add to whitelist. The app runs completely offline except when querying user-configured AI models.',
    },
  },
  {
    q: {
      'zh-CN': '如何更新到新版本？',
      'en-US': 'How to update to newer versions?',
    },
    a: {
      'zh-CN': '运行新版安装包重新安装即可（安装到同一目录）。用户数据与数据库保存在安全数据目录中，不受更新影响。',
      'en-US': 'Run the updated installer to the same directory. User data in %LOCALAPPDATA% remains safely untouched.',
    },
  },
  {
    q: {
      'zh-CN': '蒸馏和拆书是什么关系？',
      'en-US': 'What is the relationship between Analysis and Distillation?',
    },
    a: {
      'zh-CN': '拆书是把单本书提炼为资产；蒸馏是把同题材多本书的资产提炼为通用规律。先拆书，后蒸馏。',
      'en-US': 'Analysis extracts assets from a single book; Distillation synthesizes universal rules across multiple books of the same genre. Analyze first, distill second.',
    },
  },
  {
    q: {
      'zh-CN': '资产库里的东西能删除吗？',
      'en-US': 'Can assets in the Asset Library be deleted?',
    },
    a: {
      'zh-CN': '内置官方资产建议保留。自定义生成的资产可随时管理与删除；误删可通过启动自动备份快速恢复。',
      'en-US': 'Official built-in assets should be retained. User-created assets can be pruned or restored from automatic launch backups.',
    },
  },
]

const DATA_FLOW_DIAGRAM: Record<Locale, string> = {
  'zh-CN': `小说 .txt ──▶ 拆书 ──▶ 资产库（11种资产）
                    │
                    ├──▶ 质检报告（QC）
                    │
                    └──▶ 蒸馏 ──▶ 题材规律
                                    │
                                    ▼
                              辅助写作 ──▶ 新内容 ──▶ 质检 ──▶ 闭环`,
  'en-US': `Novel .txt ──▶ Analysis ──▶ Asset Library (11 Asset Kinds)
                      │
                      ├──▶ Quality Check Reports (QC)
                      │
                      └──▶ Distillation ──▶ Genre Rules
                                              │
                                              ▼
                                       Co-Writing ──▶ New Content ──▶ QC ──▶ Closed Loop`,
}

// ---------------------------------------------------------------------------
// 组件：术语表面板
// ---------------------------------------------------------------------------

function GlossaryPanel() {
  const { t, locale } = useI18n()
  const [query, setQuery] = useState('')
  const [catFilter, setCatFilter] = useState<'all' | TermCategory>('all')

  const catOptions: Array<{ key: 'all' | TermCategory; label: string }> = useMemo(() => [
    { key: 'all', label: t('help_cat_all') },
    { key: 'concept', label: t('help_cat_concept') },
    { key: 'asset', label: t('help_cat_asset') },
    { key: 'feature', label: t('help_cat_feature') },
  ], [t])

  const catLabelMap: Record<TermCategory, string> = useMemo(() => ({
    concept: t('help_cat_concept'),
    asset: t('help_cat_asset'),
    feature: t('help_cat_feature'),
  }), [t])

  const filtered = useMemo(() => {
    return GLOSSARY.filter(tItem => {
      const termStr = tItem.term[locale] || tItem.term['zh-CN']
      const defStr = tItem.definition[locale] || tItem.definition['zh-CN']
      const matchQ = !query || termStr.toLowerCase().includes(query.toLowerCase()) || defStr.toLowerCase().includes(query.toLowerCase())
      const matchC = catFilter === 'all' || tItem.category === catFilter
      return matchQ && matchC
    })
  }, [query, catFilter, locale])

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <TextField
          size="small"
          placeholder={t('help_glossary_search')}
          value={query}
          onChange={e => setQuery(e.target.value)}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
          }}
          sx={{ minWidth: 240 }}
        />
        {catOptions.map(opt => (
          <Chip
            key={opt.key}
            label={opt.label}
            clickable
            onClick={() => setCatFilter(opt.key)}
            color={catFilter === opt.key ? 'primary' : 'default'}
            variant={catFilter === opt.key ? 'filled' : 'outlined'}
          />
        ))}
      </Box>
      {filtered.map(item => {
        const termName = item.term[locale] || item.term['zh-CN']
        const defText = item.definition[locale] || item.definition['zh-CN']
        const exText = item.example ? (item.example[locale] || item.example['zh-CN']) : undefined
        return (
          <Card key={termName} sx={{ mb: 2, border: `1px solid ${ink.line}` }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <Typography variant="h6" sx={{ fontFamily: fontStack.serif, color: ink.primary }}>
                  {termName}
                </Typography>
                <Chip
                  label={catLabelMap[item.category]}
                  size="small"
                  sx={{ bgcolor: ink.primarySoft, color: ink.primary }}
                />
                {locale === 'zh-CN' && item.pinyin && (
                  <Typography variant="caption" color="text.secondary">{item.pinyin}</Typography>
                )}
              </Box>
              <Typography variant="body2" sx={{ mb: exText ? 1 : 0, lineHeight: 1.8 }}>
                {defText}
              </Typography>
              {exText && (
                <Paper sx={{ p: 1.5, bgcolor: ink.goldSoft, border: `1px dashed ${ink.gold}` }} elevation={0}>
                  <Typography variant="body2" sx={{ lineHeight: 1.8 }}>
                    <strong>{t('help_glossary_example_prefix')}</strong>{exText}
                  </Typography>
                </Paper>
              )}
            </CardContent>
          </Card>
        )
      })}
      {filtered.length === 0 && (
        <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
          {t('help_glossary_empty')}
        </Typography>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 组件：新手上路面板
// ---------------------------------------------------------------------------

function StartPanel() {
  const { t, locale } = useI18n()

  return (
    <Box>
      <Typography variant="h6" sx={{ fontFamily: fontStack.serif, mb: 2, color: ink.primary }}>
        {t('help_start_eco_title')}
      </Typography>
      <Paper sx={{ p: 3, mb: 4, bgcolor: ink.primarySoft, border: `1px solid ${ink.line}` }} elevation={0}>
        <Typography variant="body2" sx={{ lineHeight: 2.2, fontFamily: fontStack.mono, whiteSpace: 'pre-wrap' }}>
          {DATA_FLOW_DIAGRAM[locale] || DATA_FLOW_DIAGRAM['zh-CN']}
        </Typography>
        <Divider sx={{ my: 2 }} />
        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>
          {t('help_start_eco_summary_1')}
          <strong>{t('help_start_eco_summary_highlight')}</strong>
          {t('help_start_eco_summary_2')}
        </Typography>
      </Paper>

      <Typography variant="h6" sx={{ fontFamily: fontStack.serif, mb: 2, color: ink.primary }}>
        {t('help_start_workflows_title')}
      </Typography>
      {WORKFLOWS.map((w, i) => {
        const titleText = w.title[locale] || w.title['zh-CN']
        const descText = w.desc[locale] || w.desc['zh-CN']
        return (
          <Accordion key={titleText} defaultExpanded={i === 0} sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{titleText}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{descText}</Typography>
              <Stepper orientation="vertical">
                {w.steps.map((s, sIdx) => {
                  const stepText = s[locale] || s['zh-CN']
                  return (
                    <Step key={sIdx} active>
                      <StepLabel><Typography variant="body2">{stepText}</Typography></StepLabel>
                    </Step>
                  )
                })}
              </Stepper>
            </AccordionDetails>
          </Accordion>
        )
      })}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 组件：功能指南面板
// ---------------------------------------------------------------------------

function GuidesPanel({ anchor }: { anchor: HelpAnchor }) {
  const { t, locale } = useI18n()
  const [expanded, setExpanded] = useState<string | null>(anchor || null)

  React.useEffect(() => {
    if (anchor) setExpanded(anchor)
  }, [anchor])

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.8 }}>
        {t('help_guides_subtitle')}
      </Typography>
      {GUIDES.map(g => {
        const guideTitle = g.title[locale] || g.title['zh-CN']
        const guideIntro = g.intro[locale] || g.intro['zh-CN']
        return (
          <Accordion
            key={g.key}
            expanded={expanded === g.key}
            onChange={(_, isExp) => setExpanded(isExp ? g.key : null)}
            sx={{ mb: 1 }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography sx={{ mr: 1.5, fontSize: '1.3em' }}>{g.icon}</Typography>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>{guideTitle}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2, lineHeight: 1.8 }}>
                {guideIntro}
              </Typography>
              <Typography variant="subtitle2" sx={{ mb: 1, color: ink.primary }}>
                {t('help_guides_steps_header')}
              </Typography>
              <Stepper orientation="vertical" sx={{ mb: 2 }}>
                {g.steps.map((s, idx) => {
                  const sTitle = s.title[locale] || s.title['zh-CN']
                  const sDetail = s.detail[locale] || s.detail['zh-CN']
                  return (
                    <Step key={idx} active>
                      <StepLabel>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{sTitle}</Typography>
                      </StepLabel>
                      <StepContent>
                        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>
                          {sDetail}
                        </Typography>
                      </StepContent>
                    </Step>
                  )
                })}
              </Stepper>
              {g.tips.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" sx={{ mb: 1, color: ink.goldDeep }}>
                    {t('help_guides_tips_header')}
                  </Typography>
                  {g.tips.map((tipObj, tIdx) => {
                    const tipText = tipObj[locale] || tipObj['zh-CN']
                    return (
                      <Typography key={tIdx} variant="body2" color="text.secondary" sx={{ mb: 0.5, lineHeight: 1.8 }}>
                        • {tipText}
                      </Typography>
                    )
                  })}
                </Box>
              )}
              {g.faq.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1, color: ink.primary }}>
                    {t('help_guides_faq_header')}
                  </Typography>
                  {g.faq.map((fItem, fIdx) => {
                    const qText = fItem.q[locale] || fItem.q['zh-CN']
                    const aText = fItem.a[locale] || fItem.a['zh-CN']
                    return (
                      <Box key={fIdx} sx={{ mb: 1.5 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          {t('help_guides_q_prefix')}{qText}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>
                          {t('help_guides_a_prefix')}{aText}
                        </Typography>
                      </Box>
                    )
                  })}
                </Box>
              )}
            </AccordionDetails>
          </Accordion>
        )
      })}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 组件：常见问题面板
// ---------------------------------------------------------------------------

function FaqPanel() {
  const { locale } = useI18n()

  return (
    <Box>
      {FAQS.map((f, i) => {
        const qText = f.q[locale] || f.q['zh-CN']
        const aText = f.a[locale] || f.a['zh-CN']
        return (
          <Accordion key={i} sx={{ mb: 1 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>{qText}</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.8 }}>{aText}</Typography>
            </AccordionDetails>
          </Accordion>
        )
      })}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 根导出组件
// ---------------------------------------------------------------------------

export default function HelpWorkbench({ initialTab = 'start', initialAnchor = null }: HelpWorkbenchProps) {
  const { t } = useI18n()
  const [tab, setTab] = useState<HelpSection>(initialTab)

  React.useEffect(() => {
    setTab(initialTab)
  }, [initialTab])

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto', p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ fontFamily: fontStack.serif, mb: 1, color: ink.ink }}>
        {t('help_title')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t('help_subtitle')}
      </Typography>
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 3, borderBottom: `1px solid ${ink.line}` }}
      >
        <Tab value="start" label={t('help_tab_start')} />
        <Tab value="glossary" label={t('help_tab_glossary')} />
        <Tab value="guides" label={t('help_tab_guides')} />
        <Tab value="faq" label={t('help_tab_faq')} />
      </Tabs>
      {tab === 'start' && <StartPanel />}
      {tab === 'glossary' && <GlossaryPanel />}
      {tab === 'guides' && <GuidesPanel anchor={initialAnchor} />}
      {tab === 'faq' && <FaqPanel />}
    </Box>
  )
}
