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
    - 单文件：直接读取；文件名取不到数字时按第 1 章兼容（沿用既有行为），
      取到 0（如 ``chapter-0.txt``）时**保留 0**，不伪装成第 1 章。
    - 目录：``Path.rglob("*.txt")``；相对路径中任一 **父目录** 名 casefold 后命中
      ``EXCLUDED_DIR_NAMES`` 即跳过；文件名取不到数字则记入 ``ignored``。
    - 双根语义（保留旧 ``logic_check`` 的 ``[source, source/"chapters"]``）：
      常规嵌套 ``source/chapters/`` 已被 ``source`` 的递归扫描覆盖，只加载一次；
      仅当 ``source/chapters`` 指向 ``source`` **之外**（符号链接/junction）时才显式
      补扫第二根并合并——``rglob`` 默认不跟随符号链接，不补扫会静默漏章。
    - 同一**物理文件**（按 ``Path.resolve()`` 归一，含符号链接别名）只加载一次，
      既避免两根重复扫到造成假冲突，也避免别名重复计入。
    - 同一章号对应多个**不同物理文件** → 抛 ``ChapterLoadError``，错误信息含章号与
      全部候选相对路径，禁止按遍历顺序静默覆盖。
    - 返回 dict 按章号升序。
    - 读取失败抛 ``OSError`` / ``UnicodeError``，错误信息带出问题文件路径。

用法:
    from chapter_loader import load_chapter_texts, discover_chapter_files

    texts = load_chapter_texts("novel/某书")      # {1: "...", 2: "..."}
    diag = discover_chapter_files("novel/某书")   # 诊断：ignored / duplicates
"""
import os
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
        source: 加载入口（章节目录或单章文件）的 Path，保持调用方传入的书写形式。
        chapter_number: 冲突的章号（int）。
        candidates: 冲突候选文件的**绝对路径**列表（已按路径排序）——即使 source
            传的是相对路径，candidates 也可直接用于定位/打开。
    """

    def __init__(self, source, chapter_number: int, candidates):
        self.source = Path(source)
        self.chapter_number = int(chapter_number)
        self.candidates = sorted(_absolute(Path(c)) for c in candidates)
        listed = "、".join(_display_path(p, self.source) for p in self.candidates)
        super().__init__(
            f"第{self.chapter_number}章存在 {len(self.candidates)} 个候选文件，"
            f"无法确定加载哪一个: {listed}（加载入口: {self.source}）"
        )


def _absolute(path: Path) -> Path:
    """转为绝对路径；不解析符号链接（保留调用方书写形式，仅补全目录前缀）。"""
    return Path(os.path.abspath(path))


def _resolve_physical(path: Path) -> Path:
    """解析真实物理路径（符号链接/junction 归一到目标）；失败时回退原路径。"""
    try:
        return path.resolve()
    except OSError:
        return path


def _display_path(path: Path, source: Path) -> str:
    """优先展示相对 source 的路径，便于定位；不在 source 下时回退绝对路径。

    path 是绝对路径而 source 可能是相对路径（如 ``"书"``），故两种基准都试。
    """
    for base in (source, _absolute(source)):
        try:
            return str(path.relative_to(base))
        except ValueError:
            continue
    return str(path)


def _chapter_number(path: Path):
    """从文件名（不含扩展名）提取章号；取不到返回 None。"""
    m = _CHAPTER_NUM_RE.search(path.stem)
    return int(m.group(1)) if m else None


def _is_excluded(relative_parts) -> bool:
    """相对路径的父目录部分是否命中排除集合（大小写不敏感）。"""
    return any(part.casefold() in EXCLUDED_DIR_NAMES for part in relative_parts)


def _is_covered_by(child: Path, parent: Path) -> bool:
    """child 的物理位置是否已位于 parent 之下（即 parent 的 rglob 能扫到它）。"""
    try:
        _resolve_physical(child).relative_to(_resolve_physical(parent))
    except ValueError:
        return False
    return True


def _scan_roots(source: Path) -> list:
    """返回需要扫描的根目录列表（旧 ``[source, source/"chapters"]`` 双根语义）。

    ``rglob`` 会递归普通子目录，因此常规嵌套结构下 ``source/chapters/`` 已被第一根
    覆盖，再扫第二根只会把同一物理文件算成两个候选（假冲突），故不再重复扫描。
    但当 ``source/chapters`` 指向 source **之外**（符号链接/junction）时，``rglob``
    默认不跟随符号链接（Python 3.13 ``recurse_symlinks=False``），必须显式补扫，
    否则外部章节目录会被静默漏掉——这正是旧双根语义存在的实质理由。
    """
    roots = [source]
    chapters_dir = source / "chapters"
    if chapters_dir.is_dir() and not _is_covered_by(chapters_dir, source):
        roots.append(chapters_dir)
    return roots


def discover_chapter_files(source) -> dict:
    """扫描 source，返回诊断结构（不读取文件内容）。

    Args:
        source: 章节目录、单章 txt 文件路径；不存在时返回空结构。

    Returns:
        dict: ``{"files": {章号: Path}, "ignored": [Path], "duplicates": {章号: [Path]}}``

        - ``files``：章号唯一、可直接加载的文件（按章号升序）。
        - ``ignored``：扫描到但未加载的文件（位于排除目录内，或文件名不含章号）。
        - ``duplicates``：同章号命中多个**不同物理文件**（这些章号不会出现在
          ``files`` 中）。
    """
    source = Path(source)
    result = {"files": {}, "ignored": [], "duplicates": {}}

    if source.is_file():
        number = _chapter_number(source)
        # 只有取不到数字才回退第 1 章；chapter-0.txt 的 0 必须保留（0 是合法章号）
        result["files"] = {1 if number is None else number: source}
        return result
    if not source.is_dir():
        return result

    candidates = {}       # 章号 → {物理路径: 候选路径}
    ignored = []
    ignored_seen = set()
    accepted = set()      # 已接受的物理路径（跨根/跨章号去重）
    for root in _scan_roots(source):
        for path in sorted(root.rglob("*.txt")):
            relative = path.relative_to(root)
            number = None if _is_excluded(relative.parts[:-1]) else _chapter_number(path)
            resolved = _resolve_physical(path)
            if number is None:
                if resolved not in ignored_seen:
                    ignored_seen.add(resolved)
                    ignored.append(path)
                continue
            if resolved in accepted:
                # 同一物理文件（第二根重复扫到，或符号链接别名）只算一次候选
                continue
            accepted.add(resolved)
            candidates.setdefault(number, {})[resolved] = path

    files = {}
    duplicates = {}
    for number in sorted(candidates):
        paths = sorted(candidates[number].values())
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
        dict[int, str]: 章号 → 正文。传入 novel_dir 时，novel_dir 自身的 ``*.txt``
        与其 ``chapters/`` 子目录（含指向外部的符号链接）下的章节一并加载，
        同一物理文件只加载一次。

    Raises:
        ChapterLoadError: 同一章号命中多个不同物理文件（信息含全部候选路径）。
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
