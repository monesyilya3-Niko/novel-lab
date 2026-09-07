# -*- coding: utf-8 -*-
"""蒸馏层二期 · 语义检索/RAG 桥接（零第三方依赖）。

用「倒排索引 + 词项重叠打分（BM25 简化版）」近似语义检索，把四类蒸馏资产
（voice-card / craft-card / structure-obs / commercial-obs）建成可检索索引，
支持按意图字符串召回最相关的蒸馏片段，供 ``inject.build_prompt`` 追加
「针对性注入」段。

设计约束（来自 docs/system_design_v2.md）：
    * 仅用 Python 标准库，import 白名单严格限定；
    * 原始资产只读，不改写；
    * 检索返回 ``HitEntry``（asset_id/dimension/score/snippet），score 降序、
      同分按 asset_id 升序，top_k=5，snippet 截断约 200 字符。

打分公式（BM25 简化）：
    score(q, d) = Σ_{t∈q∩d} idf(t) * tf(t,d) * (k1+1) / (tf(t,d) + k1)
    idf(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )
    N = 文档总数，k1 = 1.5
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# ---------------------------------------------------------------------------
# 常量（统一收敛在此处）
# ---------------------------------------------------------------------------

# 检索返回的最大条数。
TOP_K: int = 5
# snippet 截断长度（字符）。
SNIPPET_LEN: int = 200
# BM25 k1 参数。
BM25_K1: float = 1.5

# 字符 n-gram 最大长度（1/2/3-gram 混合）。
NGRAM_MAX_N: int = 3
# BM25 与向量余弦的融合权重（BM25 占比，向量占比为 1-α）。
FUSION_ALPHA: float = 0.5
# 参与向量的最小 gram 长度（默认 1，即保留 unigram）。
MIN_NGRAM_GRAM_LEN: int = 1
# 融合分下限：低于此值视为噪声命中（如弱 bigram 子串重叠产生的近零分），
# 归零过滤，避免把 ~0.001 的伪相关注入下游 prompt。实测：无关 bigram 噪声
# 在 0.0012 量级，单字真实意图（如「钩」）在 0.0087 量级，中间约 7 倍断层，
# 0.005 能同时做到「滤掉噪声」且「不误杀单字意图」。
MIN_FUSION_SCORE: float = 0.005

# 单字符 n-gram（unigram）停用字：排除无实义高频功能字 + 常见虚词，
# 避免无关查询与文档在单字层产生伪余弦重叠、破坏「无关→空列表」语义。
# 只作用于 n==1 的 gram；n>=2 的多字 gram 不受影响（语义由组合承载）。
_UNIGRAM_STOPCHARS: frozenset = frozenset(
    "的一了是我不在人有这那他么就都而及与或和也很把被让给要为说个们去来到着看子词存有没当于之其些时候又再才却只可是从"
)
# 单字 gram 额外排除的 ASCII 字符（字母/标点/连接符/数字），避免 asset_id 的
# `-`/`_` 与书名拼音（qingning/sangshi/chireng）字母在单字层产生噪声。
_UNIGRAM_STOPASCII: frozenset = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "-_ ,.;:()[]{}/\\|@#$%^&*+=~`'\"0123456789"
)
# 单字 gram 的文档频率停止比：某单字在 ≥80% 文档中出现即视为无判别力噪声（等价于
# 向量层的 idf/停用词），在检索时从查询向量中过滤。只作用于 n==1 的 gram。
UNIGRAM_DF_STOP_RATIO: float = 0.8
# 单字 gram 停止的最小文档频率：小语料（文档数 < 该值）时 df 无统计意义，不做停止，
# 避免 2~3 篇文档的语料中所有单字都被误判为「普遍噪声」而牺牲近义召回。
UNIGRAM_DF_STOP_MIN: int = 3

# 分词正则：匹配字母数字 + 中日韩字符（连续串作为一个词项）。
_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+")

# 意图映射表：查询词项命中关键词时，为对应维度文档加权（提升召回）。
# 首版只挂高频领域词（钩子/悬念/爽点/铺垫/伏笔）→ 对应维度。
# 结构：{关键词: {维度: 额外权重词项列表}}，命中关键词时把额外词项注入查询，
# 使其能召回对应维度的文档（额外词项会完整进入打分，用于提升对应维度召回权重）。
INTENT_MAP: Dict[str, Dict[str, List[str]]] = {
    "钩子": {"structure-obs": ["钩子", "hook"], "craft-card": ["钩子"]},
    "hook": {"structure-obs": ["钩子", "hook"], "craft-card": ["钩子"]},
    "悬念": {"craft-card": ["悬念"], "structure-obs": ["钩子", "悬念"]},
    "悬疑": {"craft-card": ["悬念"], "structure-obs": ["悬念", "钩子"]},
    "反转": {"craft-card": ["反转", "悬念"], "structure-obs": ["反转", "悬念"]},
    "爽点": {"commercial-obs": ["爽点", "payoff", "卡点"]},
    "payoff": {"commercial-obs": ["爽点", "payoff", "卡点"]},
    "铺垫": {"commercial-obs": ["铺垫", "buildup"], "craft-card": ["铺垫"]},
    "伏笔": {"craft-card": ["伏笔", "foreshadow"], "structure-obs": ["伏笔"]},
    "foreshadow": {"craft-card": ["伏笔", "foreshadow"], "structure-obs": ["伏笔"]},
}

# 维度优先级（用于同分排序时的稳定性兜底，正常按 asset_id 升序）。
_DIMENSION_ORDER: Dict[str, int] = {
    "voice-card": 0,
    "craft-card": 1,
    "structure-obs": 2,
    "commercial-obs": 3,
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class DocEntry:
    """检索索引中的单篇文档（对应一条蒸馏资产）。

    Attributes:
        asset_id: 稳定 id（如 ``<genre>-<dimension>-distilled``）。
        dimension: 所属维度。
        asset_dict: 原始 distilled dict（取 snippet 用）。
        terms: 该文档词项频次（``collections.Counter``）。
        snippet: 预生成的约 200 字符摘要。
    """

    asset_id: str = ""
    dimension: str = ""
    asset_dict: Dict[str, Any] = dc_field(default_factory=dict)
    terms: Counter = dc_field(default_factory=Counter)
    snippet: str = ""
    ngrams: Counter = dc_field(default_factory=Counter)
    corpus: str = ""


@dataclass
class HitEntry:
    """一条检索命中结果。

    Attributes:
        asset_id: 稳定 id。
        dimension: 维度。
        score: BM25 打分（越大越相关）。
        snippet: 约 200 字符摘要。
    """

    asset_id: str = ""
    dimension: str = ""
    score: float = 0.0
    snippet: str = ""


@dataclass
class Index:
    """倒排索引。

    Attributes:
        inverted: 词项 -> 文档下标列表。
        doc_freq: 词项 -> 文档频率（df）。
        docs: 文档列表（DocEntry）。
        idf_cache: 词项 -> idf 缓存。
    """

    inverted: Dict[str, List[int]] = dc_field(default_factory=dict)
    doc_freq: Dict[str, int] = dc_field(default_factory=dict)
    docs: List[DocEntry] = dc_field(default_factory=list)
    idf_cache: Dict[str, float] = dc_field(default_factory=dict)
    norms: List[float] = dc_field(default_factory=list)


# ---------------------------------------------------------------------------
# 分词与规范化
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """把文本切分为词项列表（字母数字 + 中日韩字符连续串）。"""
    if not text:
        return []
    return _TOKEN_RE.findall(str(text).lower())


def _build_snippet(asset_dict: Dict[str, Any]) -> str:
    """从资产 dict 生成约 200 字符的可读摘要。

    优先取 distilled 的 ``rules``（field:value）文本；无规则时退化为「扁平化全文」，
    覆盖原始资产（craft-card 技法名等）。截断到 ``SNIPPET_LEN`` 字符。
    """
    parts: List[str] = []
    rules = asset_dict.get("rules")
    if isinstance(rules, list):
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            field = rule.get("field", "")
            value = rule.get("value")
            text = _flatten_value(value)
            if text:
                parts.append(f"{field}: {text}")
    if not parts:
        # 原始资产：扁平化全文（排除 meta/provenance 等元信息噪声）。
        text = _flatten_asset_body(asset_dict)
        if text:
            parts.append(text)
    snippet = "；".join(parts)
    if len(snippet) > SNIPPET_LEN:
        snippet = snippet[: SNIPPET_LEN - 1] + "…"
    return snippet


def _flatten_asset_body(asset_dict: Dict[str, Any]) -> str:
    """把资产正文（排除 meta/provenance 元信息）扁平化为可检索文本。"""
    keep_keys = {
        "craft_analysis",
        "craft_summary",
        "aggregate",
        "chapter_analyses",
        "payoff_density",
        "opening_analysis",
        "narration",
        "dialogue",
        "emotion_handling",
        "imagery",
        "banned",
    }
    parts: List[str] = []
    for key, value in asset_dict.items():
        if key in ("meta", "provenance", "rules", "blindspots", "stats"):
            continue
        if isinstance(value, dict):
            sub = _flatten_asset_body(value)
            if sub:
                parts.append(sub)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    sub = _flatten_asset_body(item)
                    if sub:
                        parts.append(sub)
                elif isinstance(item, str):
                    parts.append(item)
        elif isinstance(value, str):
            parts.append(value)
    return "；".join(p for p in parts if p)


def _flatten_value(value: Any) -> str:
    """把规则 value 转为紧凑文本（列表/字典递归拼接）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        parts = [_flatten_value(v) for v in value]
        return "、".join(p for p in parts if p)
    if isinstance(value, dict):
        parts = [f"{k}:{_flatten_value(v)}" for k, v in value.items()]
        return "，".join(p for p in parts if p)
    return str(value)


