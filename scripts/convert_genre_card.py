#!/usr/bin/env python3
"""体裁散文卡 → genre-pack 规则包转换器（纯标准库）。

.. deprecated::
    本脚本已弃用。它会把散文卡转成「空壳 genre-pack」（``chapter_word_range: {}``、
    ``chapter_roles: []``、``frequency: null``、``buildup_length: null`` 等占位空值），
    缺 ``iron_rules`` 且无有效 ``payoff_density``，无法通过 genre-pack 严格校验
    （auto_kind 兜底误判为 voice-card，报大量硬错误）。

    散文卡应改用 ``import_genre_prose_cards.py`` 转成 **genre-prose-card**（通用、
    产出正确的轻量种子卡），而非 genre-pack。本脚本保留仅为历史留档与
    ``novel.py`` 的 ``convert-genre-card`` 子命令引用；运行时将显式报错退出。

把 ``reference/oh-story/genre-prose-card_<题材>.md`` 这类「散文体体裁提示卡」
（YAML frontmatter + 13 个 ``##`` 小节）转换为符合 ``schema/genre-pack.schema.json``
的结构化 JSON 规则包。

设计要点：

* 散文卡是「提示性散文」，规则包是「结构化枚举」。本转换器做的是**启发式映射**：
  从散文段落中抽取可结构化信息（钩子类型、爽点类型、节奏密度、语言铁律等），
  其余无法可靠结构化的字段**留空**（不臆造数值）。
* 输出 JSON 的 ``meta`` 额外携带 ``schema_version``（int=1）与 ``converted_at``
  （ISO 8601），供下游幂等判断。
* 幂等覆盖：``--force`` 时若目标文件已存在且 ``schema_version`` 相同则跳过，
  避免重复转换污染现有规则包。

用法（已弃用，运行会退出）：:

    python scripts/convert_genre_card.py \\
        --input reference/oh-story/genre-prose-card_青春甜宠.md \\
        --output assets/genre-youth-romance-pack.json \\
        --genre-id genre-youth-romance

替代方案：:

    python scripts/import_genre_prose_cards.py ...
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 允许作为脚本独立运行，也允许被 novel.py 子进程调用（cwd 为项目根）。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from yaml_lite import load_frontmatter  # noqa: E402

# 13 个 ``##`` 小节的规范标题（按散文卡出现顺序）。
_SECTION_TITLES = (
    "正文提示词",
    "开场抓手",
    "冲突发动机",
    "爽点与情绪释放",
    "对话与声线",
    "章尾钩子",
    "场景颗粒",
    "正文落点",
    "前中后期打法",
    "节奏密度",
    "本章取舍",
    "禁止漂移",
    "证据摘要",
)

# 钩子类型枚举映射：散文卡「章尾钩子 / 正文落点」里的关键词 → 规则包 hook_types.type。
# 值仅使用 genre-pack.schema.json 已有枚举 + 本任务新增的青春甜宠枚举。
_HOOK_KEYWORD_MAP: List[Tuple[str, str]] = [
    ("误会升级", "误会升级"),
    ("甜蜜瞬间", "甜蜜瞬间"),
    ("暧昧拉扯", "暧昧拉扯"),
    ("未发出", "信息断点"),
    ("消息", "信息断点"),
    ("家长发现", "危机降临"),
    ("家长", "危机降临"),
    ("考试", "危机降临"),
    ("比赛", "危机降临"),
    ("围观", "对手登场"),
    ("起哄", "对手登场"),
    ("公开", "身份反转"),
    ("新座位", "悬念揭示"),
    ("新分组", "悬念揭示"),
    ("约定", "悬念揭示"),
    ("关系", "情感冲击"),
]

# 爽点类型枚举映射：散文卡「爽点与情绪释放」关键词 → payoff_types.type。
_PAYOFF_KEYWORD_MAP: List[Tuple[str, str]] = [
    ("维护", "他人认可"),
    ("补课", "情感回应"),
    ("帮忙", "情感回应"),
    ("称呼变化", "情感回应"),
    ("置顶", "情感回应"),
    ("低头", "情感回应"),
    ("公开", "身份揭露"),
    ("认可", "他人认可"),
    ("惩罚", "他人认可"),
]


def _now_iso() -> str:
    """返回带时区标记的 ISO 8601 时间戳（UTC）。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_sections(body: str) -> Dict[str, str]:
    """把 markdown 正文按 ``## 标题`` 切成 ``{标题: 内容}``。

    Args:
        body: frontmatter 之后的 markdown 正文。

    Returns:
        以 13 个规范标题为 key 的字典（未出现的 section 值为空字符串）。
    """
    sections: Dict[str, str] = {title: "" for title in _SECTION_TITLES}
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
            title = stripped[3:].strip()
            current_title = title if title in sections else title
            if current_title not in sections:
                sections[current_title] = ""
            continue
        if stripped.startswith("# ") and current_title is None:
            # 一级标题（如「# 青春甜宠正文提示卡」），忽略。
            continue
        buffer.append(line)

    _flush()
    return sections


