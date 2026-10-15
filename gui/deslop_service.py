"""去 AI 味检测与诊断服务（Deslop Diagnostic Service）。

纯 Python 标准库实现，严格遵循项目规范（零第三方依赖）。
针对中文网文核心痛点：
1. 假大空与玄虚修辞（Hollow Rhetoric）
2. 同义反复与冗余句式（Tautology）
3. 直陈式情绪宣泄而非具体描写（Direct Emotion Telling）
4. 口癖俗套转折词与模板动作（AI Tics & Connectors）
5. 被动句与「让」字泛滥（Passive & Rang Overuse）
6. 无由排比与连续同构句式（Parallel Structure）
"""

from __future__ import annotations

import re
from typing import Any

# 1. 假大空/玄虚修辞模板
HOLLOW_RHETORIC_PATTERNS = [
    (r"这一刻[，,]?(?:时间|空气|呼吸)?仿佛(?:凝固|停止|静止)了?", "时间凝固模板", "改为描写周围人物动作的戛然而止或具体的微观声响。"),
    (r"天地(?:之间|间)?仿佛只剩(?:下|下了)?", "天地只剩模板", "改为着眼于两人的目光交锋、距离感或周遭真实的背景环境。"),
    (r"命运的齿轮(?:在这一刻|开始|悄然)?转动", "命运齿轮滥用", "网文严重俗套烂梗，建议删除该句，直接推进现实事件。"),
    (r"仿佛跨越了(?:千山万水|几个世纪|漫长的岁月|时光)", "时空跨越虚辞", "虚化时空不如直接描写眼神变迁或身体记忆。"),
    (r"像一道小小的伤口", "伤口比喻模板", "典型 AI 伤感套路，建议具象化为实际的不甘或迟疑。"),
    (r"镀上了一层(?:淡淡的|很薄的)?(?:金|银|月)?光", "镀金镀光模板", "过于程式化的光影描写，可换成更日常的场景反光或略去。"),
    (r"不知为何[，,]?心底(?:忽然|猛然)?涌起一股", "无由情绪涌起", "情绪必须有前置视听刺激触发，勿凭空涌起。"),
    (r"眼底(?:闪过|掠过)(?:一丝|一抹)?(?:复杂的|冰冷的|凌厉的)?(?:神色|光芒|暗芒)?", "眼底复杂神色套路", "网文严重泛滥的套路眼部特写，改为动作、呼吸或微表情描写。"),
    (r"宛如(?:一[只头尊])?断了线的风筝", "断线风筝俗套", "换为实打实的重物坠落受击体感（如后背撞裂青砖、喉头腥甜）。"),
    (r"(?:不可置否|毋庸置疑|显而易见地?)", "说明文论调侵蚀", "小说叙事切忌议论文说教词汇，通过现场事实让读者自行得出结论。"),
]

# 2. 直陈式情绪词（直白喊出来而非演出）
DIRECT_EMOTION_PATTERNS = [
    (r"(?:十分|非常|极其|感到|显得|分外)(?:愤怒|生气|难过|伤心|绝望|悲痛|害怕|恐惧|兴奋|高兴)", "直陈式情绪词", "用生理反应（手抖、后槽牙咬紧、发冷）或即时动作演出情绪。"),
    (r"心中涌起(?:一股|一阵)?无法言说的(?:愤怒|绝望|悲伤|凄凉)", "无法言说情绪", "不要宣告'无法言说'，直接写出说不出来的具体情状。"),
    (r"(?:极度|无比|万分)(?:痛苦|震撼|狂喜|沮丧)", "极端副词堆砌", "削减副词修饰，强化名词与动词的力量感。"),
]

# 3. 同义反复与冗余修辞
TAUTOLOGY_PATTERNS = [
    (r"(?:十分|非常)愤怒[，,]?(?:心中|整个人)?(?:极其|分外)?(?:愤怒|生气)", "愤怒同义反复", "删除前后重复的一处。"),
    (r"寂静无声的(?:安静|死寂)", "寂静同义反复", "精简词语，避免'白色的白雪'式重复。"),
    (r"微微(?:勾起|露出一丝)?(?:淡淡的|微弱的)?笑意", "微小副词双重叠加", "保留'微勾嘴角'即可，避免过度的层层修饰。"),
    (r"深吸一口气[，,]?深呼吸", "深吸气重复", "动作单一化，一次即可。"),
]