# ---------------------------------------------------------------------------
# 字符 n-gram 向量（纯标准库）
# ---------------------------------------------------------------------------

def _corpus_text(asset_id: str, dimension: str, asset_dict: Dict[str, Any]) -> str:
    """从资产提取规范化 corpus 全文。

    与 ``_add_doc`` 原有拼接逻辑一致：asset_id + 维度 + 正文（经
    ``_flatten_asset_body`` 字段白名单清洗）+ rules 的 field/value。BM25 词项与
    向量 n-gram 都从此文本派生，保证两份表示看到同一份文档语义。
    """
    corpus_parts: List[str] = [asset_id, dimension]
    corpus_parts.append(_flatten_asset_body(asset_dict))
    for rule in asset_dict.get("rules") or []:
        if isinstance(rule, dict):
            corpus_parts.append(str(rule.get("field", "")))
            corpus_parts.append(_flatten_value(rule.get("value")))
    return " ".join(corpus_parts)


def _ngram_counter(text: str, max_n: int = NGRAM_MAX_N) -> Counter:
    """对文本生成 1..max_n 的字符 n-gram 多重集。

    键为 ``f"{n}:{gram}"``（前缀 n 避免不同长度 gram 的字符串冲突），值为该 gram
    在文本中的出现次数。用 ``MIN_NGRAM_GRAM_LEN`` 过滤过短 gram（默认 1，全保留）。
    """
    counter: Counter = Counter()
    if not text:
        return counter
    for n in range(MIN_NGRAM_GRAM_LEN, max_n + 1):
        for i in range(len(text) - n + 1):
            gram = text[i : i + n]
            if n == 1 and (gram in _UNIGRAM_STOPCHARS or gram in _UNIGRAM_STOPASCII):
                continue
            counter[f"{n}:{gram}"] += 1
    return counter


