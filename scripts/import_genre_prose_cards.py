#!/usr/bin/env python3
"""oh-story 32 题材文风卡 → genre-prose-card 轻量资产批量转换器（纯标准库）。

把 ``reference/oh-story-claudecode/skills/story-long-write/references/genre-prose-cards/*.md``
（YAML frontmatter + 若干 ``##`` 小节）转换为独立轻量的 ``genre-prose-card`` 资产，
与 genre-pack（多书聚合规则包）彻底分离，作为「未来升格为 genre-pack」的种子。

设计要点（题材无关，无硬编码关键词表）：

* 复用 ``yaml_lite.load_frontmatter`` 解析 frontmatter。
* **动态收集** body 中所有 ``## 标题`` 小节为 key，不依赖固定 13 标题清单。
* 映射规则（能结构化→结构化，不能→原文保留，无数据→空置不臆造）：
  - ``genre/aliases`` → ``meta.name`` / ``meta.sub_tags``
  - ``platform`` → ``meta.target_platform``
  - ``confidence``(high/medium/low) → ``meta.confidence``(0.85/0.65/0.4)
  - ``source`` → ``meta.provenance.source``（统一标注 zenstory-ai/oh-story-claudecode + MIT）
  - 「禁止漂移」→ ``language_rules.forbidden_elements``（提取「不要/禁止/不得」句式）
  - 「对话与声线」→ ``language_rules.voice_notes``
  - 「章尾钩子」「正文落点」→ ``structure.hook_notes``
  - 「节奏密度」「前中后期打法」→ ``structure.arc_rhythm_notes``
  - 「爽点与情绪释放」→ ``commercial.payoff_notes``
  - 「证据摘要」→ ``meta.provenance.evidence``
  - 其余全部小节 → ``prose.sections``（原文兜底）
  - 量化商业字段 / ``source_books`` → 留空占位，升格时由范文拆书填充
* ``meta.id`` 由题材名确定性生成（内置 32 项题材名 → 拼音 slug 映射表）。
* 顺带生成 ``genre-prose-card-index.json``（题材名 → id / 文件路径索引）。

用法：:

    python scripts/import_genre_prose_cards.py \
        --src reference/oh-story-claudecode/skills/story-long-write/references/genre-prose-cards/ \
        --out assets/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 允许作为脚本独立运行，也允许被 novel.py 子进程调用（cwd 为项目根）。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yaml_lite import load_frontmatter  # noqa: E402

# 32 题材中文名 → 拼音 slug 的确定性映射（team-lead 已拍板，照抄）。
GENRE_ID_MAP: Dict[str, str] = {
    "东方仙侠": "genre-xianxia",
    "传统玄幻": "genre-xuanhuan",
    "历史古代": "genre-lishi",
    "历史脑洞": "genre-lishi-naodong",
    "双男主": "genre-shuangnan",
    "古言脑洞": "genre-guyan-naodong",
    "古风世情": "genre-gufeng-shiqing",
    "女频悬疑": "genre-nvpin-xuanyi",
    "女频种田": "genre-nvpin-zhongtian",
    "宫斗宅斗": "genre-gongdou",
    "年代": "genre-niandai",
    "快穿": "genre-kuaichuan",
    "悬疑灵异": "genre-xuanyi-lingyi",
    "悬疑脑洞": "genre-xuanyi-naodong",
    "战神赘婿": "genre-zhanshen-zhuixu",
    "抗战谍战": "genre-kangzhan-diezhan",
    "星光璀璨": "genre-xingguang",
    "民国言情": "genre-minguo-yanqing",
    "游戏体育": "genre-youxi-tiyu",
    "玄幻脑洞": "genre-xuanhuan-naodong",
    "玄幻言情": "genre-xuanhuan-yanqing",
    "现言脑洞": "genre-xianyan-naodong",
    "科幻末世": "genre-kehuan-moshi",
    "职场婚恋": "genre-zhichang-hunlian",
    "西方奇幻": "genre-xifang-qihuan",
    "豪门总裁": "genre-haomen-zongcai",
    "都市修真": "genre-dushi-xiuzhen",
    "都市日常": "genre-dushi-richang",
    "都市种田": "genre-dushi-zhongtian",
    "都市脑洞": "genre-dushi-naodong",
    "都市高武": "genre-dushi-gaowu",
    "青春甜宠": "genre-qingchun-tianchong",
}

# 「禁止漂移」小节里用于提取 forbidden_elements 的句式标记。
FORBIDDEN_MARKERS = ("不要", "禁止", "不得")

# provenance 统一溯源（共享知识约定 6：MIT 需保留 attribution）。
PROVENANCE_SOURCE = "zenstory-ai/oh-story-claudecode"
PROVENANCE_LICENSE = "MIT"


def _now_iso() -> str:
    """返回带时区标记的 ISO 8601 时间戳（UTC）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _confidence_map(level: Any) -> float:
    """frontmatter ``confidence``（high/medium/low）→ 0~1 数值。

    缺省或无法识别时返回 0.5（共享知识约定 5）。
    """
    mapping = {"high": 0.85, "medium": 0.65, "low": 0.4}
    if isinstance(level, (int, float)) and not isinstance(level, bool):
        return float(level)
    if isinstance(level, str):
        return mapping.get(level.strip().lower(), 0.5)
    return 0.5


