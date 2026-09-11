"""引擎适配层：唯一 import novel-lab scripts/ 模块的地方。

职责：
1. 注入 ``scripts/`` 到 ``sys.path``，使 ``sampler``/``pipeline`` 等扁平名可 import。
2. 薄封装章切分（sampler）、批次切分（新增）、量化指标（metrics）。
3. 单批分析：复用 pipeline 的 load_prompt / build_user_input / run_pass / extract_json，
   但把输入切片缩小到「单批文本」，metrics 用整书缓存复用（不修改 pipeline 源码）。
4. 资产组装（整书跑完后统一组装 voice-card / 观测）。

注意：本模块是唯一接触 scripts/ 的地方，其他 gui 模块不得 import novel-lab 脚本。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gui import config

# ---------------------------------------------------------------------------
# sys.path 注入（启动时执行一次）
# ---------------------------------------------------------------------------
if str(config.SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(config.SCRIPTS_DIR))

# 延迟 import，避免模块级副作用在 self-check 前就触发。
_sampler = None
_pipeline = None
_metrics = None
_llm_client = None


def _get_sampler():
    global _sampler
    if _sampler is None:
        import sampler as _sampler  # type: ignore
    return _sampler


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        import pipeline as _pipeline  # type: ignore
    return _pipeline


def _get_metrics():
    global _metrics
    if _metrics is None:
        import metrics as _metrics  # type: ignore
    return _metrics


def _get_llm_client():
    global _llm_client
    if _llm_client is None:
        import llm_client as _llm_client  # type: ignore
    return _llm_client


# 延迟 import：report / report_craft / consistency 等报告与打分脚本。
_report = None
_report_craft = None
_consistency = None


def _get_report():
    global _report
    if _report is None:
        import report as _report  # type: ignore
    return _report


def _get_report_craft():
    global _report_craft
    if _report_craft is None:
        import report_craft as _report_craft  # type: ignore
    return _report_craft


def _get_consistency():
    global _consistency
    if _consistency is None:
        import consistency as _consistency  # type: ignore
    return _consistency


# ---------------------------------------------------------------------------
# 章切分（复用 sampler）
# ---------------------------------------------------------------------------

def split_chapters(text: str) -> List[Tuple[str, str]]:
    """把整本文本切成 [(标题, 正文), ...]，过滤空章。"""
    return _get_sampler().split_chapters(text)


def detect_volumes(chapters: List[Tuple[str, str]]) -> List[Tuple[int, int]]:
    """按『第X卷』切分卷边界，返回 [(start, end), ...] 索引对（0 起）。"""
    return _get_sampler().detect_volumes(chapters)


# ---------------------------------------------------------------------------
# 批次切分（新增薄封装）
# ---------------------------------------------------------------------------

def split_batches(text: str, batch_size: int) -> List[Dict[str, Any]]:
    """把一段文本按 ``batch_size`` 字符切成批次列表。

    尽量在换行/句号边界断开，避免把一个句子劈成两半；单批硬上限即 batch_size。

    Returns:
        [{"batch_index": 0, "char_start": 0, "char_end": 100, "text": "...", ...}, ...]
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size 必须为正整数，得到 {batch_size}")

    text = text or ""
    if not text.strip():
        return []

    batches: List[Dict[str, Any]] = []
    start = 0
    total = len(text)
    bidx = 0
    while start < total:
        end = min(start + batch_size, total)
        # 若未到文末，尽量回退到最近的换行或句末边界。
        if end < total:
            cut = _find_cut_boundary(text, start, end)
            end = cut if cut > start else end
        segment = text[start:end]
        if segment.strip():
            batches.append({
                "batch_index": bidx,
                "char_start": start,
                "char_end": end,
                "text": segment,
            })
            bidx += 1
        start = end
    return batches


def _find_cut_boundary(text: str, start: int, end: int) -> int:
    """在 [start, end) 内回退查找最近的换行/句号边界，返回可用的切点。"""
    window = text[start:end]
    # 优先换行
    nl = window.rfind("\n")
    if nl > len(window) // 2:
        return start + nl + 1
    # 其次中文句末标点
    best = -1
    for ch in ("。", "！", "？", "…", "；", "！", "？"):
        idx = window.rfind(ch)
        if idx > best:
            best = idx
    if best > len(window) // 2:
        return start + best + 1
    return end


# ---------------------------------------------------------------------------
# 量化指标（整书算一次，缓存复用）
# ---------------------------------------------------------------------------

def compute_metrics(text: str) -> Dict[str, Any]:
    """对整本书算一次量化指标（metrics.compute），供单批分析复用。"""
    return _get_metrics().compute(text)


# ---------------------------------------------------------------------------
# 单批分析（核心难点 A2 的解法：切片缩小到单批）
# ---------------------------------------------------------------------------