def _norm(c: Counter) -> float:
    """计算向量的 L2 范数（‖v‖ = sqrt(Σ v[g]²)）。"""
    if not c:
        return 0.0
    return math.sqrt(sum(v * v for v in c.values()))


def _cosine_sim(q: Counter, q_norm: float, d: Counter, d_norm: float) -> float:
    """计算两个向量的余弦相似度（只遍历共同键）。

    任一范数为 0（全零向量）时返回 0，避免除零。频次非负，故余弦恒 ≥ 0。
    """
    if q_norm <= 0.0 or d_norm <= 0.0:
        return 0.0
    dot = 0.0
    for g, qv in q.items():
        dv = d.get(g)
        if dv:
            dot += qv * dv
    if dot <= 0.0:
        return 0.0
    return dot / (q_norm * d_norm)


# ---------------------------------------------------------------------------
# 索引构建
# ---------------------------------------------------------------------------

def build_index(assets: Dict[str, Dict[str, dict]]) -> Index:
    """把四类资产构建为倒排索引。

    兼容两种输入结构：
        * ``{dimension: distilled_dict}``（``distill_genre`` 的产出，每维度一篇文档，
          asset_id 取 ``meta.id``）；
        * ``{dimension: {book: asset_dict}}``（``collect_assets`` 的产出，每书一篇
          文档，asset_id 取 ``meta.id``，缺失则 ``<dimension>-<book>`` 兜底）。

    Args:
        assets: 资产字典。

    Returns:
        Index 实例。assets 非 dict（如 None）时返回空索引，不 crash。
    """
    if not isinstance(assets, dict):
        return Index()

    index = Index()

    def _add_doc(dimension: str, asset_dict: Dict[str, Any]) -> None:
        """把单个 asset_dict 加入索引。

        asset_dict 非 dict（如 None）时静默跳过，避免后续 ``.get`` 与
        ``_build_snippet`` 崩溃。
        """
        if not isinstance(asset_dict, dict):
            return
        meta = asset_dict.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        asset_id = meta.get("id") or f"{dimension}-{meta.get('source_title', 'distilled')}"
        snippet = _build_snippet(asset_dict)

        # 文档全文：asset_id + 维度 + 正文（distilled 的 rules/盲区 或原始资产的技法名）。
        corpus = _corpus_text(asset_id, dimension, asset_dict)
        terms = Counter(_tokenize(corpus))
        ngrams = _ngram_counter(corpus)
        doc = DocEntry(
            asset_id=asset_id,
            dimension=dimension,
            asset_dict=asset_dict,
            terms=terms,
            snippet=snippet,
            ngrams=ngrams,
            corpus=corpus,
        )
        doc_idx = len(index.docs)
        index.docs.append(doc)
        for term in terms:
            index.inverted.setdefault(term, []).append(doc_idx)
        for term in terms:
            index.doc_freq[term] = index.doc_freq.get(term, 0) + 1

    for dimension, group in assets.items():
        if not isinstance(group, dict):
            continue
        # 判别结构：group 直接是 distilled_dict（含 rules/meta），还是 {book: asset_dict}。
        if "meta" in group and isinstance(group.get("meta"), dict):
            # {dimension: distilled_dict} 结构。
            _add_doc(dimension, group)
            continue
        # {dimension: {book: asset_dict}} 结构。
        for key, asset_dict in group.items():
            if not isinstance(asset_dict, dict):
                continue
            _add_doc(dimension, asset_dict)

    # 预计算每篇文档 n-gram 向量的 L2 范数（与 docs 下标对齐，供余弦检索复用）。
    index.norms = [_norm(doc.ngrams) for doc in index.docs]
    return index