def parse_sections(body: str) -> Dict[str, str]:
    """把 markdown 正文按 ``## 标题`` 动态切成 ``{标题: 内容}``。

    与 convert_genre_card.py 的 parse_sections 不同，这里**不依赖固定标题清单**：
    动态收集所有 ``## 标题`` 为 key，保证未来源卡新增小节不丢数据。
    一级标题（``# xxx``）忽略。

    Args:
        body: frontmatter 之后的 markdown 正文。

    Returns:
        标题 → 内容（去首尾空白）的字典，按出现顺序保留。
    """
    sections: Dict[str, str] = {}
    current_title: Optional[str] = None
    buffer: List[str] = []

    def _flush() -> None:
        if current_title is not None:
            sections[current_title] = "\n".join(buffer).strip()
            buffer.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            _flush()
            current_title = stripped[3:].strip()
            continue
        if stripped.startswith("# ") and current_title is None:
            # 一级标题（如「# 东方仙侠正文提示卡」），忽略。
            continue
        if current_title is not None:
            buffer.append(line)

    _flush()
    return sections


def _extract_forbidden_elements(text: str) -> List[str]:
    """从「禁止漂移」小节提取 forbidden_elements（按「不要/禁止/不得」句式）。

    提取为空则返回空列表；原文仍在 ``prose.sections["禁止漂移"]`` 兜底，不丢数据。
    提取结果保留完整「不要 XXX」句式（含动词），供写作时作软约束参考。
    """
    if not text or not text.strip():
        return []
    elements: List[str] = []
    # 按句号/分号/换行切分，逐句找标记。
    clauses = re.split(r"[。；;\n]", text)
    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        for marker in FORBIDDEN_MARKERS:
            idx = clause.find(marker)
            if idx != -1:
                rest = clause[idx:].strip()
                if rest and 2 <= len(rest) <= 60:
                    elements.append(rest)
                break
    return elements