# 4. 俗套口癖与转折
CLICHE_PATTERNS = [
    (r"就在这时[，,]?", "就在这时滥用", "非突发转折切勿频繁作为句首，直接叙述新动作。"),
    (r"(?:猛然间|突然之间|骤然间)[，,]?", "突然词频过高", "真正突兀的事发生时不需要大喊'突然'，直接抛出变化。"),
    (r"(?:不由得|忍不住|情不自禁地)", "不由得/忍不住口癖", "削减心理过渡词，直接写主角身体下意识的反应。"),
    (r"倒吸了一口(?:凉气|冷气)", "倒吸凉气俗套", "换为屏息、身形后仰或喉咙发紧等更生动的体感。"),
    (r"瞳孔(?:猛然|剧烈)?收缩", "瞳孔收缩俗套", "避免高频使用此模板，可用眼底暗沉、视线锁定等代替。"),
    (r"嘴角(?:微微)?勾起(?:一抹|一丝)?(?:玩味|戏谑|冰冷|嘲讽|残忍|淡淡)?的(?:笑意|弧度|冷笑)", "嘴角弧度模板", "极度泛滥的脸谱化微表情模板，建议替换为具体的眼神、视线转移或短促台词。"),
    (r"(?:眼中|眼底|眼眸|眸中)(?:闪过|掠过|浮现)(?:了)?(?:一丝|一抹|一缕)?", "眼中闪过套路", "直接写出他当场说的话、做出的决定或具体动作，不要替读者标注情绪。"),
]

# 5. 否定铺垫后接肯定翻转（2026-10-11 新增，对标业界★★★★★级 AI 句式）
#
# 依据：外部成熟实践（GitHub zenstory-ai/oh-story-claudecode 的
# skills/story-deslop/references/banned-words.md，MIT）将「不是A，（而）是B」
# 列为最高毒级句式——它是中文 AI 生成文本最具标志性的判断式结构：
# 先否定一个说法、再抛出"真正的"答案，读起来像议论文而非小说。
# 本项目此前完全未覆盖该句式（行为实测命中 0）。
NEGATION_FLIP_PATTERNS = [
    (r"不是[^。！？；\n]{1,20}[，,](?:而)?是", "不是A而是B翻转", "删掉否定铺垫，直接写 B；让读者自己看出反差，别替他先否一次。"),
    (r"并非[^。！？；\n]{1,20}[，,](?:而)?是", "并非A而是B翻转", "同上：直接陈述，去掉'并非…而是…'的议论文腔。"),
    (r"不再[^。！？；\n]{1,20}[，,]?而是", "不再A而是B翻转", "直接写现在的状态，不必先声明'不再'。"),
]

# 6. 「，带着……」万能状语（2026-10-11 新增）
#
# 依据：同上参考源列为 ★★★★ 毒级"。AI 极爱用「动作，带着某种情绪/气质」
# 补一个抽象状语收尾，这是"告诉而非展示"的典型。
DANGLING_ZHE_PATTERNS = [
    (r"[，,](?:带着|带着着)(?:一丝|一抹|几分|些许|某种|一种)?[^。！？；\n]{1,12}(?:的)?(?:笑意|嘲讽|无奈|决然|坚毅|温柔|冷意|杀意|情绪|意味)", "带着…万能状语", "删掉这个状语留主句，或换成具体动作——'带着'后面挂抽象名词是 AI 的标志性写法。"),
    (r"声音不大[，,](?:却|但)?(?:带着|透着)", "声音不大却带着套路", "直接写声音的实际特征（沙哑、发紧、压得很低）或干脆只写台词。"),
]

# 7. 认知直述（2026-10-11 新增）
#
# 依据：同上参考源列为 ★★★★ 毒级。AI 惯用「他/她知道…」「他明白…」
# 直接把角色的认知结论告诉读者，取代了通过行为让读者自行推断的过程。
TELLING_COGNITION_PATTERNS = [
    (r"(?:他|她|它)(?:心里|心中)?(?:清楚地?|当然|自然|早已)?(?:知道|明白|清楚|意识到|明白过来)[^。！？\n]{0,30}", "认知直述", "用行为展示认知：让他去做某件事、说出某句话，而不是先宣布'他知道'。"),
    (r"(?:他|她)这才(?:明白|意识到|反应过来)", "这才意识到套路", "直接呈现转变后的行动，删掉'这才意识到'这层宣告。"),
    (r"从(?:这一刻|那天|那以后)开始[，,]?", "从此刻开始套路", "章末升华式收束，改为落在具体物件、动作或对话上。"),
]

# 8. 机械列举式排比（2026-10-11 新增）
#
# 「有的…有的…有的…」「一边…一边…一边…」是网文 AI 腔高频结构，
# 与第 6 项同构句检测互补：那边管句首同字，这边管关联词串联。
ENUMERATION_PATTERNS = [
    (r"有的[^。！？；\n]{1,15}[，,](?:还有的|有的)[^。！？；\n]{1,15}[，,]?有的", "有的…有的…排比", "改为错落的具体描写，别用'有的…有的…'这类工整清单。"),
    (r"一边[^。！？；\n]{1,12}?一边[^。！？；\n]{1,12}?一边", "一边…一边…堆砌", "人做不了三个并列动作，拆成先后或只留一个。"),
]

