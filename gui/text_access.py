"""正文文件的读取准入（铁律三：纯标准库）。

背景（2026-10-08）：质检、打分、合规扫描、平台导出这四个入口都曾要求
"路径必须在项目目录或用户数据目录内"。用户的稿子放在别处（D 盘、桌面、
移动硬盘）就直接 403，反馈原话是"有些路径放不进去"。质检先放开后，其余
三处统一到同一条规则：**目录不设界，内容设界**。

为什么不能简单删掉检查：这些参数都来自本机 HTTP 接口，等价于"给一个任意
文件读取"。收口方式是把可读范围钉死在正文本身：

1. 只认正文扩展名（`.txt` / `.md`）——拿不到 index.db、settings.json、密钥；
2. 不跟随符号链接——否则 `章节.txt -> ~/.ssh/id_rsa` 就绕过了第 1 条；
3. 只读常规文件——FIFO/设备文件会让请求挂死或把无限流读进内存；
4. 有单文件 / 文件数 / 总字节上限——一次请求不会把整块盘吸进来。

2–4 必须在**同一个文件描述符**上完成：先 `os.open`，再用 `fstat` 判类型和大小，
全程不重解析路径。分开"先检查再 open"就是检查-使用竞态（检查完换成链接照读不误）。
``services._secure_read_text``（拆书导入）本来就是这套做法，本模块把它接过来做成
唯一实现，两边只是策略不同（导入只收 `.txt`、上限 100MB），文案也各自保留。

还有一条与中文作者直接相关的：**编码兜底**。国内稿子大量是 GBK/GB2312，
`Path.read_text(encoding="utf-8")` 会在这些文件上直接失败，看上去像"路径放不进去"，
其实是"编码读不了"。这里统一 UTF-8 → GBK 两段解码。

与 ``quality_service`` 的外部目录上限区分：那边是把目录**拷进临时区**给引擎扫，
量级按整本书算（单文件 50MB / 总量 200MB）；这边是**读进内存做打分与合规**，
单章 8MB 已经宽得离谱。两组数字口径不同，故各自独立，不要合并成"看起来更 DRY"的常量。
"""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

from gui.services import ServiceError

#: 允许读取的正文扩展名（小写）。
TEXT_SUFFIXES: frozenset[str] = frozenset({".txt", ".md"})

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 2000
MAX_TOTAL_BYTES = 64 * 1024 * 1024

# 默认文案/状态码；调用方可按自己的接口口径覆盖（见 read_text 的 messages）。
_DEFAULT_ERRORS: dict[str, tuple[str, int]] = {
    "suffix": ("{field} 只支持 {suffixes} 正文文件", 400),
    "symlink": ("{field} 不接受符号链接", 403),
    "irregular": ("{field} 只能读常规文件", 400),
    "oversize": ("{field} 文件过大（{size} > {limit}）", 400),
    "missing": ("{field} 指向的文件不存在：{path}", 404),
    "unreadable": ("{field} 文件读取失败：{path}", 500),
    "decode": ("{field} 编码无法识别（仅支持 UTF-8 / GBK）", 400),
}


def _fmt(messages: dict[str, tuple[str, int]], key: str, **kw: object) -> ServiceError:
    template, code = messages[key]
    return ServiceError(template.format(**kw), code)