def _confidence_map(level: str) -> float:
    """frontmatter ``confidence`` 字符串 → 0~1 数值。"""
    mapping = {"high": 0.85, "medium": 0.65, "low": 0.4}
    if isinstance(level, (int, float)):
        return float(level)
    return mapping.get(str(level).lower(), 0.5)


def _extract_hook_types(
    sections: Dict[str, str]
) -> List[Dict[str, Any]]:
    """从「章尾钩子」「正文落点」抽取 hook_types（启发式，留空则返回 []）。"""
    text = sections.get("章尾钩子", "") + "\n" + sections.get("正文落点", "")
    if not text.strip():
        return []

    found: List[Dict[str, Any]] = []
    seen: set = set()
    for keyword, hook_type in _HOOK_KEYWORD_MAP:
        if keyword in text and hook_type not in seen:
            seen.add(hook_type)
            found.append(
                {
                    "type": hook_type,
                    "frequency": None,
                    "strength": None,
                    "skeleton": "",
                }
            )
    return found


def _extract_payoff_types(
    sections: Dict[str, str]
) -> List[Dict[str, Any]]:
    """从「爽点与情绪释放」抽取 payoff_types（启发式，留空则返回 []）。"""
    text = sections.get("爽点与情绪释放", "")
    if not text.strip():
        return []

    found: List[Dict[str, Any]] = []
    seen: set = set()
    for keyword, payoff_type in _PAYOFF_KEYWORD_MAP:
        if keyword in text and payoff_type not in seen:
            seen.add(payoff_type)
            found.append(
                {
                    "type": payoff_type,
                    "ratio": None,
                    "buildup_length": None,
                    "skeleton": "",
                }
            )
    return found


def _extract_banned_phrases(text: str) -> List[str]:
    """从「禁止漂移」提取禁用词/禁用倾向（粗略，仅当明确动词短语出现）。"""
    if not text.strip():
        return []
    phrases: List[str] = []
    # 散文卡的「不要/禁止」句，抽取「不要 XXX」作为禁用倾向描述。
    for clause in text.replace("；", "。").replace("，", "。").split("。"):
        clause = clause.strip()
        for marker in ("不要", "禁止", "不得"):
            idx = clause.find(marker)
            if idx != -1:
                rest = clause[idx + len(marker) :].strip()
                if rest and 2 <= len(rest) <= 20:
                    phrases.append(rest)
                break
    return phrases


def _extract_required_elements(text: str) -> List[str]:
    """从「正文提示词」「节奏密度」抽取题材必备要素（启发式）。"""
    if not text.strip():
        return []
    # 青春甜宠类必备要素，基于散文卡语义硬编码兜底（仅当文本无更多信息时）。
    return ["校园/同学/家庭等青春场景", "关系每章有可见推进"]