def _idf(term: str, index: Index) -> float:
    """计算词项 idf（带缓存）。

    idf(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )
    """
    if term in index.idf_cache:
        return index.idf_cache[term]
    n = len(index.docs)
    df = index.doc_freq.get(term, 0)
    val = math.log((n - df + 0.5) / (df + 0.5) + 1.0)
    index.idf_cache[term] = val
    return val


def _bm25_score(query_terms: List[str], doc: DocEntry, index: Index) -> float:
    """BM25 简化打分（带 CJK 子串重叠补偿）。

    score(q, d) = Σ_{t∈q∩d} idf(t) * tf(t,d) * (k1+1) / (tf(t,d) + k1)

    由于分词正则 ``[\\w\\u4e00-\\u9fff]+`` 会把连续中日韩字符切成一个整体 token
    （如「作为微小钩子」），而查询词「钩子」是它的子串，二者无法精确相等。故在
    **精确 token 未命中**时，追加「子串重叠」匹配：查询词项 t 与文档词项 dt 满足
    ``t in dt``（或 ``dt in t``，且 len(dt)>=2 避免单字误配）即视为命中，tf 取
    ``doc.terms[dt]``，idf 取 dt 的 idf。这在不引入分词器的前提下提升 CJK 召回。
    """
    score = 0.0
    for term in query_terms:
        # 1) 精确 token 命中。
        tf = doc.terms.get(term, 0)
        if tf > 0:
            idf = _idf(term, index)
            score += idf * tf * (BM25_K1 + 1.0) / (tf + BM25_K1)
            continue
        # 2) 子串重叠命中：查询词项是文档词项的子串（或反之）。
        # 对每个查询词项，仅在所有匹配 dt 中累加「最佳匹配」一次，避免同一
        # 查询词项对同一文档因多个包含它的 token 而重复累加、虚高长文档分数。
        best_contrib = 0.0
        for dt, dtf in doc.terms.items():
            if len(dt) < 2 or len(term) < 2:
                continue
            if term in dt or dt in term:
                idf = _idf(dt, index)
                contrib = idf * dtf * (BM25_K1 + 1.0) / (dtf + BM25_K1)
                if contrib > best_contrib:
                    best_contrib = contrib
        score += best_contrib
    return score


