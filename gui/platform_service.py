"""多平台适配服务层：起点 / 番茄 / 晋江 / 七猫 格式支持。

提供各平台的章节格式、字数要求、导出适配。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from gui import config
from gui.services import ServiceError

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


def list_platforms() -> List[Dict[str, Any]]:
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


def get_platform(platform_id: str) -> Dict[str, Any]:
    """获取平台详情。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    return {"id": platform_id, **PLATFORMS[platform_id]}


def check_chapter_compliance(platform_id: str, chapter_text: str,
                              chapter_title: str = "") -> Dict[str, Any]:
    """检查章节是否符合平台要求。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
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


def format_chapter(platform_id: str, chapter_num: int, title: str,
                   content: str) -> Dict[str, Any]:
    """按平台格式化章节。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    p = PLATFORMS[platform_id]

    # 格式化标题
    formatted_title = p["chapter_format"].format(num=chapter_num, title=title)

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


def export_book_for_platform(platform_id: str, book_dir: str) -> Dict[str, Any]:
    """将整本书导出为平台适配格式。

    读取章节目录，按平台格式化并检查合规性。
    """
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    p = PLATFORMS[platform_id]

    book_path = Path(book_dir)
    if not book_path.is_dir():
        raise ServiceError(f"章节目录不存在: {book_dir}", 404)

    # 收集章节文件
    chapter_files = sorted(book_path.glob("*.txt")) + sorted(book_path.glob("*.md"))
    if not chapter_files:
        raise ServiceError(f"目录中没有章节文件: {book_dir}", 400)

    chapters = []
    total_chars = 0
    non_compliant = 0

    for i, fp in enumerate(chapter_files, 1):
        try:
            content = fp.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
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
