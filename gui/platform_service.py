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
        "climax_interval": "8-12章",
        "dialogue_sweet_spot": (20.0, 45.0),
        "rhythm_type": "长线升级·世界观宏大·智斗博弈",
        "platform_taboos": ["主角无原则圣母", "战力严重崩坏", "反派无脑降智", "通篇白话纯对白水文"],
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
        "climax_interval": "2-3章",
        "dialogue_sweet_spot": (25.0, 55.0),
        "rhythm_type": "短平快·300字入戏·高频碾压打脸",
        "platform_taboos": ["开篇大段设定说明文", "主角憋屈隐忍不还手", "章末无悬念钩子", "节奏拖沓慢热"],
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
        "climax_interval": "4-6章",
        "dialogue_sweet_spot": (35.0, 60.0),
        "rhythm_type": "人设细腻·情感推拉·修罗场张力",
        "platform_taboos": ["主角人设崩塌OOC", "油腻古早霸总台词", "通篇枯燥陈述缺乏神态微表情", "低俗低质擦边"],
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
        "climax_interval": "3-5章",
        "dialogue_sweet_spot": (25.0, 50.0),
        "rhythm_type": "下沉爽感·阶级反差·强势归来逆袭",
        "platform_taboos": ["长篇受辱无底牌反制", "世界观过于晦涩深奥", "主角行事优柔寡断"],
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
        "climax_interval": "1500字一反转",
        "dialogue_sweet_spot": (15.0, 40.0),
        "rhythm_type": "第一人称代入·多重反转·现实人性撕裂",
        "platform_taboos": ["第三人称疏离叙事", "无逻辑天降外挂", "开篇缺乏核心矛盾事件", "通篇注水流水账"],
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
            "climax_interval": p.get("climax_interval", ""),
            "rhythm_type": p.get("rhythm_type", ""),
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


_INFO_DUMP_KEYWORDS = [
    "在这个世界", "很久很久以前", "相传数万年前", "历史悠久", "众所周知",
    "力量体系分为", "地理位置极为特殊", "根据上古文献记载", "天地初开之际",
    "这片大陆上", "修仙境界划分为", "追溯到太古时期", "浩瀚的大陆"
]

_AI_SLOP_PHRASES = [
    "心中涌起一股暖流", "宛如天神下凡", "深知这个道理", "眼神中闪烁着复杂的光芒",
    "嘴角勾起一抹弧度", "不由得倒吸了一口凉气", "在心中默默发誓", "感到无比的震惊与愤怒",
    "仿佛在诉说着曾经的过往", "这一刻，时间仿佛静止了", "不是因为别的，而是因为",
    "在这寂静的夜里", "无形之中散发着", "仿佛能够穿透一切", "一时间，空气陷入了沉默"
]