def _vector_score(query_ngrams: Counter, q_norm: float, doc: DocEntry, idx: Index) -> float:
    """向量分支打分：查询 n-gram 与文档 n-gram 的余弦相似度，返回 [0,1]。

    Args:
        query_ngrams: 查询 n-gram 多重集。
        q_norm: 查询向量 L2 范数（预先算好，避免每篇文档重复开方）。
        doc: 目标文档（读取 ``doc.ngrams``）。
        idx: 索引（读取 ``idx.norms``，需与 docs 下标对齐）。

    Returns:
        余弦相似度 [0,1]；文档下标越界或范数为 0 时返回 0.0。
    """
    doc_norm = 0.0
    for i, d in enumerate(idx.docs):
        if d is doc:
            doc_norm = idx.norms[i] if i < len(idx.norms) else _norm(doc.ngrams)
            break
    if doc_norm <= 0.0:
        return 0.0
    return _cosine_sim(query_ngrams, q_norm, doc.ngrams, doc_norm)


def _fused_score(bm25_raw: float, bm25_max: float, cos_sim: float, alpha: float = FUSION_ALPHA) -> float:
    """融合打分：BM25（max 归一化）+ 余弦线性加权。

    final = alpha * (bm25_raw / bm25_max) + (1 - alpha) * cos_sim

    Args:
        bm25_raw: 该文档 BM25 原始分（≥ 0）。
        bm25_max: 当次候选集 BM25 最大值（用于归一化到 [0,1]）。
        cos_sim: 余弦相似度 [0,1]。
        alpha: BM25 权重（默认 ``FUSION_ALPHA``）。

    Returns:
        融合分 [0,1]。
    """
    norm_bm25 = 0.0
    if bm25_max > 0.0:
        norm_bm25 = bm25_raw / bm25_max
    return alpha * norm_bm25 + (1.0 - alpha) * cos_sim


# ---------------------------------------------------------------------------
# 检索
# ---------------------------------------------------------------------------