def read_text(
    raw: str | Path,
    *,
    field: str,
    suffixes: frozenset[str] | None = None,
    max_bytes: int | None = None,
    messages: dict[str, tuple[str, int]] | None = None,
) -> str:
    """TOCTOU 安全地把一个正文文件读成字符串。

    ``field`` 是接口参数名，只用于错误信息里告诉调用方"哪个参数不对"。
    ``messages`` 允许按 key 覆盖文案与状态码（拆书导入沿用它原来的措辞）。

    ``suffixes`` / ``max_bytes`` 默认值必须是 ``None`` 而不是模块常量本身：
    默认参数在 ``def`` 执行时就求值了，写成 ``max_bytes=MAX_FILE_BYTES`` 会
    把常量在导入期冻住，之后改常量（测试调小上限、或以后挪进 settings）
    都不会生效——这正是本仓库 §4 记过的"导入期快照"同一个坑。
    """
    msgs = dict(_DEFAULT_ERRORS)
    if messages:
        msgs.update(messages)
    if suffixes is None:
        suffixes = TEXT_SUFFIXES
    if max_bytes is None:
        max_bytes = MAX_FILE_BYTES

    candidate = Path(raw)
    suffix = candidate.suffix.lower()
    if suffix not in suffixes:
        raise _fmt(
            msgs, "suffix",
            suffixes="/".join(sorted(suffixes)), field=field)
    flags = os.O_RDONLY
    has_nofollow = hasattr(os, "O_NOFOLLOW")
    if has_nofollow:
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        # O_NONBLOCK：防 FIFO 打开时阻塞；后面的 fstat 会拒绝非常规文件
        flags |= os.O_NONBLOCK
    try:
        fd = os.open(str(candidate), flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise _fmt(msgs, "symlink", field=field) from exc
        # Windows 上 os.open 打目录直接 EACCES，Linux 上则是打开成功后 fstat 才认出来。
        # 不区分会让同一个"把目录当文件传"的错误在两边报成 400 / 404。
        if candidate.is_dir():
            raise _fmt(msgs, "irregular", field=field) from exc
        raise _fmt(msgs, "missing", path=str(raw), field=field) from exc
    # 没有 O_NOFOLLOW 的平台（Windows）：打开后尽力再判一次链接。
    # 这里有 TOCTOU 窗口，但该平台没有更好的原语，且建链接需要提权。
    if not has_nofollow:
        try:
            if os.path.islink(str(candidate)):
                os.close(fd)
                raise _fmt(msgs, "symlink", field=field)
        except ServiceError:
            raise
        except OSError:
            pass
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise _fmt(msgs, "irregular", field=field)
        if st.st_size > max_bytes:
            raise _fmt(
                msgs, "oversize",
                size=f"{st.st_size // 1048576}MB",
                limit=f"{max_bytes // 1048576}MB", field=field)
    except ServiceError:
        os.close(fd)
        raise
    try:
        with os.fdopen(fd, "rb") as f:
            data = f.read()  # fd 由 fdopen 接管关闭
    except OSError as exc:
        raise _fmt(msgs, "unreadable", path=str(raw), field=field) from exc
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("gbk")
        except UnicodeDecodeError as exc:
            raise _fmt(msgs, "decode", field=field) from exc


def text_files_in(raw_dir: str | Path, *, field: str) -> list[Path]:
    """返回目录内的正文文件（按文件名排序）。只扫一层，不递归。

    递归会把用户的整个文档库一次性吸进来；正文导出从来也是按单目录组织的。
    """
    candidate = Path(raw_dir)
    if candidate.is_symlink():
        raise ServiceError(f"{field} 不接受符号链接目录", 403)
    root = candidate.resolve()
    if not root.is_dir():
        raise ServiceError(f"{field} 指向的目录不存在：{raw_dir}", 404)
    found = [p for p in root.iterdir()
             if p.suffix.lower() in TEXT_SUFFIXES and p.is_file() and not p.is_symlink()]
    if not found:
        raise ServiceError(f"{field} 目录中没有正文文件：{raw_dir}", 400)
    if len(found) > MAX_FILES:
        raise ServiceError(f"{field} 目录中文件过多（>{MAX_FILES}）：{raw_dir}", 400)
    found.sort(key=lambda p: p.name)
    total = 0
    for p in found:
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ServiceError(
                f"{field} 单文件过大（{p.name} {size // 1048576}MB > "
                f"{MAX_FILE_BYTES // 1048576}MB）", 400)
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ServiceError(f"{field} 目录正文总量过大（>{MAX_TOTAL_BYTES // 1048576}MB）", 400)
    return found