# 9. 密度型检测（2026-10-11 新增）
#
# 设计依据：单个「仿佛」「微微」「了一下」都是正常中文，**单点匹配必然误报**；
# 它们形成 AI 腔的条件是"高密度聚集"。业界成熟做法（参考 zenstory-ai/
# oh-story-claudecode 的 check-ai-patterns.js，MIT；其阈值在 5584 章 qimao
# 长篇 + 3983 篇 heiyan 短篇的真人语料上做过误报率校准）是：统计每千字命中数，
# 越过阈值才报警。本实现移植该**方法论**（密度门控 + 每千字归一），
# 阈值按本项目的文本规模重新设定。
#
# 与前面各组的区别：前面是"命中即报"（单句可判定），这里是"聚集才报"。
DENSITY_RULES = [
    {
        "type": "micro_tic",
        "label": "「了一下」式微动作口癖",
        # 「了+量词」是中文自然构词，但 AI 高频用它给每个动作挂尾巴：
        # "看了一眼""顿了一下""颤了一下"连排时，读感机械。
        "pattern": re.compile(r"了(?:[一两三几半])?[下阵圈道声眼口气会]"),
        "min_hits": 5,
        "per_kilo": 6.0,
        "weight": 6,
        "suggestion": "同一场景里连续给动作挂「了一下」尾巴会显得机械，删掉大部分，只留真正需要强调节拍的那一处。",
    },
    {
        "type": "negation_pair",
        "label": "「没有…也没有…」配对否定",
        "pattern": re.compile(r"(?:没有|没|不)[^，。！？；,!?\n]{1,10}[，,；]\s*[^，。！？；,!?\n]{0,6}?也(?:没有|没|不)"),
        "min_hits": 3,
        "per_kilo": 4.0,
        "weight": 7,
        "suggestion": "连续用「没有A，也没有B」铺排是 AI 的排除法句式，改为直接写实际存在的那一项。",
    },
    {
        "type": "metaphor_density",
        "label": "比喻词密度超标",
        "pattern": re.compile(r"好像|像是|仿佛|宛如|如同|犹如|(?<![不头图画影录摄肖])像(?![头像素])"),
        "min_hits": 7,
        "per_kilo": 3.0,
        "weight": 5,
        "suggestion": "比喻成片出现会变成修辞堆叠。删到必要的数量，其余回到具体白描——不是把「像」换成另一组比喻词。",
    },
    {
        "type": "cliched_modifier",
        "label": "弱化副词/套词密度超标",
        "pattern": re.compile(r"缓缓|微微|轻轻|淡淡|一丝|一抹|些许|几分|隐约"),
        "min_hits": 8,
        "per_kilo": 12.0,
        "weight": 5,
        "suggestion": "「缓缓/微微/轻轻/淡淡」每千字合计控制在 3 个以内；成串出现或每个动作都垫一个时，删掉大部分。",
    },
    {
        "type": "action_list",
        "label": "监控式动作流水账",
        "pattern": re.compile(r"伸手|抬手|探手|拿起|拿过|取出|取过|掏出|摸出|抓起|攥住|握住|捏住|按住|推开|拉开|打开|关上|放下|递给|挑开|掀开|扯开|拧开|倒出|端起|转身|回头|抬头|低头|弯腰|俯身|走到|走向|坐下|站起|看向|看着|盯着|扫过"),
        "min_hits": 5,
        "per_kilo": 8.0,
        "weight": 6,
        "suggestion": "连续堆叠通用动作动词并用逗号串成步骤表，读感像无视角温度的监控记录；合并动作、删掉可推断的步骤。",
    },
    {
        "type": "reasoning_chain",
        "label": "解释链/推理腔",
        "pattern": re.compile(r"这意味着|也就是说|换句话说|真正的问题|问题在于|关键在于|在这种情况下|按照这个逻辑|只有这样"),
        "min_hits": 3,
        "per_kilo": 3.0,
        "weight": 8,
        "suggestion": "小说叙事不需要「这意味着/换句话说」这类论证连接词，读者能从事实自行推断。",
    },
]

# ==============================================================================
# Exoscribe 英文去 AI 味规则表（English Anti-Slop Patterns）
# ==============================================================================

_EN_WORD_RE = re.compile(r"\b[a-zA-Z0-9]+(?:[-'][a-zA-Z0-9]+)*\b")
_EN_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_EN_ADVERB_RE = re.compile(r"\b[a-zA-Z]+ly\b")
_EN_NON_ADVERB_LY = frozenset({
    "early", "daily", "weekly", "monthly", "yearly", "friendly", "lonely",
    "lovely", "holy", "silly", "ugly", "family", "belly", "jelly", "ally",
    "rally", "fly", "rely", "apply", "supply", "butterfly", "italy", "only",
    "likely", "assembly", "monopoly", "bully", "chill", "jolly",
})

