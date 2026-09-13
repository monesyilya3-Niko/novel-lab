"""文风深度集成服务层：风格分析 / 风格资产 / 风格应用。

打通 cw-style-creator 与 novel-lab 蒸馏层，实现文风的提取、存储、应用。
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

from gui import config
from gui.services import ServiceError

# 风格资产目录
STYLES_DIR = config.ASSETS_ROOT / "styles"


def _ensure_styles_dir() -> Path:
    STYLES_DIR.mkdir(parents=True, exist_ok=True)
    return STYLES_DIR


def _sanitize_name(name: str) -> str:
    """校验风格名：非空、无路径分隔符。"""
    if not name or not name.strip():
        raise ServiceError("风格名不能为空", 400)
    n = name.strip()
    if any(ch in n for ch in ("/", "\\", "..", "\x00", "\n", "\r")):
        raise ServiceError(f"非法风格名: {name!r}", 400)
    if not re.fullmatch(r"[A-Za-z0-9_\-一-鿿]+", n):
        raise ServiceError(f"风格名只允许中英文/数字/下划线/连字符: {name!r}", 400)
    return n


def analyze_style(text: str, name: str = "") -> Dict[str, Any]:
    """分析文本风格特征，返回结构化风格卡。

    提取维度：句长分布 / 对话密度 / 情绪词密度 / 标点习惯 / 段落节奏 / 常用词
    """
    if not text or len(text.strip()) < 100:
        raise ServiceError("文本太短，至少需要 100 字", 400)

    # 句长分析
    sentences = re.split(r'[。！？!?]', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    sent_lengths = [len(s) for s in sentences]
    avg_sent_len = sum(sent_lengths) / len(sent_lengths) if sent_lengths else 0

    # 对话密度
    dialogue_chars = sum(len(m.group(1)) for m in re.finditer(r'["「]([^"」]*)["」]', text))
    dialogue_ratio = dialogue_chars / len(text) if text else 0

    # 情绪词密度（常见情绪词）
    emotion_words = ['心', '泪', '笑', '怒', '怕', '爱', '恨', '痛', '暖', '冷',
                     '紧张', '害怕', '开心', '难过', '愤怒', '惊讶', '感动']
    emotion_count = sum(text.count(w) for w in emotion_words)
    emotion_density = emotion_count / len(text) * 1000  # 每千字

    # 标点习惯
    punct_counts = {
        '句号': text.count('。'),
        '感叹号': text.count('！'),
        '问号': text.count('？'),
        '省略号': text.count('……'),
        '破折号': text.count('——'),
        '逗号': text.count('，'),
    }

    # 段落节奏
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    para_lengths = [len(p) for p in paragraphs]
    avg_para_len = sum(para_lengths) / len(para_lengths) if para_lengths else 0
    short_para_ratio = sum(1 for p in para_lengths if p < 50) / len(para_lengths) if para_lengths else 0

    # 常用词（简单分词）
    words = re.findall(r'[一-鿿]{2,4}', text)
    word_freq = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1
    top_words = sorted(word_freq.items(), key=lambda x: -x[1])[:20]

    style_card = {
        "name": name or "未命名风格",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metrics": {
            "avg_sentence_length": round(avg_sent_len, 1),
            "sentence_count": len(sentences),
            "dialogue_ratio": round(dialogue_ratio, 3),
            "emotion_density": round(emotion_density, 2),
            "avg_paragraph_length": round(avg_para_len, 1),
            "short_paragraph_ratio": round(short_para_ratio, 3),
            "total_chars": len(text),
        },
        "punctuation": punct_counts,
        "top_words": [{"word": w, "count": c} for w, c in top_words],
        "sample_length": min(len(text), 500),
    }

    return style_card


def save_style(name: str, style_card: Dict[str, Any]) -> Dict[str, Any]:
    """保存风格卡到资产目录。"""
    n = _sanitize_name(name)
    _ensure_styles_dir()
    fp = STYLES_DIR / f"{n}.json"
    if fp.exists():
        raise ServiceError(f"风格已存在: {n}", 409)
    style_card["name"] = n
    fp.write_text(json.dumps(style_card, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"name": n, "path": str(fp.relative_to(config.ROOT_DIR)), "saved": True}


def list_styles() -> List[Dict[str, Any]]:
    """列出已保存的风格卡。"""
    _ensure_styles_dir()
    styles = []
    for fp in sorted(STYLES_DIR.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            styles.append({
                "name": fp.stem,
                "created_at": data.get("created_at", ""),
                "metrics": data.get("metrics", {}),
            })
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[warn] 跳过无法解析的文风档案 {fp.name}: {exc}")
            continue
    return styles


def get_style(name: str) -> Dict[str, Any]:
    """获取风格卡详情。"""
    n = _sanitize_name(name)
    fp = STYLES_DIR / f"{n}.json"
    if not fp.is_file():
        raise ServiceError(f"风格不存在: {n}", 404)
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ServiceError(f"风格文件损坏: {exc}", 500)


def delete_style(name: str) -> Dict[str, Any]:
    """删除风格卡。"""
    n = _sanitize_name(name)
    fp = STYLES_DIR / f"{n}.json"
    if not fp.is_file():
        raise ServiceError(f"风格不存在: {n}", 404)
    fp.unlink()
    return {"deleted": n}


def apply_style_prompt(style_name: str, base_prompt: str) -> Dict[str, Any]:
    """将风格卡应用到写作 prompt，生成风格增强版 prompt。

    基于风格卡的指标，生成风格指导段落并追加到 base_prompt。
    """
    style = get_style(style_name)
    metrics = style.get("metrics", {})

    # 根据指标生成风格指导
    guidance = []

    avg_sent = metrics.get("avg_sentence_length", 20)
    if avg_sent < 15:
        guidance.append("- 句子偏短，保持简洁有力的节奏")
    elif avg_sent > 40:
        guidance.append("- 句子偏长，注意适当断句避免冗长")
    else:
        guidance.append(f"- 句长适中（平均 {avg_sent} 字），保持自然节奏")

    dialogue_ratio = metrics.get("dialogue_ratio", 0.2)
    if dialogue_ratio > 0.3:
        guidance.append("- 对话密度较高，多用对话推进剧情")
    elif dialogue_ratio < 0.1:
        guidance.append("- 对话密度较低，以叙述和描写为主")
    else:
        guidance.append(f"- 对话占比约 {dialogue_ratio*100:.0f}%，对话与叙述平衡")

    emotion_density = metrics.get("emotion_density", 5)
    if emotion_density > 10:
        guidance.append("- 情绪词密度高，注重情感表达")
    elif emotion_density < 3:
        guidance.append("- 情绪词密度低，以克制内敛为主")
    else:
        guidance.append(f"- 情绪表达适中（每千字约 {emotion_density:.0f} 个情绪词）")

    short_para = metrics.get("short_paragraph_ratio", 0.3)
    if short_para > 0.4:
        guidance.append("- 短段落较多，节奏明快")
    else:
        guidance.append("- 段落较长，注重叙述连贯")

    style_section = "\n".join(guidance)
    enhanced_prompt = f"{base_prompt}\n\n【风格指导】\n{style_section}"

    return {
        "style_name": style_name,
        "base_prompt_length": len(base_prompt),
        "enhanced_prompt": enhanced_prompt,
        "enhanced_prompt_length": len(enhanced_prompt),
        "guidance": guidance,
    }
