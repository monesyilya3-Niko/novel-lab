#!/usr/bin/env python3
"""手写轻量 YAML frontmatter 解析器（纯标准库，零第三方依赖）。

只解析 genre-prose-card 这类小说体裁卡片的 frontmatter 所需的最小 YAML 子集：

* ``key: value`` 标量行（值可为字符串、整数、浮点数、布尔字面量，或被引号包裹）。
* ``key:`` 后跟缩进的 ``- item`` 列表行（列表项可为标量，或 ``k: v`` 内联映射）。
* 顶层 ``- item`` 列表行（无 key 前缀，用于纯列表 frontmatter）。
* 注释行（``#`` 开头）与空行自动忽略。

不支持嵌套映射、多行字符串、锚点/别名、显式 tag 等高级 YAML 特性 ——
它们超出体裁卡片 frontmatter 的需求范围，遇到时按最保守方式处理（整行视为字面量）。

用法示例：:

    from yaml_lite import parse_yaml
    data = parse_yaml("genre: 青春甜宠\\naliases: [青春甜宠, 校园甜宠]\\n")
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# 标量字面量正则（支持被单/双引号包裹的值，去引号后返回）。
_QUOTED_RE = re.compile(r'^([\'"])(.*)\1$', re.DOTALL)

# 内联列表形如 ``[a, b, c]`` 或 ``[a, "b", c]``。
_INLINE_LIST_RE = re.compile(r'^\[(.*)\]$', re.DOTALL)

# 内联映射形如 ``{a: 1, b: 2}``。
_INLINE_MAP_RE = re.compile(r'^\{(.*)\}$', re.DOTALL)


def _strip_comment(line: str) -> str:
    """去除行内注释（``#`` 起，但保留引号内的 ``#``）。"""
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:idx].rstrip()
    return line.rstrip()


def _unquote(text: str) -> str:
    """去除首尾引号（若有），并解转义常用序列。"""
    text = text.strip()
    m = _QUOTED_RE.match(text)
    if m:
        text = m.group(2)
    # 常见转义（YAML 双引号字符串子集）。
    text = text.replace(r"\n", "\n").replace(r"\t", "\t").replace(r"\"", '"').replace(r"\'", "'")
    return text


def _parse_scalar(raw: str) -> Any:
    """把标量字符串解析为 Python 原生类型。"""
    text = _unquote(raw.strip())
    if text == "":
        return ""
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "none", "~"):
        return None
    # 整数。
    if re.fullmatch(r"[-+]?\d+", text):
        try:
            return int(text)
        except ValueError:
            pass
    # 浮点数。
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", text):
        try:
            return float(text)
        except ValueError:
            pass
    return text


def _split_inline_list(body: str) -> List[str]:
    """按逗号切分内联列表体（尊重引号内的逗号）。"""
    parts: List[str] = []
    buf = ""
    in_single = False
    in_double = False
    for ch in body:
        if ch == "'" and not in_double:
            in_single = not in_single
            buf += ch
        elif ch == '"' and not in_single:
            in_double = not in_double
            buf += ch
        elif ch == "," and not in_single and not in_double:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts


def _parse_value(raw: str) -> Any:
    """解析单个 ``:`` 后的值（标量 / 内联列表 / 内联映射）。"""
    text = raw.strip()
    if text == "":
        return ""
    # 内联列表 [a, b, c]
    m = _INLINE_LIST_RE.match(text)
    if m:
        items = _split_inline_list(m.group(1))
        # 空列表 ``[]`` 视为空字符串（genre 卡 frontmatter 不使用空列表）。
        if len(items) == 1 and items[0] == "":
            return []
        return [_parse_scalar(i) for i in items if i != ""]
    # 内联映射 {a: 1, b: 2}
    m = _INLINE_MAP_RE.match(text)
    if m:
        result: Dict[str, Any] = {}
        for kv in _split_inline_list(m.group(1)):
            if ":" in kv:
                k, v = kv.split(":", 1)
                result[_unquote(k.strip())] = _parse_scalar(v)
            else:
                result[kv.strip()] = True
        return result
    return _parse_scalar(text)