# 1. 英文假大空与玄虚比喻模板（LLM Hollow Rhetoric & Clichés）
EN_HOLLOW_RHETORIC_PATTERNS = [
    (
        r"(?i)\btestament\s+to\b",
        "A testament to 虚辞",
        "Classic LLM cliché. Anchor the achievement or consequence in concrete actions.",
    ),
    (
        r"(?i)\b(?:delve|delves|delved|delving)(?:\s+deep)?\s+into\b",
        "Delve into 滥用",
        "Stale AI buzzword. Use explore/investigate or show character actions directly.",
    ),
    (
        r"(?i)\b(?:rich\s+|intricate\s+)?tapestry\s+of\b",
        "Tapestry of 比喻俗套",
        "Overworked metaphorical trope. Ground descriptions in tangible sensory reality.",
    ),
    (
        r"(?i)\bbeacon\s+of\s+(?:hope|light)\b",
        "Beacon of hope 俗套",
        "Melodramatic trope. Show characters inspiring others through deeds.",
    ),
    (
        r"(?i)\bdance\s+of\s+(?:shadows|light|fire|flames)\b",
        "Dance of shadows 模板",
        "Overused poetic flourish. Describe the physical movement of light or shadow directly.",
    ),
    (
        r"(?i)\bsymphony\s+of\s+(?:sounds|destruction|silence|colors|whispers|screams)\b",
        "Symphony of 虚辞",
        "Abstract musical metaphor. Specify real auditory or visual details.",
    ),
    (
        r"(?i)\bwhispers\s+of\s+(?:the\s+)?(?:past|wind|doubt|shadows)\b",
        "Whispers of 虚辞",
        "Vague melodramatic trope. Use concrete memories or sensory cues.",
    ),
    (
        r"(?i)\b(?:etched|seared)\s+into\s+(?:his|her|their|my)?\s*(?:memory|mind|soul)\b",
        "Etched into memory 俗套",
        "Show involuntary physical recall or lasting consequences rather than poetic claims.",
    ),
    (
        r"(?i)\b(?:sent\s+chills?|a\s+shiver)\s+(?:down|ran\s+down)\s+(?:his|her|their|my)?\s*spine\b",
        "Shiver down spine 套路",
        "Stock bodily reaction. Replace with visceral sensations like throat tightness or shallow breath.",
    ),
    (
        r"(?i)\bair\s+was\s+(?:thick|heavy)\s+with\b",
        "Air thick with 抽象气氛",
        "Show characters shifting weight, avoiding eye contact, or room temperature.",
    ),
    (
        r"(?i)\btime\s+(?:seemed\s+to|appeared\s+to)?\s*(?:stand\s+still|freeze|stop)\b",
        "Time stood still 模板",
        "Show hyper-focus on specific micro-actions or sounds rather than stopping time.",
    ),
    (
        r"(?i)\ba\s+palpable\s+sense\s+of\b",
        "Palpable sense of 宣教",
        "Abstract narrator proclamation. Show emotional atmosphere through character reactions.",
    ),
    (
        r"(?i)\bunspoken\s+(?:bond|understanding|agreement)\b",
        "Unspoken understanding 套路",
        "Show the shared nod, exchanged glance, or synchronized motion.",
    ),
]

# 2. 英文感知过滤词（Filter Words - 削弱代入感，隔阂读者与现场）
EN_FILTER_WORDS_PATTERNS = [
    (
        r"(?i)\b(?:he|she|they|I)\s+(?:could\s+(?:hear|see|feel|smell|taste|sense))\b",
        "Filter word (could see/hear/feel)",
        "Remove the perceptual filter: instead of 'He could hear footsteps', write 'Footsteps echoed'.",
    ),
    (
        r"(?i)\b(?:he|she|they|I)\s+(?:watched|noticed|observed)\s+as\b",
        "Filter word (watched as)",
        "Cut 'watched as' and let the action unfold directly before the reader.",
    ),
    (
        r"(?i)\b(?:felt|feeling)\s+a\s+(?:sudden\s+)?(?:wave|surge|pang|rush)\s+of\b",
        "Felt a surge/wave of",
        "Telling emotions. Ground the feeling in physical sensation (heart hammering, stomach dropping).",
    ),
    (
        r"(?i)\b(?:he|she|they|I)\s+(?:decided\s+to|began\s+to|started\s+to)\s+[a-z]+",
        "Indirect action initiation",
        "Strengthen prose by performing the action directly ('decided to run' -> 'ran').",
    ),
]

# 3. 英文否定翻转句式（Negation Flip - LLM 标志性议论文腔调）
EN_NEGATION_FLIP_PATTERNS = [
    (
        r"(?i)\b(?:it\s+was|was)\s+not\s+just\s+[^,.;\n]{1,30},\s*(?:but|it\s+was)\b",
        "Not just X but Y 议论翻转",
        "Cut the negative setup; present the actual state directly.",
    ),
    (
        r"(?i)\bnot\s+because\s+[^,.;\n]{1,30},\s*but\s+because\b",
        "Not because A but because B",
        "Avoid argumentative setup; show motivation through deed.",
    ),
    (
        r"(?i)\bwasn't\s+[^,.;\n]{1,30},\s*(?:but\s+rather|rather)\b",
        "Wasn't X but rather Y",
        "State the reality affirmatively without hedging.",
    ),
]

