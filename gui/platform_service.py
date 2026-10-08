"""多平台适配服务层：起点 / 番茄 / 晋江 / 七猫 格式支持。

提供各平台的章节格式、字数要求、导出适配。
"""
from __future__ import annotations

import re
from typing import Any

from gui import text_access
from gui.logging_setup import get_logger
from gui.services import ServiceError

_log = get_logger("platform_service")

# 平台配置
PLATFORMS = {
    "qidian": {
        "name": "起点中文网",
        "chapter_min_chars": 2000,
        "chapter_max_chars": 5000,
        "chapter_format": "第{num}章 {title}",
        "title_max_len": 30,
        "supports_serialization": True,
        "genre_whitelist": [
            "玄幻", "奇幻", "武侠", "仙侠", "都市", "现实", "军事", "历史",
            "游戏", "体育", "科幻", "悬疑", "轻小说", "短篇",
        ],
    },
    "fanqie": {
        "name": "番茄小说",
        "chapter_min_chars": 1500,
        "chapter_max_chars": 4000,
        "chapter_format": "第{num}章 {title}",
        "title_max_len": 20,
        "supports_serialization": True,
        "genre_whitelist": [
            "都市", "玄幻", "悬疑", "历史", "科幻", "言情", "武侠",
            "仙侠", "游戏", "体育", "现实", "轻小说",
        ],
    },
    "jinjiang": {
        "name": "晋江文学城",
        "chapter_min_chars": 3000,
        "chapter_max_chars": 8000,
        "chapter_format": "第{num}章 {title}",
        "title_max_len": 40,
        "supports_serialization": True,
        "genre_whitelist": [
            "言情", "纯爱", "无CP", "奇幻", "武侠", "仙侠", "都市",
            "悬疑", "科幻", "游戏", "轻小说", "短篇",
        ],
    },
    "qimao": {
        "name": "七猫小说",
        "chapter_min_chars": 1500,
        "chapter_max_chars": 4000,
        "chapter_format": "第{num}章 {title}",
        "title_max_len": 20,
        "supports_serialization": True,
        "genre_whitelist": [
            "都市", "玄幻", "悬疑", "历史", "科幻", "言情", "武侠",
            "仙侠", "游戏", "现实", "轻小说",
        ],
    },
    "zhihu": {
        "name": "知乎盐言",
        "chapter_min_chars": 5000,
        "chapter_max_chars": 20000,
        "chapter_format": "{title}",
        "title_max_len": 50,
        "supports_serialization": False,
        "genre_whitelist": [
            "悬疑", "言情", "脑洞", "科幻", "奇幻", "都市", "历史",
            "现实", "成长", "治愈",
        ],
    },
}


def list_platforms() -> list[dict[str, Any]]:
    """列出支持的平台。"""
    return [
        {
            "id": pid,
            "name": p["name"],
            "chapter_min_chars": p["chapter_min_chars"],
            "chapter_max_chars": p["chapter_max_chars"],
            "supports_serialization": p["supports_serialization"],
            "genre_count": len(p["genre_whitelist"]),
        }
        for pid, p in PLATFORMS.items()
    ]


def get_platform(platform_id: str) -> dict[str, Any]:
    """获取平台详情。

    2026-09-23（总工排查）修正错误码：本函数的 ``platform_id`` 来自**路径**
    （路由 ``GET /api/platform/{platform_id}``），语义是「按 id 取资源」，
    因此不存在时按 ``gui/router.py`` 的约定应返回 **404 资源不存在**，
    而非 400 参数错误。其余三个平台接口的 platform_id 来自**请求体**
    （``/platform/check`` / ``format`` / ``export``），属参数校验，维持 400。
    前端不区分 400/404（只展示 message），故无兼容性风险。
    """
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 404)
    return {"id": platform_id, **PLATFORMS[platform_id]}