def build_genre_pack(
    frontmatter: Dict[str, Any], sections: Dict[str, str], genre_id: str
) -> Dict[str, Any]:
    """组装 genre-pack JSON。

    Args:
        frontmatter: 解析后的 frontmatter dict。
        sections: 13 section 标题 → 内容 dict。
        genre_id: 输出 ``meta.id``（如 ``genre-youth-romance``）。

    Returns:
        符合 genre-pack.schema.json 结构的 dict。
    """
    name = str(frontmatter.get("genre", "") or "")
    aliases = frontmatter.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    platform = str(frontmatter.get("platform", "") or "")
    confidence = _confidence_map(frontmatter.get("confidence", "medium"))
    source = str(frontmatter.get("source", "") or "")

    hook_types = _extract_hook_types(sections)
    payoff_types = _extract_payoff_types(sections)
    banned = _extract_banned_phrases(sections.get("禁止漂移", ""))
    required = _extract_required_elements(sections.get("正文提示词", ""))

    return {
        "meta": {
            "id": genre_id,
            "name": name or genre_id,
            "sub_tags": [a for a in aliases if a],
            "source_books": [],  # 散文卡无单本来源明细，留空。
            "target_platform": platform or "",
            "confidence": confidence,
            # 转换器附加字段（非 schema 必需，供幂等判断）。
            "schema_version": 1,
            "converted_at": _now_iso(),
            "converted_from": source or "",
        },
        "structure": {
            "chapter_word_range": {},
            "chapter_roles": [],
            "hook_system": {
                "hook_types": hook_types,
                "hook_density_curve": [],
                "anti_repetition_rule": "",
            },
            "foreshadow_pattern": {},
            "arc_rhythm": {},
        },
        "commercial": {
            "payoff_density": {
                "per_thousand_words": None,
                "payoff_types": payoff_types,
                "dry_spell_tolerance": None,
            },
            "opening_analysis": {},
        },
        "language_rules": {
            "iron_rules": [],
            "banned_phrases": banned,
            "fatigue_words": [],
            "required_elements": required,
            "forbidden_elements": [],
        },
    }


def _load_existing(output_path: Path) -> Optional[Dict[str, Any]]:
    """读取已存在的输出文件（不存在或损坏返回 None）。"""
    if not output_path.exists():
        return None
    try:
        with output_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def convert(
    input_path: Path,
    output_path: Path,
    genre_id: str,
    force: bool = False,
) -> Tuple[bool, str]:
    """执行转换，返回 ``(是否写出, 说明)``。

    Args:
        input_path: 源散文卡 markdown 路径。
        output_path: 目标 JSON 路径。
        genre_id: meta.id。
        force: 是否幂等覆盖（已存在且同 schema_version 时跳过）。

    Returns:
        ``(wrote, reason)``；``wrote`` 为 True 表示实际写出（或跳过无需写），
        ``reason`` 描述本次动作。
    """
    if not input_path.exists():
        return False, f"输入文件不存在: {input_path}"

    md_text = input_path.read_text(encoding="utf-8")
    frontmatter, body = load_frontmatter(md_text)
    sections = parse_sections(body)
    pack = build_genre_pack(frontmatter, sections, genre_id)

    if force and output_path.exists():
        existing = _load_existing(output_path)
        existing_version = (
            existing.get("meta", {}).get("schema_version") if existing else None
        )
        if existing_version == 1:
            return False, (
                f"已存在且 schema_version=1，幂等跳过（--force）: {output_path}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return True, f"已写出: {output_path}"


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="体裁散文卡 → genre-pack 规则包转换器",
    )
    parser.add_argument("--input", required=True, help="源散文卡 markdown 路径")
    parser.add_argument("--output", required=True, help="目标 JSON 路径")
    parser.add_argument("--genre-id", required=True, help="meta.id，如 genre-youth-romance")
    parser.add_argument(
        "--force",
        action="store_true",
        help="幂等覆盖：已存在且同 schema_version 则跳过",
    )
    args = parser.parse_args(argv)

    # 失效引导：本脚本已弃用，运行即显式报错退出，不再产出误导性空壳 genre-pack。
    print(
        "错误：convert_genre_card.py 已弃用，不再执行转换。\n"
        "原因：它会把散文卡转成「空壳 genre-pack」（chapter_word_range 为空、\n"
        "chapter_roles 为空、frequency/buildup_length/per_thousand_words 为 null），\n"
        "缺少 iron_rules 且无有效 payoff_density，无法通过 genre-pack 严格校验。\n"
        "\n"
        "替代方案：散文卡应转成 genre-prose-card 而非 genre-pack，请改用：\n"
        "    python scripts/import_genre_prose_cards.py ...\n"
        "\n"
        "本脚本保留仅为历史留档与 novel.py 的 convert-genre-card 子命令引用。",
        file=sys.stderr,
    )
    return 1

    wrote, reason = convert(
        input_path=Path(args.input),
        output_path=Path(args.output),
        genre_id=args.genre_id,
        force=args.force,
    )
    print(reason)
    return 0 if wrote else 1


if __name__ == "__main__":
    sys.exit(main())