# 4. 英文对白弱修饰与弱副词堆叠（Weak Dialogue Tags & Modifiers）
EN_ADVERB_PATTERNS = [
    (
        r"(?i)\b(?:said|whispered|shouted|replied|asked|muttered)\s+(?:softly|angrily|coldly|quietly|firmly|nervously|hesitantly|gently|bitterly|excitedly)\b",
        "弱对话标签挂副词",
        "Eliminate the -ly adverb. Convey tone through dialogue content, rhythm, or an action beat.",
    ),
    (
        r"(?i)\b(?:very|extremely|incredibly|utterly|absolutely|completely)\s+(?:cold|hot|angry|scared|happy|sad|dark|bright|silent|quiet)\b",
        "虚弱副词堆砌",
        "Replace weak modifier + weak adjective with a strong single verb/noun/adjective (e.g. 'furious', 'terrified').",
    ),
]

_SENT_SPLIT_RE = re.compile(r"[。！？\n\r]+|[…]{2,}")
# 句内并列分句边界（；/;）——排比同构句常以分号串联，不切开就会整段漏检。
_CLAUSE_SPLIT_RE = re.compile(r"[；;]+")

# 同构句检测：句首“引导字”集合。AI 腔的典型形态是连续多句以同一主语/动词起手
# （他…他…他…），而旧实现要求前两字完全相同（“他看”vs“他坐”即失配），
# 导致最普遍的一类同构句完全漏检。改为「首字相同」判定。
#
# ⚠️ 为什么**不含**「我」「你」（2026-10-11 实测修正）：
# 第一人称叙事里连续以「我」起句是完全正常的写法（"我走进屋子。我看见照片。
# 我想起十年前。"），第二人称同理。把它们计入会直接误伤第一人称作品——
# 而本项目 platform_service.PLATFORMS 里知乎盐言的定位正是
# 「第一人称代入·多重反转」，误报会打在最主流的用户群上。
#
# 第三人称「他/她/它」则不同：叙述者反复点名主语才是 AI 腔特征
# （正常的第三人称叙述会用"他"起首后省略后续主语）。因此只收第三人称代词
# 与少数指示性起手字。
_PARALLEL_LEAD_CHARS = frozenset("他她它")
_PARALLEL_TAIL_LEAD_CHARS = frozenset("像每这那")


def _is_parallel_lead(sentence: str) -> bool:
    """判定句子是否以「可构成同构排比」的字起手。

    仅认人称代词与少数指示性起手字——它们作句首时才具备"连续同构"的机械感。
    例如「他…他…他…」是 AI 腔重灾区；而「风…雨…雷…」这类不同主语起手
    属于正常文学排比，不应误报。
    """
    return bool(sentence) and sentence[0] in (_PARALLEL_LEAD_CHARS | _PARALLEL_TAIL_LEAD_CHARS)