# 每个 pass 的切片结构 key（与 sampler.build_slices 输出对齐）。
_PASS_SLICE_KEY = {
    "pass1_structure": "pass1_structure",
    "pass2_character": "pass2_character",
    "pass3_style": "pass3_style",
    "pass4_commercial": "pass4_commercial",
}


def build_single_batch_slices(
    kind: str,
    chapter_index: int,
    chapter_title: str,
    batch_text: str,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """把「单批文本」构造成 pipeline.build_user_input 需要的切片结构。

    这是 GUI 单章单批粒度与 pipeline 整书粒度的衔接点：
    - pass1_structure / pass3_style / pass4_commercial 都吃 ``chapters`` 列表，
      这里只放一个「章」条目，text 为该批文本，tail500 取批末 500 字。
    - pass2_character 吃 ``dialogues`` 列表，这里无法对单批可靠抽取对话（
      对话抽取依赖跨批上下文），故返回空 dialogues，实际分析以结构层为主。
    """
    reason = f"批次切片（第{chapter_index}章第{_batch_reason(batch_text)}）"
    chapter_entry = {
        "index": chapter_index,
        "title": chapter_title,
        "text": batch_text,
        "tail500": batch_text[-500:],
        "reason": reason,
    }
    if kind == "pass2_character":
        return {"pass2_character": {"dialogues": []}}
    if kind == "pass1_structure":
        return {"pass1_structure": {"chapters": [chapter_entry]}}
    if kind == "pass3_style":
        return {"pass3_style": {"chapters": [chapter_entry]}}
    if kind == "pass4_commercial":
        return {"pass4_commercial": {"chapters": [chapter_entry]}}
    raise ValueError(f"未知 Pass: {kind}")


def _batch_reason(_text: str) -> str:
    return "批"


def run_batch(
    kind: str,
    chapter_index: int,
    chapter_title: str,
    batch_text: str,
    metrics: Dict[str, Any],
    dry_run: bool = False,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """对单批文本执行一次 pass 分析，返回结果 dict。

    复用 pipeline.load_prompt / build_user_input / run_pass，不改 pipeline 源码。
    """
    pipeline = _get_pipeline()
    slices = build_single_batch_slices(kind, chapter_index, chapter_title, batch_text, metrics)
    return pipeline.run_pass(kind, slices, metrics, dry_run=dry_run, model_id=model_id)


# ---------------------------------------------------------------------------
# 资产组装（整书跑完后统一组装）
# ---------------------------------------------------------------------------

def assemble_voice_card(
    name: str,
    genre: str,
    manifest: Dict[str, Any],
    pass2: Dict[str, Any],
    pass3: Dict[str, Any],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """组装 voice-card（复用 pipeline.assemble_voice_card）。"""
    return _get_pipeline().assemble_voice_card(name, genre, manifest, pass2, pass3, metrics)


def assemble_obs(kind: str, name: str, genre: str, pass_out: Dict[str, Any]) -> Dict[str, Any]:
    """组装结构/商业观测（复用 pipeline.assemble_obs）。"""
    return _get_pipeline().assemble_obs(kind, name, genre, pass_out)


def extract_json(raw: str) -> Dict[str, Any]:
    """LLM 输出 → JSON（复用 pipeline.extract_json）。"""
    return _get_pipeline().extract_json(raw)


def load_prompt(kind: str) -> Tuple[str, str]:
    """读取 prompt 模板 (system, user_template)（复用 pipeline.load_prompt）。"""
    return _get_pipeline().load_prompt(kind)


def any_model_configured() -> bool:
    """是否有外部模型配置（复用 llm_client.any_model_configured）。"""
    return _get_llm_client().any_model_configured()


def list_models() -> List[Dict[str, Any]]:
    """列出已配置模型（不含密钥），供 /api/config/models 使用。"""
    llm = _get_llm_client()
    cfg = llm.load_models()
    models = cfg.get("models", {})
    result = []
    for mid, m in models.items():
        env_name = m.get("api_key_env", "")
        has_env = bool(env_name and __import__("os").environ.get(env_name))
        has_secret = bool(llm.load_secrets().get(mid))
        result.append({
            "id": mid,
            "model_name": m.get("model_name", ""),
            "protocol": m.get("protocol", "openai"),
            "base_url": m.get("base_url", ""),
            "has_key": has_env or has_secret,
        })
    return result


# ---------------------------------------------------------------------------
# 报告生成 / 打分（复用 report.py / report_craft.py / consistency.py 原子函数）
# ---------------------------------------------------------------------------

def build_report(
    voice: Dict[str, Any],
    structure: Dict[str, Any],
    commercial: Dict[str, Any],
    title_override: Optional[str] = None,
) -> str:
    """拆书报告：voice-card + structure + commercial → Markdown 文本。

    复用 ``report.build_report``（原子函数），不复用其 ``main`` 端到端编排。
    """
    return _get_report().build_report(voice, structure, commercial, title_override=title_override)


def render_craft_report(craft: Dict[str, Any]) -> str:
    """笔法报告：craft-card → Markdown 文本（复用 ``report_craft.render_craft_report``）。"""
    return _get_report_craft().render_craft_report(craft)


def check_report_min_length(reports_dir, name: str) -> Dict[str, Any]:
    """铁律二「真·合计口径」校验：拆书报告 + 笔法分析 合计 ≥ 10000 字符。

    【为何需要】该校验原先只内联在 CLI 的 ``novel.py 分析`` 收尾，GUI 生成报告后
    直接发布 report_ready，把铁律二整条绕过——低于门槛的报告照样当合格品交付。
    本函数把校验暴露给 GUI，与 CLI 共用 ``scripts/report.py`` 的同一实现（单一来源）。

    Returns:
        dict: {book_chars, craft_chars, total, ok, min_chars, book_path, craft_path}
    """
    return _get_report().check_combined_report_length(reports_dir, name)


def score_text(voice_card: Dict[str, Any], text: str, label: str = "") -> Dict[str, Any]:
    """一致性打分：voice-card + 章节文本 → (score, details, raw) 归一化为 dict。

    复用 ``consistency.score_text``（原子函数），返回结构化结果供章节打分图使用。
    """
    total_score, details, raw = _get_consistency().score_text(voice_card, text, label=label)
    return {"score": float(total_score), "details": details, "raw": raw}


def get_pass5_craft(book_id: str) -> Optional[Dict[str, Any]]:
    """预留：读取某书 pass5（笔法）craft-card 资产。阶段一尽力而为，通常返回 None。"""
    _ = book_id
    return None


# ---------------------------------------------------------------------------
# W10 阶段二扩展：写作 / 质检 / 组装原子函数包装
# ---------------------------------------------------------------------------

def _get_inject():
    global _inject
    if _inject is None:
        import inject as _inject  # type: ignore
    return _inject


def _get_write():
    global _write
    if _write is None:
        import write as _write  # type: ignore
    return _write


def _get_chapter_check():
    global _chapter_check
    if _chapter_check is None:
        import chapter_check as _chapter_check  # type: ignore
    return _chapter_check


def _get_book_quality():
    global _book_quality
    if _book_quality is None:
        import book_quality as _book_quality  # type: ignore
    return _book_quality


def _get_qc():
    global _qc
    if _qc is None:
        import qc as _qc  # type: ignore
    return _qc


def _get_normalize():
    global _normalize
    if _normalize is None:
        import normalize as _normalize  # type: ignore
    return _normalize


def _get_assemble():
    global _assemble
    if _assemble is None:
        import assemble as _assemble  # type: ignore
    return _assemble


_inject = None
_write = None
_chapter_check = None
_book_quality = None
_qc = None
_normalize = None
_assemble = None


# --- 注入（inject.py）---

def build_writing_prompt(voice: Dict[str, Any], structure: Optional[Dict] = None,
                         commercial: Optional[Dict] = None, genre_pack: Optional[Dict] = None,
                         craft_card: Optional[Dict] = None, distilled: Optional[Dict] = None,
                         context_intent: Optional[str] = None,
                         tracking_state: Optional[Dict] = None,
                         genre_prose_card: Optional[Dict] = None) -> str:
    """资产 → 写作 system prompt（inject.build_prompt）。"""
    return _get_inject().build_prompt(
        voice, structure=structure, commercial=commercial, genre_pack=genre_pack,
        craft_card=craft_card, distilled=distilled, context_intent=context_intent,
        tracking_state=tracking_state, genre_prose_card=genre_prose_card)


# --- 写作（write.py 原子 + llm_client）---

def llm_chat(user: str, system: str, task: str = "writing", max_tokens: int = 6000,
             temperature: float = 0.8, json_mode: bool = False) -> Dict[str, Any]:
    """LLM 对话调用（llm_client.chat）。无模型时由调用方先判 any_model_configured()。"""
    return _get_llm_client().chat(user=user, system=system, task=task,
                                  max_tokens=max_tokens, temperature=temperature,
                                  json_mode=json_mode)


def ensure_novel_structure(novel_dir: str, name: str = "新书") -> Path:
    """建 novel 项目骨架（write.ensure_novel_structure）。"""
    return _get_write().ensure_novel_structure(Path(novel_dir), name)


def save_chapter(novel_dir: str, chapter_no: int, content: str) -> Path:
    """落盘章节（write.save_chapter）。"""
    return _get_write().save_chapter(Path(novel_dir), chapter_no, content)


# --- 打分 / 检查（consistency.py / chapter_check.py）---

def chapter_check(text: str, genre_pack: Optional[Dict] = None) -> Dict[str, Any]:
    """章节质量 12 维检查（chapter_check.chapter_check）。"""
    return _get_chapter_check().chapter_check(text, genre_pack)


def resolve_thresholds(genre_pack: Optional[Dict] = None) -> Tuple[int, int]:
    """解析质量阈值 (pass_line, warn_line)（chapter_check.resolve_thresholds）。"""
    return _get_chapter_check().resolve_thresholds(genre_pack)


# --- 全书质检（book_quality.py）---

def book_quality_check(chapter_dir: str, voice_card_path: Optional[str] = None,
                       prev_chapters_dir: Optional[str] = None) -> Dict[str, Any]:
    """全书质检（book_quality.book_quality_check）。"""
    return _get_book_quality().book_quality_check(
        chapter_dir, voice_card_path=voice_card_path, prev_chapters_dir=prev_chapters_dir)


# --- QC（qc.py）---

def run_qc(chapter_dir: str, *, voice_card_path: Optional[str] = None,
           genre_pack_path: Optional[str] = None, asset_path: Optional[str] = None,
           book_path: Optional[str] = None, novel_dir: Optional[str] = None,
           enable_llm_hook: bool = False) -> Dict[str, Any]:
    """四层十二维 QC（qc.run_qc），返回 report dict + markdown。"""
    report = _get_qc().run_qc(
        chapter_dir, voice_card_path=voice_card_path, genre_pack_path=genre_pack_path,
        asset_path=asset_path, book_path=book_path, novel_dir=novel_dir,
        enable_llm_hook=enable_llm_hook)
    return {"report": report, "markdown": _get_qc().to_markdown(report)}


# --- 组装（assemble.py / normalize.py）---

def normalize_pass2(pass2: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pass2 角色声线归一化（normalize.normalize_pass2）。"""
    return _get_normalize().normalize_pass2(pass2)


def normalize_pass3(pass3: Dict[str, Any]) -> Tuple[Dict, Dict, Dict, Dict, Dict]:
    """Pass3 文风归一化（normalize.normalize_pass3）。"""
    return _get_normalize().normalize_pass3(pass3)


def assemble_asset_voice_card(name: str, genre: str, manifest: Dict, metrics: Dict,
                              voices: List, narration: Dict, dialogue: Dict, emotion: Dict,
                              imagery: Dict, banned: Dict) -> Dict[str, Any]:
    """组装 voice-card（assemble.assemble_voice_card）。"""
    return _get_assemble().assemble_voice_card(
        name, genre, manifest, metrics, voices, narration, dialogue, emotion, imagery, banned)


def assemble_asset_obs(kind: str, name: str, genre: str, pass_out: Dict) -> Dict:
    """组装 structure-obs / commercial-obs（assemble.assemble_obs）。"""
    return _get_assemble().assemble_obs(kind, name, genre, pass_out)


def assemble_asset_craft_card(name: str, genre: str, manifest: Dict, metrics: Dict,
                              pass5: Dict) -> Dict[str, Any]:
    """组装 craft-card（assemble.assemble_craft_card）。"""
    return _get_assemble().assemble_craft_card(name, genre, manifest, metrics, pass5)


def clean_verbatim(asset: Dict[str, Any], book_text: str) -> Tuple[Dict, int]:
    """清除资产中夹带的原文台词（assemble._clean_verbatim）。"""
    return _get_assemble()._clean_verbatim(asset, book_text)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

def adapter_self_check() -> bool:
    """验证 scripts/ 原子函数可被正常调用（不调 LLM）。"""
    try:
        # 章切分
        chs = split_chapters("第1章\n这是正文内容。\n\n第2章\n这是第二章正文。\n")
        assert len(chs) == 2, f"split_chapters 结果异常: {chs}"
        # 批次切分
        text = "a" * 1000 + "\n" + "b" * 1000
        batches = split_batches(text, 600)
        assert len(batches) >= 2, f"split_batches 结果异常: {len(batches)}"
        # 量化
        m = compute_metrics("这是测试文本。有对话吗？")
        assert "total_chars" in m, "compute_metrics 缺 total_chars"
        # 单批切片
        slices = build_single_batch_slices("pass1_structure", 1, "第1章", "正文", m)
        assert "pass1_structure" in slices
        # W10：阈值解析（纯算法，不调 LLM）
        pass_line, warn_line = resolve_thresholds(None)
        assert pass_line == 75 and warn_line == 60, f"resolve_thresholds 异常: {pass_line}/{warn_line}"
        # W10：章节检查（纯算法）
        qc_result = chapter_check("这是一段测试正文，用来验证章节检查函数可调用。" * 20)
        assert "score" in qc_result and "verdict" in qc_result, "chapter_check 返回结构异常"
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[adapter_self_check] 失败: {exc}")
        return False
