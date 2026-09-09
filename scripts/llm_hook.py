#!/usr/bin/env python3
"""
LLM 因果合理性二次判定 Hook — 纯标准库，零第三方依赖

职责（阶段④）：对 `logic_check.check_logic` 第一层纯算法检测出的「疑似逻辑
矛盾」做 LLM 二次判定，判断其是「真矛盾」还是「闪回/倒叙/伏笔/世界观合理
设定」造成的误报，过滤误报以降低 D2 维度的误报率。

接口契约（与 ARCH_llm_hook_causality.md 严格一致）：

    make_causality_hook(task="consistency_check", texts=None)
        -> Optional[Callable[[list], list]]

    - 返回 None = 不启用（`llm_client.any_model_configured()` 为 False，L1 降级）。
    - 返回 callable = 启用。该 callable 语义：
        入参：第一层纯算法产出的完整 issue 列表 list[dict]
        出参：过滤后的 issue 列表 list[dict]
      任何 LLM 异常/解析失败都在 hook 内部静默吞掉，绝不让异常冒泡。

    texts 参数（关键）：传入 {章号:int -> 章节原文:str} 时，hook 会在 prompt 中
    附带「相关章节原文片段」，让 LLM 读到「回忆/梦/倒叙」等语境词，这是识别
    闪回/倒叙/伏笔误报的核心依据。**不传 texts 则 LLM 只拿到一句 detail，
    无法判断闪回**，因此 qc.py 编排层必须传入真实章节原文。

三层降级（硬约束）：
    L1 构造期：`any_model_configured()` False → `make_causality_hook()` 返回 None
    L2 调用期：`llm_client.chat` 抛 `LLMError` / 网络异常 → 返回原 issue 列表
    L3 解析期：JSON 解析失败 / verdict 缺失 → 该条默认 `real_contradiction`（保留）

保守原则：LLM 只负责降误报，绝不因解析失败/不确定而漏掉真矛盾。
"""
import json
import re
from typing import Callable, List, Optional

# 仅 import 项目内 `llm_client`（本身是纯标准库 urllib 实现，不违反铁律三）
import llm_client


# 系统提示（固定：判定角色 + 只输出 JSON 的输出契约）
SYSTEM_PROMPT = (
    "你是一名网文逻辑审校员。任务：判断给定的「疑似逻辑矛盾」是否是真矛盾，"
    "还是闪回/倒叙/伏笔/世界观合理设定的误报。\n"
    "只输出 JSON，不要输出任何多余文字。"
)

# 送入 LLM 二次判定的候选 issue 类型（四类算法天然易误报类型）
CANDIDATE_TYPES = {
    "number_contradiction",
    "timeline_contradiction",
    "state_contradiction",
    "appellation_contradiction",
}

# 候选数量上限：超出按 severity 优先截断，防超长书 token 爆炸
MAX_CANDIDATES = 50

# 每条候选带上的「相关章节原文片段」长度上限（字/段）
SNIPPET_MAX_CHARS = 800

# 判定类任务参数（确定性判断，控制成本）
JUDGE_TASK = "consistency_check"
JUDGE_MAX_TOKENS = 512
JUDGE_TEMPERATURE = 0.0

# severity 优先级：critical > high > medium > low（候选截断排序用）
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# 关键字回退词表（解析失败时的兜底判定）
_FALSE_POSITIVE_KEYWORDS = [
    "闪回", "倒叙", "伏笔", "回忆", "合理", "设定", "误报", "不矛盾", "非矛盾",
    "梦境", "幻觉", "想象", "假设", "错觉", "误解",
]
_REAL_KEYWORDS = [
    "确实矛盾", "硬伤", "矛盾", "冲突", "不一致", "前后矛盾", "确为矛盾",
]

# 提取「首个 {...}」子串的正则（宽容解析第一步）
_BRACE_RE = re.compile(r"\{.*\}", re.S)