def _merge_overlapping(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把同类型、位置重叠的命中合并为一条。

    背景：``re.finditer`` 对连续重复输入逐位置报告。例如文本里出现
    「一边一边一边…」时，enumeration 正则在每个位置都匹配成功，产出大量
    指向同一现象的条目，把 ``issues[:30]`` 的配额占满，真正的其他问题
    反而被截断看不见。

    合并规则：同 ``type`` 且新条目起点 ≤ 上一条覆盖终点 → 并入上一条
    （扩展其覆盖终点），不新增。不同类型即使位置重叠也各自保留——
    它们描述的是不同性质的问题。

    只在"重叠"时合并，因此正常的、彼此分离的多处命中不受影响。
    """
    if not issues:
        return issues
    # 用**真实匹配长度**判定覆盖范围。
    #
    # 曾用 len(snippet) 当覆盖终点，结果连续重复的短命中无法合并：
    # 「不是冷漠，而是绝望。」×5 里每个匹配长 8 字符、间隔 10 字符，
    # 8 < 10 使相邻判定失败，5 条重复全部保留（2026-10-11 实测发现）。
    # 改用 _match_len 后，相邻命中只要起点落在上一个匹配结束前即合并。
    #
    # 另设「同类型相邻命中间距」兜底：正则匹配通常短于实际语段，
    # 若两条同类型命中之间没有其他类型的命中隔开，也视为同一处聚集。
    out: list[dict[str, Any]] = []
    cover_end: dict[int, int] = {}
    for it in issues:
        merged = False
        for prev in reversed(out):
            if prev["type"] != it["type"]:
                continue
            if it["index"] <= cover_end[id(prev)]:
                cover_end[id(prev)] = max(
                    cover_end[id(prev)], it["index"] + it.get("_match_len", 0)
                )
                merged = True
            break
        if not merged:
            out.append(it)
            cover_end[id(it)] = it["index"] + it.get("_match_len", 0)
    for it in out:
        it.pop("_match_len", None)
    return out


def _locate(text: str, needle: str, start: int) -> int:
    """从 ``start`` 起定位 ``needle``，找不到则回落到全文查找，再不行返回 start。

    用于给 issue 提供**正确**的字符偏移。旧实现直接用 ``text.find(s)``，
    同一句在文中重复出现时索引恒指向首次出现处，前端高亮会跳到错误段落。
    """
    if not needle:
        return start
    idx = text.find(needle, max(0, start))
    if idx >= 0:
        return idx
    idx = text.find(needle)
    return idx if idx >= 0 else start


def _analyze_deslop_en(text: str, en_words: list[str]) -> dict[str, Any]:
    """Exoscribe 国际版英文小说去 AI 味深度诊断引擎。"""
    en_count = len(en_words)
    raw_sents = [s.strip() for s in _EN_SENT_SPLIT_RE.split(text) if s.strip()]
    sentence_count = len(raw_sents)

    issues: list[dict[str, Any]] = []

    # 1. 规则表驱动扫描
    rule_groups = (
        ("hollow_rhetoric", EN_HOLLOW_RHETORIC_PATTERNS, 12),
        ("filter_words", EN_FILTER_WORDS_PATTERNS, 9),
        ("negation_flip", EN_NEGATION_FLIP_PATTERNS, 14),
        ("adverb_tics", EN_ADVERB_PATTERNS, 8),
    )
    for itype, patterns, weight in rule_groups:
        for pat, label, suggestion in patterns:
            for m in re.finditer(pat, text):
                issues.append({
                    "type": itype,
                    "label": label,
                    "snippet": m.group(0),
                    "index": m.start(),
                    "_match_len": m.end() - m.start(),
                    "weight": weight,
                    "suggestion": suggestion,
                })

    issues = _merge_overlapping(issues)

    # 2. -ly 副词密度专项检测
    all_ly = _EN_ADVERB_RE.findall(text)
    adverb_hits = [w for w in all_ly if w.lower() not in _EN_NON_ADVERB_LY]
    adverb_count = len(adverb_hits)
    adverb_density = (adverb_count / max(en_count, 1)) * 100.0
    if en_count >= 30 and adverb_density > 4.0:
        issues.append({
            "type": "adverb_overuse",
            "label": "副词使用超标 (-ly adverbs)",
            "snippet": f"全篇共检测到 {adverb_count} 个副词（占比 {adverb_density:.1f}%）",
            "index": 0,
            "weight": 12,
            "suggestion": "削减 -ly 副词修饰，将弱动词+副词搭配替换为更具力量感的精准动词。",
        })

    # 3. 英文连续相同主语/代词起手检测（Monotonous Sentence Starters）
    lead_words: list[tuple[str, str, int]] = []
    for s in raw_sents:
        wm = _EN_WORD_RE.search(s)
        if wm:
            lead_words.append((wm.group(0).lower(), s, _locate(text, s, 0)))
        else:
            lead_words.append(("", s, 0))

    k = 0
    n_leads = len(lead_words)
    while k < n_leads:
        w = lead_words[k][0]
        if not w or w not in ("he", "she", "they", "it", "the"):
            k += 1
            continue
        nxt_k = k + 1
        while nxt_k < n_leads and lead_words[nxt_k][0] == w:
            nxt_k += 1
        chain_len = nxt_k - k
        if chain_len >= 3:
            snippets = [lead_words[idx][1] for idx in range(k, nxt_k)]
            issues.append({
                "type": "parallelism",
                "label": f"连续主语起手 ('{w.capitalize()}' 句式单调)",
                "snippet": " | ".join(snippets[:4]) + ("..." if chain_len > 4 else ""),
                "index": lead_words[k][2],
                "weight": 14,
                "suggestion": f"连续多句均以 '{w}' 开头，节奏机械。倒装从句、使用分词短语或以环境/动作细节起句以打破单调。",
            })
        k = nxt_k if chain_len >= 3 else k + 1

    # 综合计分 (0-100)
    penalty_sum = sum(it["weight"] for it in issues)
    # 按英文页/篇幅缩放：以 250 词为基准
    scale_factor = 250.0 / max(en_count, 80)
    scaled_penalty = penalty_sum * scale_factor
    ai_score = min(100.0, max(0.0, round(scaled_penalty * 1.8, 1)))

    if ai_score < 18.0:
        verdict = "NATURAL"
        verdict_cn = "自然流畅（英文地道，无明显 AI 痕迹）"
    elif ai_score < 40.0:
        verdict = "MILD"
        verdict_cn = "轻度模式化（个别英文模板与修辞冗余）"
    elif ai_score < 65.0:
        verdict = "NOTICEABLE"
        verdict_cn = "AI 腔明显（存在高频 LLM 俗套虚辞与感知过滤词）"
    else:
        verdict = "SEVERE"
        verdict_cn = "重度 AI 味（需深度重塑去油）"

    suggestions = []
    if any(it["type"] == "hollow_rhetoric" for it in issues):
        suggestions.append("警惕 'testament to'、'tapestry of' 等玄虚修辞，将描写锚定在具象触觉与现实动作。")
    if any(it["type"] == "filter_words" for it in issues):
        suggestions.append("清除 'could see/feel'、'watched as' 等感知过滤词，直接呈现场景动作（Show, don't tell）。")
    if any(it["type"] in ("adverb_tics", "adverb_overuse") for it in issues):
        suggestions.append("削减对话与动作中的 -ly 副词，选用更有画面感与表现力的动词原词。")
    if any(it["type"] == "parallelism" for it in issues):
        suggestions.append("丰富句式开头与长短句节奏，避免连续多句以同一代词机械铺叙。")

    return {
        "ai_score": ai_score,
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "stats": {
            "word_count": en_count,
            "sentence_count": sentence_count,
            "issues_count": len(issues),
            "rang_density": 0.0,
            "adverb_density": round(adverb_density, 1),
        },
        "issues": issues[:30],
        "suggestions": suggestions,
    }


def analyze_deslop(text: str, lang: str = "auto") -> dict[str, Any]:
    """对输入文本进行全维度去 AI 味深度诊断（支持中文网文与 Exoscribe 英文国际版）。"""
    if not isinstance(text, str):
        text = str(text or "")

    normalized_lang = (lang or "auto").strip().lower()
    cn_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    en_words = _EN_WORD_RE.findall(text)
    en_count = len(en_words)

    # 英文分支判定：显式指定 en，或 auto 模式下无中文且有英文词汇
    if normalized_lang == "en" or (normalized_lang == "auto" and cn_count == 0 and en_count > 0):
        return _analyze_deslop_en(text, en_words)

    if cn_count == 0:
        return {
            "ai_score": 0.0,
            "verdict": "NATURAL",
            "verdict_cn": "未检测到有效中文文本",
            "stats": {"word_count": 0, "sentence_count": 0, "issues_count": 0, "rang_density": 0.0},
            "issues": [],
            "suggestions": [],
        }

    raw_len = len(text)

    # 切句
    raw_sents = [s.strip() for s in _SENT_SPLIT_RE.split(text) if s.strip()]
    sentence_count = len(raw_sents)

    issues: list[dict[str, Any]] = []

    # 1-8. 规则表驱动扫描。
    # weight 依据业界毒级分档（参考 zenstory-ai/oh-story-claudecode 的
    # banned-words.md）：★★★★★ 句式给最高权重，★★★ 及以下递减。
    rule_groups = (
        ("hollow_rhetoric", HOLLOW_RHETORIC_PATTERNS, 12),
        ("direct_emotion", DIRECT_EMOTION_PATTERNS, 8),
        ("tautology", TAUTOLOGY_PATTERNS, 10),
        ("cliche", CLICHE_PATTERNS, 5),
        # 以下四组 2026-10-11 新增，补齐行为实测出的覆盖缺口
        ("negation_flip", NEGATION_FLIP_PATTERNS, 15),      # ★★★★★ 最毒
        ("dangling_zhe", DANGLING_ZHE_PATTERNS, 11),        # ★★★★
        ("telling_cognition", TELLING_COGNITION_PATTERNS, 11),  # ★★★★
        ("enumeration", ENUMERATION_PATTERNS, 8),           # ★★★
    )
    for itype, patterns, weight in rule_groups:
        for pat, label, suggestion in patterns:
            for m in re.finditer(pat, text):
                issues.append({
                    "type": itype,
                    "label": label,
                    "snippet": m.group(0),
                    "index": m.start(),
                    # 真实匹配长度（snippet 可能被后续合并改写，不能拿它当覆盖范围）
                    "_match_len": m.end() - m.start(),
                    "weight": weight,
                    "suggestion": suggestion,
                })

    # 4.5 重叠命中合并（2026-10-11）。
    #
    # 正则 finditer 在连续重复的输入上会逐位置各报一次：例如「一边」×10000
    # 会让 enumeration 规则产出上万条**同一现象**的条目，把 issues 列表刷满
    # （实测 30 条上限全被同一段占据，真实问题被挤出视野）。
    # 同构句那边已用贪心链解决同类问题，这里对规则表统一做一次合并：
    # 同 type 且新命中起点落在上一条的覆盖范围内 → 并入上一条，不新增条目。
    issues = _merge_overlapping(issues)

    # 5. 「让」字密度专项
    rang_count = text.count("让")
    rang_density = (rang_count / (cn_count / 1000.0)) if cn_count > 0 else 0.0
    if rang_density > 8.0:
        issues.append({
            "type": "rang_overuse",
            "label": "「让」字密度超标",
            "snippet": f"全篇共出现 {rang_count} 个「让」字（千字密度 {rang_density:.1f}）",
            "index": 0,
            "weight": 15,
            "suggestion": "过度使用'让…产生…'被动句型是翻译腔与 AI 味的重灾区。将其重构为主谓主动句。",
        })

    # 6. 无由排比与连续同构句式检查
    #
    # 实现要点（旧实现的三处缺陷，2026-10-11 修复）：
    #   a) 旧版要求前两字完全相同 → "他看见/他听见/他感到" 这类最典型的 AI 腔同构
    #      全部漏检。改为「首字相同」判定，并保留 2 字全同也视为同构。
    #   b) 旧版固定 3 句滑动窗口 → 4 句同构会报 2 条重叠问题、5 句报 3 条。
    #      改为**贪心最长链**：一次吞掉整条同构链，链内不再重复计数。
    #   c) 旧版 index 用 text.find(s1) → 同一句在文中重复出现时，索引恒指向首次
    #      出现处，前端高亮会跳到错误段落。改为按切句时的累计偏移定位。
    #
    # 切句：除句末标点外，分号串联的并列分句也要切开——排比句常写成
    # "他看见风雪；他看见长剑；他看见破碎的梦。"，不切分号就整段是一句。
    clauses: list[tuple[str, int]] = []
    for s in raw_sents:
        parts = _CLAUSE_SPLIT_RE.split(s)
        if len(parts) == 1:
            clauses.append((s, _locate(text, s, clauses[-1][1] if clauses else 0)))
            continue
        base = _locate(text, s, clauses[-1][1] if clauses else 0)
        cursor = base
        for p in parts:
            p_st = p.strip()
            if not p_st:
                continue
            off = _locate(text, p_st, cursor)
            clauses.append((p_st, off))
            cursor = off + len(p_st)

    i = 0
    n_clause = len(clauses)
    while i < n_clause:
        head = clauses[i][0]
        if len(head) < 4 or not _is_parallel_lead(head):
            i += 1
            continue
        # 向后贪心延伸同构链
        j = i + 1
        while j < n_clause:
            nxt = clauses[j][0]
            if len(nxt) >= 4 and _is_parallel_lead(nxt) and nxt[0] == head[0]:
                j += 1
            else:
                break
        chain_len = j - i
        if chain_len >= 3:
            segs = [c[0] for c in clauses[i:j]]
            issues.append({
                "type": "parallelism",
                "label": "机械连续同构句",
                "snippet": "；".join(segs[:6]) + ("…" if chain_len > 6 else ""),
                "index": clauses[i][1],
                "weight": 14,
                "suggestion": "连续相同句式开头显得过于工整死板，打破对仗，融合为更有节奏的错落叙述。",
            })
        i = j if chain_len >= 3 else i + 1

    # 9. 密度型检测：单个词是正常中文，聚集才构成 AI 腔。
    # 门槛取「绝对命中数」与「每千字密度」双重判定——短文本靠前者防误报，
    # 长文本靠后者防漏报（长文里 5 次「了一下」完全正常）。
    kilo = max(cn_count / 1000.0, 0.3)   # 与计分口径一致的千字基数下限
    for rule in DENSITY_RULES:
        hits = rule["pattern"].findall(text)
        n_hit = len(hits)
        if n_hit < rule["min_hits"]:
            continue
        density = n_hit / kilo
        if density <= rule["per_kilo"]:
            continue
        issues.append({
            "type": rule["type"],
            "label": rule["label"],
            "snippet": f"共 {n_hit} 处（千字密度 {density:.1f}，阈值 {rule['per_kilo']}）",
            "index": 0,
            "weight": rule["weight"],
            "suggestion": rule["suggestion"],
        })

    # 综合计分 (0-100，越低越健康纯正，100 极度油腻严重 AI 味)
    # 基础分 = 惩罚分归一化
    penalty_sum = sum(it["weight"] for it in issues)
    # 按字数缩放：千字惩罚加权
    scale_factor = 1000.0 / max(cn_count, 300)
    scaled_penalty = penalty_sum * scale_factor
    ai_score = min(100.0, max(0.0, round(scaled_penalty * 1.8, 1)))

    if ai_score < 18.0:
        verdict = "NATURAL"
        verdict_cn = "自然流畅（无明显 AI 味）"
    elif ai_score < 40.0:
        verdict = "MILD"
        verdict_cn = "轻度模式化（个别俗套句式）"
    elif ai_score < 65.0:
        verdict = "NOTICEABLE"
        verdict_cn = "AI 腔明显（存在高频模板与直陈宣泄）"
    else:
        verdict = "SEVERE"
        verdict_cn = "重度 AI 味（需深度重塑润色）"

    # 生成全局改写建议
    general_suggestions = []
    if any(it["type"] == "hollow_rhetoric" for it in issues):
        general_suggestions.append("警惕'这一刻仿佛凝固'等玄虚修辞，网文需要的是落地的动作与环境反馈。")
    if any(it["type"] == "direct_emotion" for it in issues):
        general_suggestions.append("秉持'Show, don't tell'原则，用呼吸急促、眼神闪烁等具体动作代替'十分难过'。")
    if rang_density > 6.0:
        general_suggestions.append("大量减少'让'字被动句，将视角转回角色的直接动作。")
    if any(it["type"] == "cliche" for it in issues):
        general_suggestions.append("清理'就在这时'、'突然'等俗套连接词，突兀感靠叙述节奏自发带出。")

    return {
        "ai_score": ai_score,
        "verdict": verdict,
        "verdict_cn": verdict_cn,
        "stats": {
            "word_count": cn_count,
            "sentence_count": sentence_count,
            "issues_count": len(issues),
            "rang_density": round(rang_density, 1),
        },
        "issues": issues[:30],  # 最多返回前 30 项
        "suggestions": general_suggestions,
    }
