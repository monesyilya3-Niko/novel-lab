#!/usr/bin/env python3
"""
QC 统一质检入口 — 四层十二维整合（纯标准库，零第三方依赖）

整合并复用既有 6 个脚本的核心函数（零改动既有脚本），把散落各处的质检
统一为「四层十二维」模型，产出 QCReport，支持 JSON / Markdown 双输出。

四层十二维映射：
  L1 剧情层（剧情连贯性）
      D1 剧情连贯   → book_quality.check_plot_continuity
      D2 逻辑合理   → logic_check.check_logic
      D3 结构完整   → chapter_check.check_structure
  L2 人物层（角色一致性）
      D4 人物弧线   → consistency.check_voices
      D5 设定一致   → setting_check.check_setting
  L3 技法层（写作手法）
      D6 手法运用   → consistency.score_text 五维（声线/情绪/叙述/禁忌/意象）
      D7 节奏       → chapter_check.check_paragraph_rhythm
      D8 爽点       → chapter_check.check_hook
  L4 语言层（表达质量）
      D9  句子重复  → book_quality.check_duplicate_sentences（跨章句）
                      + book_quality.check_intra_chapter_repeats（章内碎片）
      D10 章节重复  → book_quality.check_duplicate_chapters + check_duplicate_paragraphs
      D11 AI味      → book_quality.check_ai_flavor + chapter_check.check_ai_tics
      D12 禁用词    → compliance.scan_asset + build_ngram_index

判定统一规则（复用 book_quality）：
  critical > 0        → FAIL
  high >= 5           → FAIL
  high > 0            → WARN
  否则                → PASS

阈值单一事实来源 = chapter_check.resolve_thresholds（默认 75/60）。

用法:
  python qc.py <chapter_dir> [--voice vc.json] [--genre-pack gp.json]
              [--asset a.json] [--book book.txt] [--novel-dir dir] [--json]

报告落盘: reports/qc/<书名>-qc.json + .md
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# 复用既有脚本（导入即用，零改动）
import book_quality
import chapter_check
import chapter_loader
import compliance
import consistency
import logic_check
import llm_hook as llm_hook_mod
import setting_check


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    """单个维度得分。"""
    key: str                      # 维度唯一标识，如 "plot_continuity"
    label: str                    # 维度中文名，如 "剧情连贯"
    layer: str                    # 所属层，如 "L1"
    score: float = 0.0            # 0-100
    weight: float = 0.0           # 该维度在层内/全书的权重
    issues: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class LayerScore:
    """单层得分（聚合该层所有维度）。"""
    layer: str
    label: str
    score: float = 0.0            # 0-100（层内加权）
    dimensions: list = field(default_factory=list)  # list[DimensionScore]


@dataclass
class QCReport:
    """全书 QC 报告。"""
    book_title: str = ""
    total_score: float = 0.0
    verdict: str = "PASS"         # PASS / WARN / FAIL
    layers: list = field(default_factory=list)   # list[LayerScore]
    issues: list = field(default_factory=list)   # 汇总 issue 列表
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 章节加载
# ---------------------------------------------------------------------------

def _load_texts(chapter_dir: str) -> dict:
    """加载章节文本为 {章号:int -> 文本:str}。

    2026-09-16: 委托 `chapter_loader.load_chapter_texts()`——与 book_quality /
    logic_check 共用同一套发现规则（排除备份/构建目录，同章号冲突抛
    `ChapterLoadError`，它是 `ValueError` 子类，故调用方按 ValueError 处理即可）。
    """
    return chapter_loader.load_chapter_texts(chapter_dir)


def _load_json(path) -> dict:
    """安全加载 JSON，失败返回 None。"""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _full_text(texts: dict) -> str:
    """把多章文本按章号顺序拼成全文（供单文本维度打分）。"""
    return "\n".join(texts[ch] for ch in sorted(texts.keys()))


# ---------------------------------------------------------------------------
# 维度打分辅助
# ---------------------------------------------------------------------------

def _severity_to_deduct(issues: list) -> float:
    """根据 issue 严重度计算扣分（用于把「问题数」折算为维度得分）。

    扣分权重：critical 20 / high 10 / medium 5 / low 2，单维扣满 100 封顶。
    """
    weight_map = {"critical": 20, "high": 10, "medium": 5, "low": 2}
    deduct = sum(weight_map.get(it.get("severity", "low"), 2) for it in issues)
    return min(deduct, 100.0)


def _score_from_issues(issues: list, max_deduct: float = 100.0) -> float:
    """问题数 → 得分（100 - 扣分，下限 0）。"""
    return round(max(0.0, max_deduct - _severity_to_deduct(issues)), 1)


def _wrap_issues(issues: list, chapter_field: str = "chapter") -> list:
    """把既有脚本的 issue dict 归一为统一结构（保证有 chapter 字段）。"""
    out = []
    for it in issues or []:
        if not isinstance(it, dict):
            continue
        d = dict(it)
        # book_quality 的跨章 issue 用 "chapters" 字段，兼容为单 chapter
        if "chapter" not in d and "chapters" in d:
            chs = d.get("chapters", [])
            d["chapter"] = chs[0] if chs else 0
        d.setdefault("chapter", 0)
        d.setdefault("severity", "low")
        d.setdefault("type", "unknown")
        d.setdefault("detail", "")
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# 十二维实现
# ---------------------------------------------------------------------------

def _dim_plot_continuity(texts: dict) -> DimensionScore:
    """D1 剧情连贯 → book_quality.check_plot_continuity。"""
    issues = _wrap_issues(book_quality.check_plot_continuity(texts))
    return DimensionScore(
        key="plot_continuity", label="剧情连贯", layer="L1",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues, raw={"source": "book_quality.check_plot_continuity"})


def _dim_logic(texts: dict, entities: dict, llm_hook=None) -> DimensionScore:
    """D2 逻辑合理 → logic_check.check_logic。

    llm_hook: 可选因果二次判定 callable（None 时纯算法，行为与改造前一致）。
    """
    issues = _wrap_issues(logic_check.check_logic(texts, entities, llm_hook))
    return DimensionScore(
        key="logic", label="逻辑合理", layer="L1",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues, raw={"source": "logic_check.check_logic"})


def _dim_structure(texts: dict) -> DimensionScore:
    """D3 结构完整 → chapter_check.check_structure（全书均值）。"""
    scores = []
    raw_chapters = {}
    for ch in sorted(texts.keys()):
        s, _detail = chapter_check.check_structure(texts[ch])
        scores.append(s)
        raw_chapters[ch] = s
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    # check_structure 满分 8，归一为百分制
    score = round(avg / 8 * 100, 1)
    issues = []
    for ch, s in raw_chapters.items():
        if s < 4:
            issues.append({"type": "structure_incomplete", "severity": "medium",
                           "chapter": ch, "detail": f"Ch{ch} 结构完整度 {s}/8 偏低"})
    return DimensionScore(
        key="structure", label="结构完整", layer="L1",
        score=score, weight=1.0, issues=issues,
        raw={"source": "chapter_check.check_structure", "per_chapter": raw_chapters})


def _detail_is_meaningful_issue(detail: str) -> bool:
    """判断 check_voices / score_text 明细是否应记入 issues。

    满分成功日志（如「命中 5/5 → 7.0/7」「体感词 → 20.0/20」）**不**入 issues，
    否则满分维度会堆出假 low。仅当 → 分数低于满分时记为问题。
    无 → 的明细不记（与既有口径一致）。
    """
    d = detail.strip()
    if "→" not in d:
        return False
    m = re.search(r"→\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)", d)
    if m:
        got, full = float(m.group(1)), float(m.group(2))
        return got + 1e-9 < full
    # 无明确 n/m 分数形态：保守视为问题（保留召回）
    return True


def _dim_character_arc(texts: dict, voice_card: dict) -> DimensionScore:
    """D4 人物弧线 → consistency.check_voices（声线执行度）。

    2026-09-16 修复：声线卡存在但 `dialogue.character_voices` 为空列表时，
    `check_voices` 返回 0 分（"本章无角色出场，无法检查声线"），使本维度被
    一张**不含本书角色**的通用卡直接打到 0。现与「无 voice-card」分支保持一致，
    按「无法评估」跳过（记 100 并在 raw 中标注 skipped），避免空卡污染总分。
    """
    if not voice_card:
        return DimensionScore(key="character_arc", label="人物弧线", layer="L2",
                              score=100.0, weight=1.0, issues=[],
                              raw={"source": "consistency.check_voices", "skipped": "无 voice-card"})
    voices = voice_card.get("dialogue", {}).get("character_voices", []) or []
    if not voices:
        return DimensionScore(
            key="character_arc", label="人物弧线", layer="L2",
            score=100.0, weight=1.0, issues=[],
            raw={"source": "consistency.check_voices",
                 "skipped": "声线卡无角色（character_voices 为空）"})
    full = _full_text(texts)
    score, details = consistency.check_voices(full, voices)
    # check_voices 满分 35，归一为百分制
    score100 = round(score / 35 * 100, 1)
    issues = [{"type": "character_arc", "severity": "low", "chapter": 0,
               "detail": d.strip()} for d in details if _detail_is_meaningful_issue(d)]
    return DimensionScore(
        key="character_arc", label="人物弧线", layer="L2",
        score=score100, weight=1.0, issues=issues,
        raw={"source": "consistency.check_voices", "raw_score": score, "details": details})


def _dim_setting(texts: dict, entities: dict) -> DimensionScore:
    """D5 设定一致 → setting_check.check_setting。"""
    issues = _wrap_issues(setting_check.check_setting(texts, entities))
    return DimensionScore(
        key="setting", label="设定一致", layer="L2",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues, raw={"source": "setting_check.check_setting"})


def _dim_craft(texts: dict, voice_card: dict) -> DimensionScore:
    """D6 手法运用 → consistency.score_text 五维（声线/情绪/叙述/禁忌/意象）。

    2026-09-16 修复：`score_text` 的五维满分合计 100（声线 35 / 情绪 20 /
    叙述 15 / 禁忌 20 / 意象 10）。当声线卡不含角色时，35 分的「角色声线」
    子项恒为 0，会把本维度**凭空压到 65 分**。现改为按可评估子项
    （情绪 20 + 叙述 15 + 禁忌 20 + 意象 10 = 65）重归一，并在 raw 中标注。
    """
    if not voice_card:
        return DimensionScore(key="craft", label="手法运用", layer="L3",
                              score=100.0, weight=1.0, issues=[],
                              raw={"source": "consistency.score_text", "skipped": "无 voice-card"})
    full = _full_text(texts)
    total, details, raw = consistency.score_text(voice_card, full, label="全书")
    voices = voice_card.get("dialogue", {}).get("character_voices", []) or []
    if not voices:
        evaluable_max = 65  # 情绪20 + 叙述15 + 禁忌20 + 意象10
        evaluable = (raw.get("emotion", 0) + raw.get("narration", 0)
                     + raw.get("banned", 0) + raw.get("imagery", 0))
        total = round(evaluable / evaluable_max * 100, 1)
        raw = dict(raw, renormalized="声线卡无角色，按可评估子项 65 分制重归一")
    issues = [{"type": "craft", "severity": "low", "chapter": 0,
               "detail": d.strip()} for d in details if _detail_is_meaningful_issue(d)]
    return DimensionScore(
        key="craft", label="手法运用", layer="L3",
        score=round(total, 1), weight=1.0, issues=issues,
        raw={"source": "consistency.score_text", "dims": raw, "details": details})


def _dim_rhythm(texts: dict) -> DimensionScore:
    """D7 节奏 → chapter_check.check_paragraph_rhythm（全书均值）。"""
    scores = []
    raw_chapters = {}
    for ch in sorted(texts.keys()):
        s, _detail = chapter_check.check_paragraph_rhythm(texts[ch])
        scores.append(s)
        raw_chapters[ch] = s
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    score = round(avg / 8 * 100, 1)  # 满分 8 → 百分制
    issues = []
    for ch, s in raw_chapters.items():
        if s < 4:
            issues.append({"type": "rhythm_poor", "severity": "low",
                           "chapter": ch, "detail": f"Ch{ch} 段落节奏 {s}/8 偏低"})
    return DimensionScore(
        key="rhythm", label="节奏", layer="L3",
        score=score, weight=1.0, issues=issues,
        raw={"source": "chapter_check.check_paragraph_rhythm", "per_chapter": raw_chapters})


def _dim_hook(texts: dict) -> DimensionScore:
    """D8 爽点 → chapter_check.check_hook（全书均值）。"""
    scores = []
    raw_chapters = {}
    for ch in sorted(texts.keys()):
        s, _detail = chapter_check.check_hook(texts[ch])
        scores.append(s)
        raw_chapters[ch] = s
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    score = round(avg / 12 * 100, 1)  # 满分 12 → 百分制
    issues = []
    for ch, s in raw_chapters.items():
        if s < 6:
            issues.append({"type": "hook_weak", "severity": "low",
                           "chapter": ch, "detail": f"Ch{ch} 章末钩子 {s}/12 偏弱"})
    return DimensionScore(
        key="hook", label="爽点", layer="L3",
        score=score, weight=1.0, issues=issues,
        raw={"source": "chapter_check.check_hook", "per_chapter": raw_chapters})


def _dim_sentence_dup(texts: dict) -> DimensionScore:
    """D9 句子重复 → book_quality.check_duplicate_sentences（跨章句）
                       + book_quality.check_intra_chapter_repeats（章内碎片）。

    2026-09-18（第三轮 Task 3.2）：本维度此前只消费跨章句检测，导致
    `check_intra_chapter_repeats`（第二轮新增，按章内重复句占比定档）无人消费——
    同一份稿子 `novel 质检` 会因「章内 46% 重复」报 WARN，而 `novel qc` 的 D9
    与总分完全不受影响，两个命令结论相反。现把两个**句子级**检测器并列消费：
    章内碎片是「句子重复」最严重的形态，语义同族。

    严重度沿用检测器给出的值（章内占比 ≥25% → high、0.10–0.25 → medium、
    <0.10 → low，含检测器自身的最小样本保护），扣分仍走 `_severity_to_deduct`
    权重表（本任务未改）。`raw` 分别给出两个来源的 issue 计数，便于追溯是
    跨章还是章内重复拉低了分数；D10「章节重复」保持整章/整段粒度不变。
    """
    cross = _wrap_issues(book_quality.check_duplicate_sentences(texts))
    intra = _wrap_issues(book_quality.check_intra_chapter_repeats(texts))
    issues = cross + intra
    return DimensionScore(
        key="sentence_dup", label="句子重复", layer="L4",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues,
        raw={"source": ("book_quality.check_duplicate_sentences"
                        " + book_quality.check_intra_chapter_repeats"),
             "cross_chapter": len(cross),
             "intra_chapter": len(intra)})


def _dim_chapter_dup(texts: dict) -> DimensionScore:
    """D10 章节重复 → book_quality.check_duplicate_chapters + check_duplicate_paragraphs。"""
    issues = _wrap_issues(book_quality.check_duplicate_chapters(texts))
    issues += _wrap_issues(book_quality.check_duplicate_paragraphs(texts))
    return DimensionScore(
        key="chapter_dup", label="章节重复", layer="L4",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues, raw={"source": "book_quality.check_duplicate_chapters+paragraphs"})


def _dim_ai_flavor(texts: dict) -> DimensionScore:
    """D11 AI味 → book_quality.check_ai_flavor + chapter_check.check_ai_tics。"""
    issues = _wrap_issues(book_quality.check_ai_flavor(texts))
    # 逐章 check_ai_tics（满分 4，低分即扣分信号）
    for ch in sorted(texts.keys()):
        s, _detail = chapter_check.check_ai_tics(texts[ch])
        if s < 4:
            issues.append({"type": "ai_tics", "severity": "low", "chapter": ch,
                           "detail": f"Ch{ch} AI味 {s}/4（{_detail}）"})
    return DimensionScore(
        key="ai_flavor", label="AI味", layer="L4",
        score=_score_from_issues(issues), weight=1.0,
        issues=issues, raw={"source": "book_quality.check_ai_flavor + chapter_check.check_ai_tics"})


def _dim_banned(texts: dict, asset: dict, book_path: str) -> DimensionScore:
    """D12 禁用词 → compliance.scan_asset + build_ngram_index（版权合规）。"""
    if not asset:
        return DimensionScore(key="banned", label="禁用词", layer="L4",
                              score=100.0, weight=1.0, issues=[],
                              raw={"source": "compliance.scan_asset", "skipped": "无 asset"})
    issues = []
    score = 100.0
    if book_path:
        try:
            book_text = Path(book_path).read_text(encoding="utf-8")
            ngram = compliance.build_ngram_index(book_text)
            errors, warns = compliance.scan_asset(asset, ngram)
            for e in errors:
                issues.append({"type": "compliance_error", "severity": "critical",
                               "chapter": 0, "detail": e})
            for w in warns:
                issues.append({"type": "compliance_warn", "severity": "medium",
                               "chapter": 0, "detail": w})
            score = _score_from_issues(issues)
        except Exception as e:
            issues.append({"type": "compliance_error", "severity": "medium",
                           "chapter": 0, "detail": f"合规扫描异常: {e}"})
            score = _score_from_issues(issues)
    else:
        raw = {"source": "compliance.scan_asset", "skipped": "无 book（原文）"}
        return DimensionScore(key="banned", label="禁用词", layer="L4",
                              score=100.0, weight=1.0, issues=[], raw=raw)
    return DimensionScore(
        key="banned", label="禁用词", layer="L4",
        score=score, weight=1.0, issues=issues,
        raw={"source": "compliance.scan_asset"})


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

_LAYER_DEFS = [
    ("L1", "剧情层", "剧情连贯性"),
    ("L2", "人物层", "角色一致性"),
    ("L3", "技法层", "写作手法"),
    ("L4", "语言层", "表达质量"),
]


def run_qc(chapter_dir: str, *, voice_card_path: str = None, genre_pack_path: str = None,
           asset_path: str = None, book_path: str = None, novel_dir: str = None,
           llm_hook=None, enable_llm_hook: bool = False) -> QCReport:
    """统一 QC 编排入口。

    Args:
        chapter_dir: 章节目录或单章 txt（必填）。
        voice_card_path: voice-card JSON 路径（可选，用于 D4/D6）。
        genre_pack_path: 题材包 JSON 路径（可选，用于阈值解析）。
        asset_path: 资产 JSON 路径（可选，用于 D12 版权合规）。
        book_path: 原文 TXT 路径（可选，用于 D12 版权合规 ngram 索引）。
        novel_dir: novel-writing 项目目录（可选，用于定位 entities.json）。
        llm_hook: 可选因果二次判定 callable（由 llm_hook_mod.make_causality_hook
                  构造，None 时纯算法，与改造前完全一致）。此参数保留以兼容调用方
                  显式传入外部构造的 hook。
        enable_llm_hook: 布尔开关。为 True 时，run_qc 会在加载完章节原文后，
                  内部调用 llm_hook_mod.make_causality_hook(texts=texts) 构造 hook，
                  从而让 LLM 二次判定真正拿到「相关章节原文片段」（识别闪回/倒叙/
                  伏笔的核心依据）。若同时显式传入 llm_hook，则优先使用 llm_hook。

    Returns:
        QCReport: 完整报告。

    Raises:
        ValueError: 未找到章节文件，或章节加载冲突
            （`chapter_loader.ChapterLoadError` 是 ValueError 子类）。
            不吞异常、不返回伪造的空报告，由服务层记录错误。
    """
    texts = _load_texts(chapter_dir)
    if not texts:
        raise ValueError(f"未找到章节文件: {chapter_dir}")

    # 确定实体表（优先 novel_dir，其次 chapter_dir 自动探测）
    entities = None
    if novel_dir:
        entities = logic_check.load_entities(Path(novel_dir))
    if not entities:
        # 复用 book_quality 的自动探测：chapter_dir 上两级 settings/entities.json
        entities = _auto_detect_entities(Path(chapter_dir))

    # 构造因果判定 hook：必须在此（texts 加载之后）构造，才能把真实章节原文
    # 传给 hook。无模型配置时 make_causality_hook 返回 None，静默降级为纯算法。
    if llm_hook is None and enable_llm_hook:
        llm_hook = llm_hook_mod.make_causality_hook(texts=texts)

    voice_card = _load_json(voice_card_path)
    genre_pack = _load_json(genre_pack_path)
    asset = _load_json(asset_path)

    # 书名（优先从 state.json 或 voice-card meta）
    book_title = _resolve_book_title(novel_dir, voice_card, chapter_dir)

    # 十二维
    dims = [
        _dim_plot_continuity(texts),
        _dim_logic(texts, entities, llm_hook),
        _dim_structure(texts),
        _dim_character_arc(texts, voice_card),
        _dim_setting(texts, entities),
        _dim_craft(texts, voice_card),
        _dim_rhythm(texts),
        _dim_hook(texts),
        _dim_sentence_dup(texts),
        _dim_chapter_dup(texts),
        _dim_ai_flavor(texts),
        _dim_banned(texts, asset, book_path),
    ]

    # 按层聚合（层内维度等权平均）
    layers = []
    for layer_key, layer_label, _desc in _LAYER_DEFS:
        layer_dims = [d for d in dims if d.layer == layer_key]
        if layer_dims:
            layer_score = round(sum(d.score for d in layer_dims) / len(layer_dims), 1)
        else:
            layer_score = 0.0
        layers.append(LayerScore(
            layer=layer_key, label=layer_label, score=layer_score,
            dimensions=layer_dims))

    # 总分：四层等权平均
    total_score = round(sum(l.score for l in layers) / len(layers), 1) if layers else 0.0

    # 汇总所有 issue
    all_issues = []
    for d in dims:
        all_issues.extend(d.issues)

    # 判定（复用 book_quality 统一规则：critical>0→FAIL, high>=5→FAIL, high>0→WARN, else PASS）
    verdict = _judge(all_issues)

    # 阈值信息（单一事实来源 = chapter_check.resolve_thresholds）
    pass_line, warn_line = chapter_check.resolve_thresholds(genre_pack)

    meta = {
        "total_chapters": len(texts),
        "total_issues": len(all_issues),
        "pass_line": pass_line,
        "warn_line": warn_line,
        "threshold_source": "chapter_check.resolve_thresholds",
        "voice_card": voice_card_path,
        "genre_pack": genre_pack_path,
        "asset": asset_path,
        "book": book_path,
        "novel_dir": novel_dir,
        "severity_count": _severity_count(all_issues),
        "llm_hook": llm_hook.llm_hook_meta if (
            llm_hook is not None and hasattr(llm_hook, "llm_hook_meta")
        ) else {"enabled": llm_hook is not None},
        # 2026-09-17（第二轮 Task B / 报告 P2-1）：汇总 D2（逻辑合理）与
        # D5（设定一致）的检测覆盖率——「0 问题」与「没检查」必须可区分。
        # 纯新增键，不参与任何维度打分与 verdict 判定。
        "coverage": {
            "logic": logic_check.logic_coverage(texts, entities),
            "setting": setting_check.setting_coverage(texts, entities),
        },
    }

    return QCReport(
        book_title=book_title, total_score=total_score, verdict=verdict,
        layers=layers, issues=all_issues, meta=meta)


def _auto_detect_entities(chapter_path: Path) -> dict:
    """复刻 book_quality 的实体表自动探测逻辑。"""
    bases = []
    if chapter_path.is_dir():
        bases = [chapter_path, chapter_path.parent]
    else:
        bases = [chapter_path.parent, chapter_path.parent.parent]
    for base in bases:
        candidate = base / "settings" / "entities.json"
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def _resolve_book_title(novel_dir, voice_card, chapter_dir) -> str:
    """解析书名：state.json.name > voice-card.meta.name > 目录名。"""
    if novel_dir:
        state = Path(novel_dir) / "state.json"
        if state.exists():
            try:
                s = json.loads(state.read_text(encoding="utf-8"))
                if s.get("name"):
                    return s["name"]
            except Exception:
                pass
    if voice_card:
        meta = voice_card.get("meta", {})
        if meta.get("name"):
            return meta["name"]
    # 目录名兜底
    p = Path(chapter_dir)
    return p.stem if p.is_file() else p.name


def _severity_count(issues: list) -> dict:
    c = {}
    for it in issues:
        sev = it.get("severity", "low")
        c[sev] = c.get(sev, 0) + 1
    return c


def _judge(issues: list) -> str:
    """统一判定规则（复用 book_quality）。"""
    sev = _severity_count(issues)
    critical = sev.get("critical", 0)
    high = sev.get("high", 0)
    if critical > 0:
        return "FAIL"
    if high >= 5:
        return "FAIL"
    if high > 0:
        return "WARN"
    return "PASS"


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------

def _report_to_dict(report: QCReport) -> dict:
    """QCReport → 可 JSON 序列化的 dict。"""
    return {
        "book_title": report.book_title,
        "total_score": report.total_score,
        "verdict": report.verdict,
        "layers": [
            {
                "layer": l.layer, "label": l.label, "score": l.score,
                "dimensions": [asdict(d) for d in l.dimensions],
            } for l in report.layers
        ],
        "issues": report.issues,
        "meta": report.meta,
    }


def to_json(report: QCReport) -> str:
    """QCReport → JSON 字符串（ensure_ascii=False, indent=2）。"""
    return json.dumps(_report_to_dict(report), ensure_ascii=False, indent=2)


def to_markdown(report: QCReport) -> str:
    """QCReport → Markdown 报告（标题/总分/verdict/四层十二维表格/问题清单）。"""
    lines = []
    lines.append(f"# {report.book_title or '未命名'} QC 质检报告")
    lines.append("")
    lines.append(f"**总分**: {report.total_score}/100  **判定**: {report.verdict}")
    lines.append("")
    m = report.meta
    lines.append(f"- 章节数: {m.get('total_chapters', 0)}")
    lines.append(f"- 问题数: {m.get('total_issues', 0)}")
    lines.append(f"- 阈值: PASS≥{m.get('pass_line', 75)} / WARN≥{m.get('warn_line', 60)}")
    sev = m.get("severity_count", {})
    if sev:
        lines.append("- 严重度分布: " + " / ".join(
            f"{k} {v}" for k, v in sorted(sev.items(), key=lambda kv: ["critical", "high", "medium", "low"].index(kv[0]) if kv[0] in ["critical", "high", "medium", "low"] else 9)))
    lines.append("")
    lines.append("## 四层十二维")
    lines.append("")
    lines.append("| 层 | 维度 | 得分 | 问题数 |")
    lines.append("| --- | --- | --- | --- |")
    for l in report.layers:
        for d in l.dimensions:
            lines.append(f"| {l.label}({l.layer}) | {d.label} | {d.score} | {len(d.issues)} |")
    lines.append("")
    lines.append("## 层得分")
    lines.append("")
    lines.append("| 层 | 得分 |")
    lines.append("| --- | --- |")
    for l in report.layers:
        lines.append(f"| {l.label}({l.layer}) | {l.score} |")
    lines.append("")
    lines.append("## 问题清单")
    lines.append("")
    if not report.issues:
        lines.append("无问题。")
    else:
        sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
        for it in report.issues:
            icon = sev_icon.get(it.get("severity"), "⚪")
            ch = it.get("chapter", 0)
            lines.append(f"- {icon} [{it.get('severity', 'low')}] Ch{ch}: {it.get('detail', '')}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="QC 统一质检入口（四层十二维）")
    ap.add_argument("chapter_dir", help="章节目录或单章 txt")
    ap.add_argument("--voice", help="voice-card 路径")
    ap.add_argument("--genre-pack", help="题材包路径")
    ap.add_argument("--asset", help="资产 JSON 路径（版权合规）")
    ap.add_argument("--book", help="原文 TXT 路径（版权合规 ngram 索引）")
    ap.add_argument("--novel-dir", help="novel-writing 项目目录（定位 entities.json）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非 Markdown")
    ap.add_argument("--no-save", action="store_true", help="不落盘，仅打印到 stdout")
    ap.add_argument("--llm-hook", action="store_true",
                    help="启用 LLM 因果合理性二次判定（无模型时自动降级为纯算法）")
    args = ap.parse_args()

    report = run_qc(
        args.chapter_dir,
        voice_card_path=args.voice,
        genre_pack_path=args.genre_pack,
        asset_path=args.asset,
        book_path=args.book,
        novel_dir=args.novel_dir,
        enable_llm_hook=args.llm_hook,
    )

    # 落盘 reports/qc/<书名>-qc.json + .md
    if not args.no_save:
        out_dir = ROOT / "reports" / "qc"
        out_dir.mkdir(parents=True, exist_ok=True)
        title = report.book_title or "book"
        json_path = out_dir / f"{title}-qc.json"
        md_path = out_dir / f"{title}-qc.md"
        json_path.write_text(to_json(report), encoding="utf-8")
        md_path.write_text(to_markdown(report), encoding="utf-8")

    # stdout 输出
    if args.json:
        print(to_json(report))
    else:
        print(to_markdown(report))
        if not args.no_save:
            print(f"\n报告已落盘: reports/qc/{report.book_title or 'book'}-qc.{{json,md}}")

    sys.exit(0 if report.verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
