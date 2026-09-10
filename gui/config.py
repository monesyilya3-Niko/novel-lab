"""GUI 自有配置：端口、批次大小、静态目录、路径解析。

只依赖标准库 + 项目内相对路径，不 import 任何第三方包，也不 import scripts/。
模型配置复用 ``scripts/model_config.py``（由 engine_adapter 统一接入）。
"""
from __future__ import annotations

import os
from pathlib import Path

# GUI 包根目录（novel-lab/gui/）
GUI_DIR = Path(__file__).resolve().parent
# novel-lab 项目根目录（novel-lab/）
ROOT_DIR = GUI_DIR.parent
# scripts 目录（novel-lab/scripts/）
SCRIPTS_DIR = ROOT_DIR / "scripts"
# 前端源码目录（novel-lab/gui/web/）
WEB_DIR = GUI_DIR / "web"
# 前端预构建产物目录（novel-lab/gui/web/dist/）
DIST_DIR = WEB_DIR / "dist"

# 默认服务端口；被占用时自动 +1。
DEFAULT_PORT = 8000
# 默认批次大小（字符数），单批文本不超过该值。
DEFAULT_BATCH_SIZE = 4000

# 状态/资产落盘目录（相对 novel-lab 根目录）。
ASSETS_ROOT = ROOT_DIR / "assets"
# 运行时状态目录：只放**运行时产物**（SQLite 库 / WAL / SHM、单实例锁、备份）。
# 该目录被 .gitignore 整目录忽略（见 .gitignore「GUI 运行时数据」段）。
STATE_ROOT = ROOT_DIR / "gui_state"

# 状态 JSON 副本目录：state_store 的 `gui_state_*.json` 降级副本落这里。
#
# 【不入库】该目录被 .gitignore 整目录忽略（见 .gitignore「状态 JSON 副本目录」段）。
# 它是 SQLite（gui_state/index.db）的**派生镜像**，SQLite 才是任务状态的唯一权威来源；
# 跟踪派生数据会造成双真相源漂移与提交噪声，与「长期稳定可维护」相悖。
# 【机制保留】与 STATE_ROOT 分离，仅用于保留运行时 JSON 降级写入能力（库不可用/未初始化
# 时仍能落盘与读取），不改变任何代码逻辑；备份由 gui_state/*.bak-* 与 migrate backup 承担。
STATE_JSON_DIR = ROOT_DIR / "gui" / "state"

# SQLite 持久化库路径（Q1：gui_state/index.db）。
DB_PATH = STATE_ROOT / "index.db"
# 单实例锁文件（W09，P1）。
LOCK_PATH = STATE_ROOT / ".lock"

# 资产索引扫描范围（阶段一）。
REPORTS_DIR = ROOT_DIR / "reports"      # 拆书报告 / 笔法分析 Markdown
CORPUS_DIR = ROOT_DIR / "corpus"        # 已导入语料（*.txt）
CONFIG_DIR = ROOT_DIR / "config"        # 模型配置 models.json 等
# 阶段二写作产出目录（预留，阶段一不扫描）。
NOVEL_DIR = ROOT_DIR / "novel"

# 可选的端口环境变量覆盖（便于自动化测试 / 部署）。
_ENV_PORT = os.environ.get("NOVEL_LAB_GUI_PORT", "").strip()


def resolve_port(preferred: int | None = None) -> int:
    """解析最终端口：参数 > 环境变量 > 默认值。"""
    if preferred is not None:
        return int(preferred)
    if _ENV_PORT.isdigit():
        return int(_ENV_PORT)
    return DEFAULT_PORT


def batch_size_from_env() -> int:
    """从环境变量读取批次大小，缺省用默认值。"""
    raw = os.environ.get("NOVEL_LAB_GUI_BATCH_SIZE", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return DEFAULT_BATCH_SIZE