def retrieve_for_intent(intent: str, index: Index, top_k: int = TOP_K) -> List[HitEntry]:
    """按意图字符串检索最相关的蒸馏片段。

    流程：分词 → 意图映射加权（命中关键词注入额外召回词项）→ 倒排索引打分
    → 按 score 降序、同分按 asset_id 升序排序 → 截 top_k。

    Args:
        intent: 意图字符串（如 ``"悬疑反转钩子"``）。intent 非 str（如
            list/int/None 等调用方误用）时视为空意图，直接返回空列表，不 crash
            也不产脏数据。
        index: 已构建的 Index。index 为 None 时同样返回空列表。
        top_k: 返回条数上限。

    Returns:
        HitEntry 列表（score 降序）。
    """
    if not isinstance(intent, str) or index is None or not index.docs:
        return []

    query_terms = _tokenize(intent)
    if not query_terms:
        return []

    # 意图映射：命中关键词 → 注入额外召回词项（提升对应维度召回）。
    # 关键词匹配采用「子串包含」而非仅 token 相等：中文意图如「悬疑反转钩子」
    # 会被分词为一个连续 token，但其中包含「钩子」等关键词，需子串识别。
    intent_lower = str(intent).lower()
    expanded_terms: List[str] = list(query_terms)
    for keyword, dim_map in INTENT_MAP.items():
        if keyword in query_terms or keyword in intent_lower:
            for dimension, extra_terms in dim_map.items():
                for et in extra_terms:
                    if et not in expanded_terms:
                        expanded_terms.append(et)

    # 查询向量：意图映射注入的额外词项同样进入 n-gram，与向量检索协同。
    query_ngrams = _ngram_counter(" ".join(expanded_terms))

    # 单字 n-gram 文档频率过滤：单字 gram 在 ≥80% 文档中出现时无判别力，属于
    # 「无关查询与文档在单字层伪重叠」的噪声源（如「学/量/力」等高频字），过滤后
    # 恢复「完全无关意图 → 空列表」语义，同时保留「钩/爽」等低频单字意图的召回。
    unigram_df: Dict[str, int] = {}
    for doc in index.docs:
        for key in doc.ngrams:
            if key.startswith("1:"):
                ch = key[2:]
                unigram_df[ch] = unigram_df.get(ch, 0) + 1
    stop_threshold = UNIGRAM_DF_STOP_RATIO * len(index.docs)
    query_ngrams = Counter(
        {
            k: v
            for k, v in query_ngrams.items()
            if not (
                k.startswith("1:")
                and unigram_df.get(k[2:], 0) >= UNIGRAM_DF_STOP_MIN
                and unigram_df.get(k[2:], 0) >= stop_threshold
            )
        }
    )
    q_norm = _norm(query_ngrams)

    # 先对每篇文档算 BM25 原始分与余弦分，收集 BM25 最大值用于归一化。
    bm25_scores: List[float] = []
    cos_scores: List[float] = []
    for doc in index.docs:
        bm25_scores.append(_bm25_score(expanded_terms, doc, index))
        cos_scores.append(_vector_score(query_ngrams, q_norm, doc, index))
    bm25_max = max(bm25_scores) if bm25_scores else 0.0

    # 融合打分。
    hits: List[HitEntry] = []
    for doc, bm25, cos in zip(index.docs, bm25_scores, cos_scores):
        score = _fused_score(bm25, bm25_max, cos, FUSION_ALPHA)
        if score < MIN_FUSION_SCORE:
            continue
        hits.append(
            HitEntry(
                asset_id=doc.asset_id,
                dimension=doc.dimension,
                score=score,
                snippet=doc.snippet,
            )
        )

    # 排序：score 降序，同分 asset_id 升序（稳定可复现）。
    hits.sort(key=lambda h: (-h.score, h.asset_id))
    return hits[:top_k]


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def render_retrieval(hits: List[HitEntry]) -> str:
    """把检索命中渲染为「针对性注入」段。

    Returns:
        Markdown 文本；无命中返回空串（调用方据此决定是否注入）。
    """
    if not hits:
        return ""
    lines: List[str] = ["### 针对性注入（来自检索）"]
    for h in hits:
        lines.append(f"- {h.snippet}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 便捷入口：从资产目录直接构建索引并检索
# ---------------------------------------------------------------------------

def build_index_from_genre(
    genre: str, book_names: Optional[List[str]] = None
) -> Index:
    """从资产目录采集四类资产并构建索引（依赖 distill_core.collect_assets）。"""
    try:
        from distill_core import collect_assets  # noqa: F401 延迟导入避免循环依赖
    except ImportError:
        return Index()
    assets = collect_assets(genre, book_names=book_names)
    return build_index(assets)