def _as_str_list(value: Any) -> List[str]:
    """把 frontmatter 的 aliases 等字段规范为字符串列表。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [str(value)]


def resolve_genre_id(name: str, fallback_id: Optional[str] = None) -> str:
    """由题材中文名确定性生成 ``meta.id``。

    优先查内置 32 项映射表；未命中时回退到显式传入的 ``fallback_id``，
    再兜底用题材名原样（不臆造拼音，避免与未来升格 id 冲突）。

    Args:
        name: 题材中文名（如 ``东方仙侠``）。
        fallback_id: 显式传入的 id（CLI ``--genre-id`` 覆盖用），可选。

    Returns:
        生成的 ``genre-<slug>`` id。
    """
    if name in GENRE_ID_MAP:
        return GENRE_ID_MAP[name]
    if fallback_id:
        return fallback_id
    return f"genre-{name}"


def build_genre_prose_card(
    frontmatter: Dict[str, Any],
    sections: Dict[str, str],
    genre_id: str,
) -> Dict[str, Any]:
    """组装 genre-prose-card dict（按架构文档 3.1/1.2 节映射规则）。

    Args:
        frontmatter: 解析后的 frontmatter dict。
        sections: 动态收集的 ``{标题: 内容}``。
        genre_id: ``meta.id``。

    Returns:
        符合 genre-prose-card.schema.json 结构的 dict。
    """
    name = str(frontmatter.get("genre", "") or "").strip()
    sub_tags = _as_str_list(frontmatter.get("aliases"))
    platform = str(frontmatter.get("platform", "") or "").strip()
    confidence = _confidence_map(frontmatter.get("confidence"))

    forbidden_elements = _extract_forbidden_elements(sections.get("禁止漂移", ""))
    voice_notes = sections.get("对话与声线", "")
    hook_notes = "\n\n".join(
        p for p in (sections.get("章尾钩子", ""), sections.get("正文落点", "")) if p
    )
    arc_rhythm_notes = "\n\n".join(
        p for p in (sections.get("节奏密度", ""), sections.get("前中后期打法", "")) if p
    )
    payoff_notes = sections.get("爽点与情绪释放", "")
    evidence = sections.get("证据摘要", "")

    meta: Dict[str, Any] = {
        "id": genre_id,
        "name": name or genre_id,
        "kind": "genre-prose-card",
        "sub_tags": sub_tags,
        "target_platform": platform,
        "confidence": confidence,
        "upgrade_status": "seed",
        "provenance": {
            "source": PROVENANCE_SOURCE,
            "license": PROVENANCE_LICENSE,
            "verified": False,
            "evidence": evidence,
            "converted_at": _now_iso(),
        },
        "source_books": [],  # 占位，升格时由范文拆书填充。
    }

    language_rules: Dict[str, Any] = {
        "forbidden_elements": forbidden_elements,
        "banned_phrases": [],
        "voice_notes": voice_notes,
    }

    # structure / commercial 仅在定性描述非空时附带（避免注入空段）。
    structure: Dict[str, Any] = {}
    if hook_notes:
        structure["hook_notes"] = hook_notes
    if arc_rhythm_notes:
        structure["arc_rhythm_notes"] = arc_rhythm_notes

    commercial: Dict[str, Any] = {}
    if payoff_notes:
        commercial["payoff_notes"] = payoff_notes

    card: Dict[str, Any] = {
        "meta": meta,
        "language_rules": language_rules,
        "prose": {"sections": sections},
    }
    if structure:
        card["structure"] = structure
    if commercial:
        card["commercial"] = commercial
    return card


def import_cards(
    src_dir: Path,
    out_dir: Path,
    genre_id_override: Optional[str] = None,
) -> Tuple[List[str], List[str], List[str], Dict[str, Dict[str, str]]]:
    """扫描源目录，逐卡转换落库。

    Args:
        src_dir: 源 ``*.md`` 目录。
        out_dir: 落库目录（``assets/``）。
        genre_id_override: 可选，统一覆盖所有卡的 id（仅调试用，一般不传）。

    Returns:
        ``(success, skipped, failed, index)``，其中 index 为
        ``{题材名: {"id": ..., "file": ...}}``。
    """
    if not src_dir.exists():
        return [], [], [f"源目录不存在: {src_dir}"], {}

    md_files = sorted(src_dir.glob("*.md"))
    if not md_files:
        return [], [], [f"源目录无 *.md 文件: {src_dir}"], {}

    out_dir.mkdir(parents=True, exist_ok=True)

    success: List[str] = []
    skipped: List[str] = []
    failed: List[str] = []
    index: Dict[str, Dict[str, str]] = {}

    for md_path in md_files:
        name = md_path.stem
        try:
            md_text = md_path.read_text(encoding="utf-8")
        except OSError as e:
            failed.append(f"{name}: 读取失败 {e}")
            continue

        frontmatter, body = load_frontmatter(md_text)
        if not frontmatter:
            skipped.append(f"{name}: 无 frontmatter，跳过")
            continue

        sections = parse_sections(body)
        if not sections:
            failed.append(f"{name}: 未解析出任何 ## 小节")
            continue

        genre_id = resolve_genre_id(name, genre_id_override)
        card = build_genre_prose_card(frontmatter, sections, genre_id)

        out_path = out_dir / f"genre-prose-card-{genre_id}.json"
        try:
            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(card, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        except OSError as e:
            failed.append(f"{name}: 写库失败 {e}")
            continue

        success.append(f"{name} → {out_path.name}")
        index[name] = {"id": genre_id, "file": out_path.name}

    return success, skipped, failed, index


def write_index(index: Dict[str, Dict[str, str]], out_dir: Path) -> Path:
    """写出 ``genre-prose-card-index.json`` 索引。"""
    out_path = out_dir / "genre-prose-card-index.json"
    payload: Dict[str, Any] = {
        "_description": "题材文风卡索引：题材中文名 → id / 落库文件名。",
        "_count": len(index),
        "cards": index,
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return out_path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="oh-story 题材文风卡 → genre-prose-card 轻量资产批量转换器",
    )
    parser.add_argument(
        "--src",
        required=True,
        help="源 *.md 目录（genre-prose-cards）",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="落库目录（默认 assets/）",
    )
    parser.add_argument(
        "--genre-id",
        help="可选：统一覆盖所有卡的 meta.id（调试用，一般勿用）",
    )
    args = parser.parse_args(argv)

    success, skipped, failed, index = import_cards(
        Path(args.src), Path(args.out), args.genre_id
    )

    # 汇总打印。
    print("=" * 60)
    print(f"转换完成：成功 {len(success)} / 跳过 {len(skipped)} / 失败 {len(failed)}")
    print("=" * 60)
    if success:
        print("\n[成功]")
        for s in success:
            print(f"  ✓ {s}")
    if skipped:
        print("\n[跳过]")
        for s in skipped:
            print(f"  - {s}")
    if failed:
        print("\n[失败]")
        for f in failed:
            print(f"  ✗ {f}")

    if index:
        idx_path = write_index(index, Path(args.out))
        print(f"\n[索引] {idx_path}（{len(index)} 条）")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