def make_causality_hook(task: str = JUDGE_TASK, texts: dict = None) -> Optional[Callable[[list], list]]:
    """构造因果合理性二次判定 hook。

    Args:
        task: 传给 `llm_client.chat` 的任务名（路由模型），默认 consistency_check。
        texts: {章号:int -> 章节原文:str}。传入时 hook 会在 prompt 附带「相关章节
               原文片段」，让 LLM 识别闪回/倒叙/伏笔（核心依据）。None 时仅喂 detail。

    Returns:
        Optional[Callable[[list], list]]:
            - None：无模型配置（L1 降级），调用方应走纯算法、不启用 LLM。
            - callable：因果判定 hook。入参第一层 issue 列表，出参过滤后列表；
              任何异常内部静默捕获、返回原列表。
    """
    try:
        if not llm_client.any_model_configured():
            return None
    except Exception:
        # any_model_configured 本身异常（配置文件损坏等）也按「无模型」降级
        return None

    texts_map = dict(texts) if texts else {}

    # 可追溯统计（供 qc.py 写入 meta.llm_hook）
    stats = {
        "candidates": 0,
        "filtered": 0,
        "retained": 0,
        "undetermined": 0,
        "cost": 0.0,
    }

    def hook(issues: list) -> list:
        """因果二次判定入口。异常绝不冒泡，任何失败返回原列表。"""
        result = _judge_candidates(list(issues), task=task, texts=texts_map, stats=stats)
        # 刷新可追溯元信息（供 qc.py 读取做 meta.llm_hook）
        hook.llm_hook_meta = {"enabled": True, **stats}
        return result

    # 初始元信息（未运行时）
    hook.llm_hook_meta = {"enabled": True, **stats}

    return hook


def make_causality_hook_with_texts(task: str = JUDGE_TASK, texts: dict = None):
    """构造带章节原文的 hook（`make_causality_hook` 的语义别名）。

    保留此函数名以兼容旧调用（qc.py 已直接使用 make_causality_hook(texts=...)
    传原文，二者等价）。与 make_causality_hook 的区别仅在于显式表达「带原文」语义。
    """
    return make_causality_hook(task=task, texts=texts)


# ---------------------------------------------------------------------------
# 候选筛选
# ---------------------------------------------------------------------------

def _is_candidate(issue: dict) -> bool:
    """判断 issue 是否属于需要 LLM 二次判定的候选类型。"""
    if not isinstance(issue, dict):
        return False
    return issue.get("type") in CANDIDATE_TYPES


def _select_candidates(issues: list, max_candidates: int = MAX_CANDIDATES) -> List[int]:
    """从 issue 列表中筛出候选的下标，按 severity 优先 + 原顺序截断。

    Returns:
        List[int]: 被选中的 issue 下标列表（保持稳定、可追踪）。
    """
    indexed = []
    for i, issue in enumerate(issues):
        if _is_candidate(issue):
            sev = issue.get("severity", "low")
            indexed.append((i, _SEVERITY_ORDER.get(sev, 3)))
    # 按 severity 优先级排序（同优先级保持原下标顺序 = 稳定）
    indexed.sort(key=lambda t: (t[1], t[0]))
    return [i for i, _ in indexed[:max_candidates]]


# ---------------------------------------------------------------------------
# 原文片段抽取
# ---------------------------------------------------------------------------

def _chapter_number(chapter) -> int:
    """issue.chapter 可能是 int 或 'ChN' 字符串，统一归一为 int。"""
    if isinstance(chapter, int):
        return chapter
    if isinstance(chapter, str):
        m = re.search(r"(\d+)", chapter)
        if m:
            return int(m.group(1))
    return 0


def _extract_entities(detail: str) -> List[str]:
    """从 issue.detail 中抽取「实体名」，用于定位原文片段的关键词。

    抽取规则：匹配「实体「XXX」」或「角色「XXX」」中的引号内名称。
    """
    names = []
    for m in re.finditer(r"(?:实体|角色)「([^」]+)」", detail):
        name = m.group(1).strip()
        if name and name not in names:
            names.append(name)
    return names


