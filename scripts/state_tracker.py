#!/usr/bin/env python3
"""长文本状态追踪核心（纯函数式，纯标准库：json + os + re）。

借鉴 oh-story 的「结构化权威状态 + 确定性派生视图」设计，为 novel-lab 提供
长篇续写时的连续性状态追踪：

* 权威层：``_tracking-state.json``，维护 ``state_revision``（单调递增的修订号）、
  角色快照、伏笔、时间线、上下文与下一章承诺。
* 事务提交：``apply_transaction`` 应用「逐章事务」到权威状态，用
  ``expected_state_revision`` 拒绝基于旧状态构造的 stale 事务。
* 注入上下文：``build_injection_context`` 从权威状态生成「续写状态卡」式只读片段，
  供 inject.py 注入写作 prompt（角色快照 + 活跃伏笔 + 近 3 章速记 + 下一章承诺）。
* 修订校验：``validate_revision`` 校验 ``expected_state_revision`` 是否与当前状态一致。

容量约束（与 tracking-transaction.md 对齐）：

* 角色快照单文件目标 ≤4096 字节，超 4096 警告；硬上限 8192 字节，超限拒绝写入。
  字节数用 ``len(text.encode('utf-8'))`` 计算。
* ``active_character_names`` 最多 6 人。
* 活跃伏笔确定性选取最多 8 条。
* 近章速记只保留 3 章。
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

SNAPSHOT_WARN_BYTES = 4096  # 角色快照目标字节上限（超出警告）。
SNAPSHOT_HARD_BYTES = 8192  # 角色快照硬字节上限（超出拒绝）。
MAX_ACTIVE_CHARACTERS = 6   # 活跃角色上限。
MAX_ACTIVE_FORESHAWDS = 8   # 活跃伏笔上限。
MAX_RECENT_CHAPTERS = 3     # 近章速记保留章数。
CONTEXT_CARD_MAX_BYTES = 12288  # 续写状态卡固定 7 区块目标上限（参考值，软约束）。

_SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _utf8_bytes(text: str) -> int:
    """计算字符串 UTF-8 编码字节数。"""
    return len(text.encode("utf-8"))


def _snapshot_bytes(snapshot: Dict[str, Any]) -> int:
    """计算单个角色快照序列化后的字节数。"""
    return _utf8_bytes(json.dumps(snapshot, ensure_ascii=False))


def _is_retired_status(status: str) -> bool:
    """判断伏笔状态是否「已回收/已作废」——非活跃伏笔。"""
    return status in ("已回收", "已作废", "回收", "作废")


def _validate_snapshot_limits(
    character_snapshots: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """校验角色快照字节限制，返回 ``(是否通过, 警告列表)``。

    Returns:
        ``(ok, warnings)``。``ok`` 为 False 表示存在超硬上限（8192 字节）的快照，
        必须拒绝写入；``warnings`` 为超目标上限（4096 字节）的快照名列表。
    """
    warnings: List[str] = []
    for name, snapshot in character_snapshots.items():
        size = _snapshot_bytes(snapshot)
        if size > SNAPSHOT_HARD_BYTES:
            return False, [f"角色快照「{name}」{size} 字节超硬上限 {SNAPSHOT_HARD_BYTES}"]
        if size > SNAPSHOT_WARN_BYTES:
            warnings.append(f"角色快照「{name}」{size} 字节超目标上限 {SNAPSHOT_WARN_BYTES}")
    return True, warnings


# ---------------------------------------------------------------------------
# 权威状态读写
# ---------------------------------------------------------------------------

def _empty_state(book_title: str = "") -> Dict[str, Any]:
    """构造空的权威状态骨架。"""
    return {
        "schema_version": _SCHEMA_VERSION,
        "book_title": book_title,
        "last_chapter": 0,
        "state_revision": 0,
        "context": {
            "position": {},
            "long_term_constraints": [],
            "active_character_names": [],
            "continuity_risks": [],
            "recent_chapters": [],
            "next_chapter_commitments": [],
        },
        "character_snapshots": {},
        "foreshadow": [],
        "timeline_events": [],
    }


def load_state(state_path: str | os.PathLike) -> Dict[str, Any]:
    """读取权威状态文件；不存在时返回空状态。"""
    path = Path(state_path)
    if not path.exists():
        return _empty_state()
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state(state: Dict[str, Any], state_path: str | os.PathLike) -> None:
    """原子写回权威状态文件（先写临时文件再替换）。"""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 核心函数：apply_transaction
# ---------------------------------------------------------------------------

def apply_transaction(
    state: Dict[str, Any],
    transaction: Dict[str, Any],
    state_path: Optional[str | os.PathLike] = None,
) -> Dict[str, Any]:
    """应用一次逐章事务到权威状态，返回更新后的 state。

    幂等且无副作用（除非传入 ``state_path`` 则原子写回磁盘）。

    Args:
        state: 当前权威状态 dict（可由 :func:`load_state` 读入）。
        transaction: 逐章事务 dict，遵循 tracking-transaction.md 协议。
            关键字段：``mode``(init/append/revision)、``chapter``、
            ``chapter_title``、``expected_state_revision``、``delta``、
            ``context``、``character_snapshots``。
            init 事务另可直接携带顶层 ``foreshadow`` / ``timeline_events``
            （整份当前值，非 delta 式变更）；append/revision 则通过
            ``delta.foreshadow_changes`` / ``delta.timeline_events``
            以 upsert/delete 语义更新。
        state_path: 可选，传入时校验通过后原子写回该路径。

    Returns:
        更新后的 state dict。

    Raises:
        ValueError: 校验失败（stale 修订号、超容量、字段非法等），不写入。
    """
    schema_version = transaction.get("schema_version", _SCHEMA_VERSION)
    if schema_version != _SCHEMA_VERSION:
        raise ValueError(f"不支持的 schema_version: {schema_version}")

    mode = transaction.get("mode", "append")
    if mode not in ("init", "append", "revision"):
        raise ValueError(f"非法 mode: {mode}")

    # 1. 修订号校验（stale 防护）。init 时 state_revision 恒为 0。
    current_revision = state.get("state_revision", 0)
    if mode == "init":
        expected = 0
    else:
        expected = transaction.get("expected_state_revision")
        if expected is None:
            raise ValueError("append/revision 事务缺少 expected_state_revision")
        if not isinstance(expected, int):
            raise ValueError("expected_state_revision 必须为整数")
    if expected != current_revision:
        raise ValueError(
            f"stale 事务：expected_state_revision={expected} "
            f"但当前 state_revision={current_revision}"
        )

    # 2. 角色快照容量校验（硬上限，超限拒绝）。
    snapshots = transaction.get("character_snapshots", {})
    ok, warnings = _validate_snapshot_limits(snapshots)
    if not ok:
        raise ValueError(warnings[0])
    # 警告仅打印，不阻断。
    for w in warnings:
        print(f"[state_tracker] 警告: {w}")

    # 3. 活跃角色上限校验。
    active_names = transaction.get("context", {}).get("active_character_names", [])
    if not isinstance(active_names, list):
        raise ValueError("context.active_character_names 必须为列表")
    if len(active_names) > MAX_ACTIVE_CHARACTERS:
        raise ValueError(
            f"活跃角色 {len(active_names)} 人超上限 {MAX_ACTIVE_CHARACTERS}"
        )
    # 活跃角色必须已有快照（init 除外，init 可先建快照）。
    if mode != "init":
        existing_snapshots = set(state.get("character_snapshots", {}).keys())
        new_snapshots = set(snapshots.keys())
        merged = existing_snapshots | new_snapshots
        missing = [n for n in active_names if n not in merged]
        if missing:
            raise ValueError(f"活跃角色缺快照: {missing}")

    # 4. 应用 delta 到状态。
    delta = transaction.get("delta", {})
    result_state = _apply_delta(state, delta, mode)

    # 4b. init 事务直接提交顶层 foreshadow / timeline_events 的「当前行」。
    #     协议（tracking-transaction.md 导入初始化示例）规定：init 时顶层
    #     foreshadow、timeline_events 为伏笔与时间线事件的整份当前值（非 delta
    #     式变更），必须合并进状态；否则会被静默丢弃。append/revision 则走 delta
    #     内的 foreshadow_changes / timeline_events（upsert/delete 语义）。
    if mode == "init":
        for field in ("foreshadow", "timeline_events"):
            if field in transaction:
                value = transaction[field]
                if value is None:
                    result_state[field] = []
                elif isinstance(value, list):
                    result_state[field] = value
                else:
                    raise ValueError(f"init 事务的 {field} 必须为列表或 null")

    # 5. 更新 context（init 收六项，commit 收前四项；其余由工具派生）。
    ctx_in = transaction.get("context", {})
    ctx = result_state.setdefault("context", {})
    for field in ("position", "long_term_constraints", "active_character_names", "continuity_risks"):
        if field in ctx_in:
            ctx[field] = ctx_in[field]
    # recent_chapters 与 next_chapter_commitments：init 直接采用输入；append 由 delta 派生。
    if mode == "init":
        if "recent_chapters" in ctx_in:
            ctx["recent_chapters"] = ctx_in["recent_chapters"]
        if "next_chapter_commitments" in ctx_in:
            ctx["next_chapter_commitments"] = ctx_in["next_chapter_commitments"]
    else:
        ctx["recent_chapters"] = _derive_recent_chapters(state, transaction, result_state)
        # 只在 delta 显式包含该键时才覆盖，避免静默清空已有承诺
        if "next_chapter_commitments" in delta:
            ctx["next_chapter_commitments"] = delta["next_chapter_commitments"]

    # 6. 更新角色快照（合并，非覆盖整体）。
    if snapshots:
        result_state.setdefault("character_snapshots", {})
        result_state["character_snapshots"].update(snapshots)

    # 7. 退役角色：删除其快照。
    for retired_name in delta.get("retired_characters", []):
        result_state.get("character_snapshots", {}).pop(retired_name, None)
        if retired_name in result_state.get("context", {}).get("active_character_names", []):
            result_state["context"]["active_character_names"].remove(retired_name)

    # 8. 推进修订号与最后章。
    result_state["state_revision"] = current_revision + 1
    chapter = transaction.get("chapter")
    if isinstance(chapter, int):
        result_state["last_chapter"] = max(result_state.get("last_chapter", 0), chapter)

    # 9. 原子写回（可选）。
    if state_path is not None:
        save_state(result_state, state_path)

    return result_state


def _apply_delta(
    state: Dict[str, Any], delta: Dict[str, Any], mode: str
) -> Dict[str, Any]:
    """把 delta 应用到状态的深拷贝上，返回新 state。"""
    import copy

    result = copy.deepcopy(state)

    # 伏笔变更（upsert / delete）。
    foreshadow = result.setdefault("foreshadow", [])
    foreshadow_index: Dict[str, int] = {
        f.get("id", ""): i for i, f in enumerate(foreshadow)
    }
    for change in delta.get("foreshadow_changes", []):
        action = change.get("action")
        fid = change.get("id")
        if action == "delete":
            if fid in foreshadow_index:
                foreshadow.pop(foreshadow_index[fid])
        else:  # upsert
            if fid in foreshadow_index:
                foreshadow[foreshadow_index[fid]] = change
            else:
                foreshadow.append(change)
        # 重建索引（长度可能变化）。
        foreshadow_index = {
            f.get("id", ""): i for i, f in enumerate(foreshadow)
        }

    # 时间线事件（upsert / delete）。
    timeline = result.setdefault("timeline_events", [])
    timeline_index: Dict[str, int] = {
        e.get("id", ""): i for i, e in enumerate(timeline)
    }
    for event in delta.get("timeline_events", []):
        action = event.get("action")
        eid = event.get("id")
        if action == "delete":
            if eid in timeline_index:
                timeline.pop(timeline_index[eid])
        else:
            if eid in timeline_index:
                timeline[timeline_index[eid]] = event
            else:
                timeline.append(event)
        timeline_index = {
            e.get("id", ""): i for i, e in enumerate(timeline)
        }

    # 退役上下文条目：从 context 的约束/风险中移除。
    if "retired_context_items" in delta:
        ctx = result.setdefault("context", {})
        for field in ("long_term_constraints", "continuity_risks"):
            cur = ctx.get(field, [])
            if isinstance(cur, list):
                ctx[field] = [x for x in cur if x not in delta["retired_context_items"]]

    return result


def _derive_recent_chapters(
    old_state: Dict[str, Any],
    transaction: Dict[str, Any],
    new_state: Dict[str, Any],
) -> List[Any]:
    """派生近章速记（最多 3 章）：合并旧近章 + 本章结果，截尾。"""
    old_recent = old_state.get("context", {}).get("recent_chapters", [])
    if not isinstance(old_recent, list):
        old_recent = []

    chapter = transaction.get("chapter")
    result = transaction.get("delta", {}).get("result", "")
    entry = {"chapter": chapter, "summary": result} if chapter is not None else None

    combined = list(old_recent)
    if entry is not None and result:
        combined.append(entry)

    # 去重（同章覆盖）。
    seen: Dict[int, int] = {}
    deduped: List[Any] = []
    for e in combined:
        ch = e.get("chapter") if isinstance(e, dict) else None
        if ch is not None:
            if ch in seen:
                deduped[seen[ch]] = e
            else:
                seen[ch] = len(deduped)
                deduped.append(e)
        else:
            deduped.append(e)

    return deduped[-MAX_RECENT_CHAPTERS:]


# ---------------------------------------------------------------------------
# 核心函数：build_injection_context
# ---------------------------------------------------------------------------

def build_injection_context(
    state: Dict[str, Any],
    max_characters: int = MAX_ACTIVE_CHARACTERS,
    max_foreshadows: int = MAX_ACTIVE_FORESHAWDS,
    max_recent: int = MAX_RECENT_CHAPTERS,
) -> str:
    """从权威状态生成「续写状态卡」式只读注入文本。

    包含 4 个信息块（字符快照 + 活跃伏笔 + 近 3 章速记 + 下一章承诺），
    供 inject.py 拼进写作 prompt（只读，不改写状态）。

    Args:
        state: 权威状态 dict。
        max_characters: 活跃角色上限（默认 6）。
        max_foreshadows: 活跃伏笔上限（默认 8）。
        max_recent: 近章速记保留章数（默认 3）。

    Returns:
        多行 markdown 文本；状态为空时返回空字符串。
    """
    ctx = state.get("context", {})
    if not ctx and not state.get("character_snapshots"):
        return ""

    blocks: List[str] = []
    blocks.append("## 长期状态追踪")

    # 1. 角色快照（活跃角色）。
    active_names = ctx.get("active_character_names", [])
    snapshots = state.get("character_snapshots", {})
    ordered_names: List[str] = []
    for name in active_names[:max_characters]:
        if name in snapshots:
            ordered_names.append(name)
    # 活跃名单不足时，补齐快照里存在的角色。
    for name in snapshots:
        if name not in ordered_names and len(ordered_names) < max_characters:
            ordered_names.append(name)

    if ordered_names:
        lines = ["### 角色快照"]
        for name in ordered_names:
            snap = snapshots[name]
            lines.append(f"- **{name}**")
            for key, label in (
                ("identity", "身份"),
                ("location", "位置"),
                ("goal", "当前目标"),
                ("state", "身心状态"),
            ):
                if snap.get(key):
                    lines.append(f"  - {label}：{snap[key]}")
            for key, label in (
                ("abilities_resources", "能力与资源"),
                ("relationships", "关键关系"),
                ("knowledge", "已知信息"),
                ("open_threads", "未结事项"),
            ):
                val = snap.get(key)
                if isinstance(val, list) and val:
                    lines.append(f"  - {label}：" + "；".join(str(v) for v in val))
                elif val:
                    lines.append(f"  - {label}：{val}")
        blocks.append("\n".join(lines))

    # 2. 活跃伏笔（未回收/未作废，最多 8 条）。
    foreshadows = state.get("foreshadow", [])
    active_fs = [
        f for f in foreshadows if not _is_retired_status(f.get("status", ""))
    ][:max_foreshadows]
    if active_fs:
        lines = ["### 活跃伏笔"]
        for f in active_fs:
            lines.append(f"- [{f.get('id', '?')}] {f.get('summary', '')}")
        blocks.append("\n".join(lines))

    # 3. 近三章速记。
    recent = ctx.get("recent_chapters", [])
    if isinstance(recent, list) and recent:
        lines = ["### 近三章速记"]
        for e in recent[-max_recent:]:
            if isinstance(e, dict):
                ch = e.get("chapter", "?")
                summary = e.get("summary", "")
                lines.append(f"- 第{ch}章：{summary}")
            else:
                lines.append(f"- {e}")
        blocks.append("\n".join(lines))

    # 4. 下一章承诺。
    commitments = ctx.get("next_chapter_commitments", [])
    if isinstance(commitments, list) and commitments:
        lines = ["### 下一章承诺"]
        lines += [f"- {c}" for c in commitments]
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# 核心函数：validate_revision
# ---------------------------------------------------------------------------

def validate_revision(
    state: Dict[str, Any],
    expected_state_revision: int,
) -> Tuple[bool, str]:
    """校验 ``expected_state_revision`` 是否与当前状态修订号一致。

    Args:
        state: 当前权威状态 dict。
        expected_state_revision: 事务声明的期望修订号。

    Returns:
        ``(是否通过, 说明)``。一致返回 ``(True, ...)``；不一致返回
        ``(False, 原因)``，提示调用方重新读取 state 并重构事务。
    """
    current = state.get("state_revision", 0)
    if expected_state_revision == current:
        return True, f"修订号一致（state_revision={current}）"
    return False, (
        f"stale：expected_state_revision={expected_state_revision} "
        f"但当前 state_revision={current}，请重新读取 state 并重构事务"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="长文本状态追踪：读/写状态、应用事务、校验修订号",
        prog="state_tracker",
    )
    sub = parser.add_subparsers(dest="cmd", help="子命令")

    p_show = sub.add_parser("show", help="读取并打印权威状态")
    p_show.add_argument("--state", required=True, help="_tracking-state.json 路径")

    p_apply = sub.add_parser("apply", help="应用逐章事务")
    p_apply.add_argument("--state", required=True, help="_tracking-state.json 路径")
    p_apply.add_argument("--transaction", required=True, help="逐章事务 JSON 路径")

    p_validate = sub.add_parser("validate", help="校验 expected_state_revision")
    p_validate.add_argument("--state", required=True, help="_tracking-state.json 路径")
    p_validate.add_argument("--expected-revision", type=int, required=True)

    p_context = sub.add_parser("context", help="生成续写状态卡注入文本")
    p_context.add_argument("--state", required=True, help="_tracking-state.json 路径")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 入口。"""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0

    if args.cmd == "show":
        state = load_state(args.state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "apply":
        state = load_state(args.state)
        with Path(args.transaction).open("r", encoding="utf-8") as fh:
            transaction = json.load(fh)
        try:
            new_state = apply_transaction(state, transaction, state_path=args.state)
        except ValueError as exc:
            print(f"[state_tracker] 错误: {exc}")
            return 2
        print(f"已提交，state_revision={new_state['state_revision']}")
        return 0

    if args.cmd == "validate":
        state = load_state(args.state)
        ok, reason = validate_revision(state, args.expected_revision)
        print(reason)
        return 0 if ok else 1

    if args.cmd == "context":
        state = load_state(args.state)
        text = build_injection_context(state)
        print(text)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
