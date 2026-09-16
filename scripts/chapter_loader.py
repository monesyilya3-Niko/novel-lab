#!/usr/bin/env python3
"""统一章节加载器 — 确定性发现 + 备份目录排除 + 同章号冲突显式报错（纯标准库）

为什么需要它（2026-09-16）：
    `book_quality` / `qc` / `logic_check` 曾各自实现一套「递归扫 ``*.txt`` + 从文件名
    取数字」的加载逻辑，并且都写成 ``texts[num] = read_text()`` 直接赋值。后果有三：

      1. 章节目录下的 ``_备份/``、``备份/``、``backup/``、``.git/``、``build/``、
         ``dist/`` 里的旧稿会被当成正文参与质检，污染结论；
      2. 同一章号命中多个文件时（如 ``第001章.txt`` 与 ``chapter-001.txt`` 并存），
         按 ``sorted(rglob)`` 的遍历顺序静默覆盖——加载结果依赖文件名字典序，
         不可复现，且**不报错**；
      3. 三套实现细节不一致，修一处漏两处。

    本模块是章节发现的唯一事实来源：三个后端入口统一委托 ``load_chapter_texts()``。

规则（确定性）：
    - 单文件：直接读取；文件名取不到数字时按第 1 章兼容（沿用既有行为）。
    - 目录：``Path.rglob("*.txt")``；相对路径中任一 **父目录** 名 casefold 后命中
      ``EXCLUDED_DIR_NAMES`` 即跳过；文件名取不到数字则记入 ``ignored``。
    - 同一章号对应多个候选文件 → 抛 ``ChapterLoadError``，错误信息含章号与全部
      候选相对路径，禁止按遍历顺序静默覆盖。
    - 返回 dict 按章号升序。
    - 读取失败抛 ``OSError`` / ``UnicodeError``，错误信息带出问题文件路径。

用法:
    from chapter_loader import load_chapter_texts, discover_chapter_files

    texts = load_chapter_texts("novel/某书")      # {1: "...", 2: "..."}
    diag = discover_chapter_files("novel/某书")   # 诊断：ignored / duplicates
"""
import re
from pathlib import Path

__all__ = [
    "ChapterLoadError",
    "EXCLUDED_DIR_NAMES",
    "discover_chapter_files",
    "load_chapter_texts",
]

# 备份/构建产物目录名（比较时 casefold）：这些目录里的 .txt 一律不参与加载
EXCLUDED_DIR_NAMES = {"_备份", "备份", "backup", ".git", "build", "dist"}

_CHAPTER_NUM_RE = re.compile(r'(\d+)')


class ChapterLoadError(ValueError):
    """章节加载失败：同一章号命中多个未被排除的候选文件。

    Attributes:
        source: 加载入口（章节目录或单章文件）的 Path。
        chapter_number: 冲突的章号（int）。
        candidates: 冲突候选文件的绝对路径列表（已按路径排序）。
    """

    def __init__(self, source, chapter_number: int, candidates):
        self.source = Path(source)
        self.chapter_number = int(chapter_number)
        self.candidates = sorted(Path(c) for c in candidates)
        listed = "、".join(_display_path(p, self.source) for p in self.candidates)
        super().__init__(
            f"第{self.chapter_number}章存在 {len(self.candidates)} 个候选文件，"
            f"无法确定加载哪一个: {listed}（加载入口: {self.source}）"
        )


def _display_path(path: Path, source: Path) -> str:
    """优先展示相对 source 的路径，便于定位；不在 source 下时回退绝对路径。"""
    try:
        return str(path.relative_to(source))
    except ValueError:
        return str(path)


def _chapter_number(path: Path):
    """从文件名（不含扩展名）提取章号；取不到返回 None。"""
    m = _CHAPTER_NUM_RE.search(path.stem)
    return int(m.group(1)) if m else None


def _is_excluded(relative_parts) -> bool:
    """相对路径的父目录部分是否命中排除集合（大小写不敏感）。"""
    return any(part.casefold() in EXCLUDED_DIR_NAMES for part in relative_parts)


def discover_chapter_files(source) -> dict:
    """扫描 source，返回诊断结构（不读取文件内容）。

    Args:
        source: 章节目录、单章 txt 文件路径；不存在时返回空结构。

    Returns:
        dict: ``{"files": {章号: Path}, "ignored": [Path], "duplicates": {章号: [Path]}}``

        - ``files``：章号唯一、可直接加载的文件（按章号升序）。
        - ``ignored``：扫描到但未加载的文件（位于排除目录内，或文件名不含章号）。
        - ``duplicates``：同章号命中多个文件（这些章号不会出现在 ``files`` 中）。
    """
    source = Path(source)
    result = {"files": {}, "ignored": [], "duplicates": {}}

    if source.is_file():
        result["files"] = {_chapter_number(source) or 1: source}
        return result
    if not source.is_dir():
        return result

    candidates = {}
    ignored = []
    for path in sorted(source.rglob("*.txt")):
        relative = path.relative_to(source)
        if _is_excluded(relative.parts[:-1]):
            ignored.append(path)
            continue
        number = _chapter_number(path)
        if number is None:
            ignored.append(path)
            continue
        candidates.setdefault(number, []).append(path)

    files = {}
    duplicates = {}
    for number in sorted(candidates):
        paths = sorted(candidates[number])
        if len(paths) > 1:
            duplicates[number] = paths
        else:
            files[number] = paths[0]

    result["files"] = files
    result["ignored"] = ignored
    result["duplicates"] = duplicates
    return result


def _read_text(path: Path) -> str:
    """读取章节文本；失败时抛出带出问题文件路径的 OSError / UnicodeError。"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise UnicodeError(f"章节文件解码失败（非 UTF-8？）: {path} — {exc}") from exc
    except OSError as exc:
        raise OSError(f"章节文件读取失败: {path} — {exc}") from exc


def load_chapter_texts(source) -> dict:
    """把章节目录 / 单章文件归一为 ``{章号: 文本}``（按章号升序）。

    Args:
        source: 章节目录、单章 txt 文件路径；不存在时返回空 dict。

    Returns:
        dict[int, str]: 章号 → 正文。

    Raises:
        ChapterLoadError: 同一章号命中多个未被排除的文件（信息含全部候选路径）。
        OSError / UnicodeError: 文件读取或解码失败（信息含问题文件路径）。
    """
    diagnostic = discover_chapter_files(source)
    if diagnostic["duplicates"]:
        number = min(diagnostic["duplicates"])
        raise ChapterLoadError(source, number, diagnostic["duplicates"][number])
    return {number: _read_text(path)
            for number, path in diagnostic["files"].items()}


if __name__ == "__main__":  # pragma: no cover - 诊断入口
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    diag = discover_chapter_files(target)
    print(f"章节目录: {target}")
    print(f"  可加载章节: {len(diag['files'])} → {sorted(diag['files'])}")
    print(f"  忽略文件: {len(diag['ignored'])}")
    for p in diag["ignored"][:20]:
        print(f"    - {p}")
    print(f"  同章号冲突: {len(diag['duplicates'])}")
    for number, paths in diag["duplicates"].items():
        print(f"    第{number}章:")
        for p in paths:
            print(f"      * {p}")