def _build_snippets(issue: dict, texts: dict) -> str:
    """为单条候选 issue 构造 user 上下文片段。

    取 issue 涉及章节（chapter 字段）中、含关键实体/关键词的上下文窗口，
    每段 ≤ SNIPPET_MAX_CHARS 字。texts 为空时退化为空串（仍保留 detail）。

    Returns:
        str: 供拼入 prompt 的原文片段文本（可含空行分隔的多段）。
    """
    chapter = _chapter_number(issue.get("chapter"))
    if not texts or chapter not in texts:
        return ""
    text = texts[chapter]
    if not text:
        return ""

    names = _extract_entities(issue.get("detail", ""))
    snippets = []

    # 若有关键实体名，优先取含实体名的上下文窗口
    if names:
        for name in names:
            idx = text.find(name)
            if idx < 0:
                continue
            start = max(0, idx - SNIPPET_MAX_CHARS // 2)
            end = min(len(text), idx + SNIPPET_MAX_CHARS // 2)
            snippet = text[start:end].strip()
            if snippet:
                snippets.append(snippet)
    # 否则（或无命中）回退：取该章开头片段
    if not snippets:
        snippets.append(text[:SNIPPET_MAX_CHARS].strip())

    return "\n---\n".join(s for s in snippets if s)


def _build_user_prompt(issue: dict, texts: dict) -> str:
    """构造单条候选的 user 提示：detail + 原文片段。"""
    detail = issue.get("detail", "")
    snippet = _build_snippets(issue, texts)
    parts = [f"疑似矛盾：{detail}"]
    if snippet:
        parts.append(f"相关章节原文片段：\n{snippet}")
    parts.append(
        "请判断这是真矛盾还是误报，并只输出 JSON："
        '{"verdict": "real_contradiction" 或 "false_positive", '
        '"reason": "一句中文理由", "category": "flashback/foreshadowing/setting/narration_switch/real/unknown"}'
    )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 结构化返回解析（防格式漂移）
# ---------------------------------------------------------------------------

def _parse_verdict(text: str) -> str:
    """把 LLM 返回文本解析为 verdict（'false_positive' / 'real_contradiction'）。

    防格式漂移双保险：
      1. 直接 `json.loads`；
      2. 失败则提取首个 `{...}` 子串再 `json.loads`；
      3. 仍失败则关键字回退；
      4. 最终无法判定 → 默认 'real_contradiction'（保守，宁保留不漏杀）。
    """
    if not isinstance(text, str) or not text.strip():
        return "real_contradiction"

    verdict = _try_json_parse(text)
    if verdict is not None:
        return verdict

    verdict = _keyword_fallback(text)
    if verdict is not None:
        return verdict

    return "real_contradiction"


def _try_json_parse(text: str) -> Optional[str]:
    """尝试 JSON 解析，返回规范化的 verdict；失败返回 None。"""
    # 第一层：直接解析
    obj = _loads_soft(text)
    # 第二层：提取首个 {...} 再解析
    if obj is None:
        m = _BRACE_RE.search(text)
        if m:
            obj = _loads_soft(m.group(0))
    if not isinstance(obj, dict):
        return None

    v = obj.get("verdict")
    if isinstance(v, str):
        v = v.strip().lower()
        if v in ("false_positive", "false positive", "误报", "否"):
            return "false_positive"
        if v in ("real_contradiction", "real", "contradiction", "真矛盾", "矛盾", "是"):
            return "real_contradiction"
    # 无 verdict 字段，但可能有等价字段
    for key in ("is_contradiction", "is_conflict", "contradiction"):
        val = obj.get(key)
        if isinstance(val, bool):
            return "real_contradiction" if val else "false_positive"
    return None


def _loads_soft(text: str):
    """json.loads 的软封装：任何异常返回 None（不冒泡）。"""
    try:
        return json.loads(text)
    except Exception:
        return None


def _keyword_fallback(text: str) -> Optional[str]:
    """关键字回退：命中误报词 → false_positive；命中真矛盾词 → real_contradiction。

    优先检查误报词，再检查真矛盾词（避免「矛盾」同时命中两边时误判）。
    Returns:
        Optional[str]: 命中返回 verdict，未命中返回 None。
    """
    for kw in _FALSE_POSITIVE_KEYWORDS:
        if kw in text:
            return "false_positive"
    for kw in _REAL_KEYWORDS:
        if kw in text:
            return "real_contradiction"
    return None


# ---------------------------------------------------------------------------
# 判定 + 过滤
# ---------------------------------------------------------------------------

def _judge_candidates(issues: list, task: str = JUDGE_TASK,
                      texts: dict = None, stats: dict = None) -> list:
    """对候选 issue 逐条喂 LLM，过滤误报，返回过滤后的 issue 列表。

    三层降级均在此兜底：
      - 无候选 / 无模型 → 原样返回；
      - LLM 调用抛异常 → 该条保守保留，继续后续（不冒泡）；
      - 单条解析失败 → 默认 real_contradiction（保留该条）。

    Args:
        issues: 第一层完整 issue 列表。
        task: LLM 任务路由名。
        texts: {章号:int -> 章节原文:str}。传入时 prompt 附带原文片段；None 仅 detail。
        stats: 可选统计 dict（含 candidates/filtered/retained/undetermined/cost），
               用于 meta 追溯，逐条判定时刷新。

    Returns:
        list: 过滤后的 issue 列表（任何失败场景均返回原列表或仅删误报，绝不漏杀）。
    """
    if not issues:
        return issues

    # 无模型配置（运行时二次确认，兜住构造期后模型被删的边界）
    try:
        if not llm_client.any_model_configured():
            return issues
    except Exception:
        return issues

    candidate_indices = _select_candidates(issues)
    if not candidate_indices:
        return issues

    texts_map = dict(texts) if texts else {}

    total_candidates = len(candidate_indices)
    dropped = set()
    cost_total = 0.0
    undetermined = 0  # 调用失败 / 解析失败（默认 real_contradiction 保守保留）的数量

    for idx in candidate_indices:
        issue = issues[idx]
        prompt = _build_user_prompt(issue, texts_map)
        try:
            resp = llm_client.chat(
                user=prompt,
                system=SYSTEM_PROMPT,
                task=task,
                max_tokens=JUDGE_MAX_TOKENS,
                temperature=JUDGE_TEMPERATURE,
                json_mode=True,
            )
        except Exception:
            # 单条调用失败（L2 降级）：保守保留该条，计入 undetermined
            undetermined += 1
            continue
        text = resp.get("text", "") if isinstance(resp, dict) else ""
        cost_total += float(resp.get("cost", 0) or 0) if isinstance(resp, dict) else 0.0

        # 解析：若 LLM 返回空文本/不可解析（走默认 real_contradiction），
        # 视为「未确定」而非「真矛盾」，计入 undetermined（保守保留）。
        verdict, is_explicit = _parse_verdict_explicit(text)
        if not is_explicit:
            undetermined += 1
            continue  # 保守保留该条（默认 real_contradiction），不计入 filtered
        if verdict == "false_positive":
            dropped.add(idx)

    # 刷新可追溯统计
    if stats is not None:
        stats["candidates"] = total_candidates
        stats["filtered"] = len(dropped)
        stats["retained"] = total_candidates - len(dropped)
        stats["undetermined"] = undetermined
        stats["cost"] = round(cost_total, 4)

    if not dropped:
        return issues

    return [it for i, it in enumerate(issues) if i not in dropped]


def _parse_verdict_explicit(text: str) -> tuple:
    """解析 verdict，并区分「明确判定」与「回退默认值」。

    与 _parse_verdict 的差异：返回 (verdict, is_explicit) 二元组，其中
    is_explicit 为 True 表示通过 JSON/关键字明确判定了 verdict；为 False 表示
    走了「默认 real_contradiction」的保守回退（即无法判定，应计入 undetermined）。

    Returns:
        tuple: (verdict_str, is_explicit_bool)。
    """
    if not isinstance(text, str) or not text.strip():
        return "real_contradiction", False

    verdict = _try_json_parse(text)
    if verdict is not None:
        return verdict, True

    verdict = _keyword_fallback(text)
    if verdict is not None:
        return verdict, True

    return "real_contradiction", False