def check_chapter_compliance(platform_id: str, chapter_text: str,
                              chapter_title: str = "") -> dict[str, Any]:
    """检查章节是否符合平台要求。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    if not isinstance(chapter_text, str):
        raise ServiceError("chapter_text 必须为字符串", 400)
    if chapter_title is None:
        chapter_title = ""
    if not isinstance(chapter_title, str):
        raise ServiceError("chapter_title 必须为字符串", 400)
    p = PLATFORMS[platform_id]

    char_count = len(chapter_text)
    issues = []

    # 字数检查
    if char_count < p["chapter_min_chars"]:
        issues.append({
            "type": "word_count",
            "severity": "error",
            "message": f"字数 {char_count} 不足，{p['name']} 要求最少 {p['chapter_min_chars']} 字",
        })
    elif char_count > p["chapter_max_chars"]:
        issues.append({
            "type": "word_count",
            "severity": "warning",
            "message": f"字数 {char_count} 超出建议上限 {p['chapter_max_chars']} 字",
        })

    # 标题检查
    if chapter_title:
        if len(chapter_title) > p["title_max_len"]:
            issues.append({
                "type": "title_length",
                "severity": "warning",
                "message": f"标题长度 {len(chapter_title)} 超出建议 {p['title_max_len']} 字",
            })

    # 内容检查
    if not chapter_text.strip():
        issues.append({
            "type": "empty_content",
            "severity": "error",
            "message": "章节内容为空",
        })

    # 敏感词简单检查
    sensitive_words = ['政治', '色情', '赌博', '毒品', '暴力']
    found_sensitive = [w for w in sensitive_words if w in chapter_text]
    if found_sensitive:
        issues.append({
            "type": "sensitive_content",
            "severity": "warning",
            "message": f"包含可能的敏感词: {', '.join(found_sensitive)}",
        })

    has_error = any(i["severity"] == "error" for i in issues)

    return {
        "platform": p["name"],
        "platform_id": platform_id,
        "char_count": char_count,
        "title_length": len(chapter_title) if chapter_title else 0,
        "compliant": not has_error,
        "issues": issues,
        "requirements": {
            "min_chars": p["chapter_min_chars"],
            "max_chars": p["chapter_max_chars"],
            "title_max_len": p["title_max_len"],
        },
    }


#: 章节标题自带的章号前缀（"第1章"、"第三十二章 "、"Chapter 3：" …）。
_CHAPTER_PREFIX_RE = re.compile(
    r"^\s*(?:第\s*[0-9零〇一二三四五六七八九十百千万两]{1,8}\s*[章节回]"
    r"|chapter\s*[0-9]+)\s*[:：、.·\-—]?\s*",
    re.IGNORECASE)


def format_chapter(platform_id: str, chapter_num: int, title: str,
                   content: str) -> dict[str, Any]:
    """按平台格式化章节。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    if not isinstance(title, str):
        raise ServiceError("title 必须为字符串", 400)
    if not isinstance(content, str):
        raise ServiceError("content 必须为字符串", 400)
    # 章号会直接拼进投稿标题，0 或负数会产出"第-3章 …"这种能一路贴到编辑眼前的垃圾
    if not isinstance(chapter_num, int) or isinstance(chapter_num, bool) or chapter_num < 1:
        raise ServiceError("chapter_num 必须为正整数", 400)
    p = PLATFORMS[platform_id]

    # 格式化标题：只有模板自己会补 {num} 时才剥掉原标题的章号前缀，
    # 否则"第1章 初见"会变成"第1章 第1章 初见"（2026-10-08 实测到的重复前缀）。
    # 知乎模板是纯 "{title}"，不剥——剥了就把章号整个丢了。
    fmt = p["chapter_format"]
    m = _CHAPTER_PREFIX_RE.match(title) if "{num}" in fmt else None
    if m is None:
        formatted_title = fmt.format(num=chapter_num, title=title)
    else:
        bare = title[m.end():].strip()
        # 标题只有章号（"第1章"）或空：前者原样保留，后者补一个光秃秃的章号。
        formatted_title = fmt.format(num=chapter_num, title=bare) if bare else (
            title.strip() or f"第{chapter_num}章")
    # 空标题会让模板留下"第1章 "这种尾巴，导出稿里看着像手没擦干净。
    formatted_title = formatted_title.rstrip()

    # 组装完整章节
    full_chapter = f"{formatted_title}\n\n{content}"

    return {
        "platform": p["name"],
        "platform_id": platform_id,
        "formatted_title": formatted_title,
        "full_chapter": full_chapter,
        "char_count": len(full_chapter),
        "content_char_count": len(content),
    }


def export_book_for_platform(platform_id: str, book_dir: str) -> dict[str, Any]:
    """将整本书导出为平台适配格式。

    读取章节目录，按平台格式化并检查合规性。
    """
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    p = PLATFORMS[platform_id]

    # book_dir 自 2026-10-08 起不再限制目录（用户稿子常在项目外），
    # 可读范围改由 text_access 按内容收紧：正文扩展名 + 非符号链接 + 体积上限。
    chapter_files = text_access.text_files_in(book_dir, field="book_dir")

    chapters = []
    total_chars = 0
    non_compliant = 0

    for i, fp in enumerate(chapter_files, 1):
        try:
            # 走 text_access 而不是 Path.read_text：国内稿子大量是 GBK，
            # 只按 UTF-8 解会让整章被静默跳过，导出的书凭空少一章。
            content = text_access.read_text(fp, field="book_dir")
        except ServiceError as exc:
            _log.warning(f"导出跳过无法读取的章节 {fp.name}: {exc.message}")
            continue

        # 提取标题（第一行）
        lines = content.strip().split('\n', 1)
        title = lines[0].strip() if lines else f"第{i}章"
        body = lines[1].strip() if len(lines) > 1 else content

        # 检查合规性
        compliance = check_chapter_compliance(platform_id, body, title)
        if not compliance["compliant"]:
            non_compliant += 1

        # 格式化
        formatted = format_chapter(platform_id, i, title, body)

        chapters.append({
            "num": i,
            "title": formatted["formatted_title"],
            "char_count": formatted["content_char_count"],
            "compliant": compliance["compliant"],
            "issues": compliance["issues"],
        })
        total_chars += formatted["content_char_count"]

    return {
        "platform": p["name"],
        "platform_id": platform_id,
        "total_chapters": len(chapters),
        "total_chars": total_chars,
        "non_compliant_chapters": non_compliant,
        "chapters": chapters,
        "export_ready": non_compliant == 0,
    }
