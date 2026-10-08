"""用户自有正文文件的读取准入（铁律三：纯标准库）。

背景（2026-10-08）：质检、打分、合规扫描、平台导出这四个入口都曾要求
"路径必须在项目目录或用户数据目录内"。用户的稿子放在别处（D 盘、桌面、
移动硬盘）就直接 403，反馈原话是"有些路径放不进去"。质检已经先放开，
这里把其余三处统一到同一条规则上：**目录不再设界，内容类型设界**。

为什么不能简单删掉检查：这些参数都来自本机 HTTP 接口，等价于
"给一个任意文件读取"。收口方式是把可读范围钉死在正文本身：

1. 只认 `.txt` / `.md` —— 拿不到 index.db、secrets、密钥等其它文件；
2. 拒绝符号链接 —— 防止 `第1章.txt -> ~/.ssh/id_rsa` 绕过第 1 条
   （必须在 `resolve()` 之前判断，resolve 之后链接痕迹就没了）；
3. 单文件 / 文件数 / 总字节三重上限 —— 一次请求不会把整块盘读进内存。

注意与 ``quality_service`` 的外部目录上限区分：那边是把目录**拷进临时区**
给引擎扫，量级按整本书算（单文件 50MB / 总量 200MB）；这边是**读进内存做
打分与合规**，单章级别 8MB 已经宽得离谱。两组数字口径不同，故各自独立，
不要合并成一个"看起来更 DRY"的常量。
"""

from __future__ import annotations

from pathlib import Path

from gui.services import ServiceError

#: 允许读取的正文扩展名（小写）。
TEXT_SUFFIXES: frozenset[str] = frozenset({".txt", ".md"})

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 2000
MAX_TOTAL_BYTES = 64 * 1024 * 1024


def text_file(raw: str | Path, *, field: str) -> Path:
    """校验并返回一个可读的正文文件路径（不读内容，由调用方决定怎么读）。

    ``field`` 是接口参数名，只用于错误信息里告诉调用方"哪个参数不对"。
    """
    candidate = Path(raw)
    if candidate.is_symlink():
        raise ServiceError(f"{field} 不接受符号链接", 400)
    suffix = candidate.suffix.lower()
    if suffix not in TEXT_SUFFIXES:
        raise ServiceError(f"{field} 只支持 {'/'.join(sorted(TEXT_SUFFIXES))} 正文文件", 400)
    fp = candidate.resolve()
    if not fp.is_file():
        raise ServiceError(f"{field} 指向的文件不存在：{raw}", 404)
    size = fp.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ServiceError(
            f"{field} 文件过大（{size // 1048576}MB > {MAX_FILE_BYTES // 1048576}MB）", 400)
    return fp


def text_files_in(raw_dir: str | Path, *, field: str) -> list[Path]:
    """校验并返回目录内的正文文件（按文件名排序），越过分层用 ``_`` 开头的文件。

    只扫一层（与既有导出行为一致），不递归——递归会把用户的整个文档库吸进来。
    """
    candidate = Path(raw_dir)
    if candidate.is_symlink():
        raise ServiceError(f"{field} 不接受符号链接目录", 400)
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