def diagnose_chapter(platform_id: str, chapter_text: str,
                     chapter_title: str = "", chapter_num: int = 1) -> dict[str, Any]:
    """网文签约过稿深度诊断（黄金三章自检、说明文劝退度分析、全平台专属审核规则）。"""
    if platform_id not in PLATFORMS:
        raise ServiceError(f"不支持的平台: {platform_id}", 400)
    if not isinstance(chapter_text, str):
        raise ServiceError("chapter_text 必须为字符串", 400)
    if chapter_title is None:
        chapter_title = ""
    if not isinstance(chapter_title, str):
        raise ServiceError("chapter_title 必须为字符串", 400)
    try:
        c_num = int(chapter_num)
        if c_num < 1:
            c_num = 1
    except (TypeError, ValueError):
        c_num = 1

    p = PLATFORMS[platform_id]
    char_count = len(chapter_text)
    score = 100
    veto_risks: list[str] = []
    actionable_fixes: list[str] = []

    # 1. 篇幅达标度
    min_c = p["chapter_min_chars"]
    max_c = p["chapter_max_chars"]
    if char_count < min_c:
        deficit = min_c - char_count
        score -= min(35, int(deficit / min_c * 40))
        veto_risks.append(f"字数不足：当前 {char_count} 字，低于 {p['name']} 最低签约门槛 {min_c} 字（缺 {deficit} 字）")
        actionable_fixes.append(f"将本章核心冲突或情绪推进补充完整，扩写至 {min_c} 字以上")
    elif char_count > max_c:
        score -= 5
        veto_risks.append(f"单章偏长：当前 {char_count} 字超出建议上限 {max_c} 字，可能造成单章定价偏高或阅读疲劳")
        actionable_fixes.append("建议在剧情转折处拆分为两章，以提升留存与追读率")

    # 2. 黄金开篇前 300 字检测（特别是前三章）
    opening_snippet = chapter_text[:300].strip()
    is_early_chapter = c_num <= 3
    has_dialogue_or_action = any(q in opening_snippet for q in ('"', "“", "”", "：")) or any(
        act in opening_snippet for act in ("退婚", "死", "杀", "冷笑", "拔剑", "签", "跪", "滚", "跑", "巴掌", "离婚", "系统")
    )
    found_info_dump = [k for k in _INFO_DUMP_KEYWORDS if k in opening_snippet]

    if is_early_chapter:
        if found_info_dump:
            score -= 25
            veto_risks.append(f"头号劝退点：开篇前300字陷入大段背景/历史说明文（命中：{', '.join(found_info_dump)}）")
            actionable_fixes.append("删去开篇背景设定，直接从主角面临的生死危机、剧烈冲突或对话场景切入（先打起来，设定随剧情自然展开）")
        elif not has_dialogue_or_action:
            score -= 15
            veto_risks.append("开篇节奏较缓：前300字缺乏鲜明的动作冲突、人物对话或紧迫悬念")
            actionable_fixes.append("前三句植入核心钩子或悬念（如危机、反常事件或倒计时），抓住前三秒阅读注意力")

    # 3. 对话密度分析
    from gui import engine_adapter
    dialogue_chars = engine_adapter.dialogue_char_count(chapter_text)
    dialogue_ratio = round((dialogue_chars / char_count) * 100, 1) if char_count > 0 else 0
    if char_count > 500:
        if dialogue_ratio < 12.0:
            score -= 15
            veto_risks.append(f"对话密度过低（{dialogue_ratio}%）：通篇叙述说明，读者极易产生视觉与心理疲劳")
            actionable_fixes.append("将部分陈述句转换为人物交锋对白，用角色的说话态度表现性格冲突")
        elif dialogue_ratio > 65.0:
            score -= 10
            veto_risks.append(f"对话密度过高（{dialogue_ratio}%）：通篇纯对白，缺乏环境渲染与神态动作支撑")
            actionable_fixes.append("在台词间穿插角色的微表情、肢体动作与潜台词动作节拍（action beats）")

    # 4. AI味俗套词排查
    found_slop = [phrase for phrase in _AI_SLOP_PHRASES if phrase in chapter_text]
    if found_slop:
        deduction = min(20, len(found_slop) * 5)
        score -= deduction
        veto_risks.append(f"AI味俗套表达过多（命中 {len(found_slop)} 处：{', '.join(found_slop[:3])}）")
        actionable_fixes.append("使用写作台【去AI味体检】功能，将书面说明腔与陈词滥调替换为自然网文口语表达")

    # 5. 全平台专属风格深度自检
    if platform_id == "zhihu" and "我" not in chapter_text[:500]:
        score -= 20
        veto_risks.append("知乎盐言风格偏离：前500字未见第一人称“我”，知乎读者偏好第一人称沉浸式代入")
        actionable_fixes.append("知乎短篇故事建议改为第一人称主视角叙事，直接拉满代入感与情绪撕裂度")
    elif platform_id == "fanqie" and is_early_chapter and score < 80:
        veto_risks.append("番茄完读率预警：前三章节奏偏慢，番茄算法推荐严重依赖前三章读完率")
        actionable_fixes.append("在第1章结尾必须设计强悬念钩子，第2-3章必须安排一次小型爽点兑现")
    elif platform_id == "qidian":
        virgin_mary_keywords = ["原谅了他", "得饶人处且饶人", "放虎归山", "心中不忍放过", "饶他不死"]
        found_holy = [k for k in virgin_mary_keywords if k in chapter_text]
        if found_holy:
            score -= 15
            veto_risks.append(f"起点读者大忌：主角出现无原则圣母行为（命中：{', '.join(found_holy)}）")
            actionable_fixes.append("起点读者极重杀伐果断与合理自保，消除圣母行为，改为主角权衡利弊后的果决处置")
        if dialogue_ratio > 55.0 and char_count > 1000:
            score -= 10
            veto_risks.append(f"起点宏大叙事失衡：对话占比高达 {dialogue_ratio}%，缺乏世界观、博弈与心理铺垫")
            actionable_fixes.append("起点长线文需要更扎实的势力背景与环境博弈描写，精简纯对白，增加局势分析与动作细节")
    elif platform_id == "jinjiang":
        greasy_phrases = ["小妖精", "女人你成功引起了我的注意", "不知好歹的小东西", "玩火自焚"]
        found_greasy = [k for k in greasy_phrases if k in chapter_text]
        if found_greasy:
            score -= 20
            veto_risks.append(f"晋江人设大忌：出现油腻古早霸总俗套台词（命中：{', '.join(found_greasy)}）")
            actionable_fixes.append("彻底删除油腻俗套用语，改为符合现代审美的互相尊重、平等推拉与眼神细节")
        emotional_keywords = ["眼神", "心跳", "指尖", "微怔", "垂眸", "呼吸", "眼底", "轻颤", "下意识"]
        if not any(k in chapter_text for k in emotional_keywords) and char_count > 800:
            score -= 10
            veto_risks.append("晋江情感张力不足：本章未见眼神、心跳、微表情等细腻神态描写")
            actionable_fixes.append("晋江读者极重心理共鸣，在两人互动关键节点补充神态微表情与潜台词动作节拍")
    elif platform_id == "qimao":
        insult_keywords = ["废物", "穷光蛋", "上门女婿", "窝囊废", "倒插门"]
        has_insult = any(k in chapter_text[:800] for k in insult_keywords)
        counter_keywords = ["底牌", "战神", "至尊", "神医", "龙王", "系统", "余额", "冷笑", "下跪", "大佬"]
        has_counter = any(k in chapter_text[:1200] for k in counter_keywords)
        if is_early_chapter and has_insult and not has_counter:
            score -= 15
            veto_risks.append("七猫爽点脱节预警：开篇主角受尽侮辱嘲讽，但前千字内未见任何反制底牌或爽点预期")
            actionable_fixes.append("下沉免费流极忌漫长憋屈，在受辱后 500 字内必须展示隐秘底牌或反打脸前置伏笔")

    score = max(20, min(100, score))
    if score >= 85:
        grade = "A"
        signing_prob = "高（具备高过稿潜力）"
    elif score >= 70:
        grade = "B"
        signing_prob = "中（基本合格，建议按优化建议调整后投递）"
    else:
        grade = "C"
        signing_prob = "低（存在明显硬伤，容易被编辑当场秒拒）"

    return {
        "platform": p["name"],
        "platform_id": platform_id,
        "chapter_num": c_num,
        "char_count": char_count,
        "score": score,
        "grade": grade,
        "signing_prob": signing_prob,
        "dialogue_ratio": dialogue_ratio,
        "veto_risks": veto_risks,
        "actionable_fixes": actionable_fixes,
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