def _split_key_value(line: str) -> Tuple[Optional[str], Optional[str]]:
    """把一行拆成 ``(key, value)``，无 ``:`` 时返回 ``(None, None)``。

    尊重引号内的冒号，避免把 ``http://`` 或带冒号的字符串拆坏。
    """
    in_single = False
    in_double = False
    for idx, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ":" and not in_single and not in_double:
            key = line[:idx].strip()
            value = line[idx + 1 :].strip()
            return key, value
    return None, None


def parse_yaml(text: str) -> Any:
    """解析 YAML 子集，返回 ``dict`` 或 ``list``。

    Args:
        text: 原始 YAML 文本（通常是 markdown 文件开头的 frontmatter 块）。

    Returns:
        解析结果：顶层为映射时返回 ``dict``，为列表时返回 ``list``。
        空输入返回空 ``dict``。
    """
    lines = text.splitlines()
    result: Dict[str, Any] = {}
    # 当前正在填充的列表所属 key（``key:`` 后紧跟 ``- item`` 时）。
    current_list_key: Optional[str] = None
    # 顶层纯列表（无 key）时的累积列表。
    top_list: Optional[List[Any]] = None

    for raw_line in lines:
        line = _strip_comment(raw_line)
        if not line.strip():
            continue

        # 检测缩进：体裁卡 frontmatter 的列表项用两空格缩进。
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped.startswith("- "):
            item_raw = stripped[2:].strip()
            # 列表项内联映射：- name: 张三, age: 20
            if ":" in item_raw:
                k, v = _split_key_value(item_raw)
                if k is not None:
                    item: Any = {_unquote(k): _parse_value(v) if v is not None else ""}
                else:
                    item = _parse_value(item_raw)
            else:
                item = _parse_value(item_raw)

            if current_list_key is not None and indent > 0:
                result.setdefault(current_list_key, [])
                result[current_list_key].append(item)
            else:
                # 顶层纯列表。
                if top_list is None:
                    top_list = []
                top_list.append(item)
            continue

        # 列表项内联映射的第二行及以后（缩进更深、无 ``- `` 前缀）。
        if current_list_key is not None and indent > 0 and stripped and ":" in stripped:
            k, v = _split_key_value(stripped)
            if k is not None and result.get(current_list_key):
                # 合并进最近一个列表项（若该项是 dict）。
                last = result[current_list_key][-1]
                if isinstance(last, dict):
                    last[_unquote(k)] = _parse_value(v) if v is not None else ""
            continue

        # ``key: value`` 或 ``key:`` 行。
        k, v = _split_key_value(line)
        if k is None:
            # 无法识别为键值对或列表项的行：整行作为字面量，忽略（宽容解析）。
            continue

        if v is None or v == "":
            # ``key:`` 后可能紧跟列表（下一行是 ``- item``），也可能是空值。
            # 不写入空字符串，而是先移除旧值，让后续列表项分支的
            # ``setdefault(key, [])`` 得以创建全新的 list（避免 str 上 append 崩溃）。
            result.pop(_unquote(k), None)
            current_list_key = _unquote(k)
            continue

        parsed = _parse_value(v)
        result[_unquote(k)] = parsed
        # 值非空后，若有待续列表则结束该列表上下文。
        current_list_key = None

    if top_list is not None:
        return top_list
    return result


def load_frontmatter(md_text: str) -> Tuple[Dict[str, Any], str]:
    """从 markdown 文本中提取 frontmatter 并解析。

    识别以 ``---`` 或 ``+++`` 分隔的 YAML frontmatter 块（位于文件开头）。

    Args:
        md_text: 完整 markdown 文本。

    Returns:
        ``(frontmatter_dict, body)``。frontmatter_dict 为解析出的元数据 dict
        （无 frontmatter 时为空 dict），body 为 frontmatter 之后的正文。
    """
    lines = md_text.splitlines()
    if not lines:
        return {}, ""

    first = lines[0].strip()
    if first not in ("---", "+++"):
        return {}, md_text

    # 找到闭合分隔符。
    end_idx: Optional[int] = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in ("---", "+++"):
            end_idx = idx
            break

    if end_idx is None:
        # 未闭合的 frontmatter：视为普通正文，不解析。
        return {}, md_text

    fm_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    return parse_yaml(fm_text), body


__all__ = ["parse_yaml", "load_frontmatter"]
