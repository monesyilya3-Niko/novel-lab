"""自动备份（铁律三：纯标准库）。

- 服务启动时备份一次（server.start → startup_backup）
- 每日本地日期首次有请求时备份一次（跨天首个请求触发）

复用 ``migrate.backup()``：SQLite 原生在线备份（含 WAL 数据）+ keep=3 剪枝，
故障只记日志不阻断服务/请求。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from gui.logging_setup import get_logger

_log = get_logger("auto_backup")

_last_backup_date: Optional[str] = None


def startup_backup() -> Optional[Path]:
    """执行一次备份并登记日期。返回备份路径，无可备份库/失败返回 None。"""
    global _last_backup_date
    try:
        from gui import migrate  # 延迟导入：避免 import 环（migrate → db → config）
        p = migrate.backup()
        _last_backup_date = time.strftime("%Y-%m-%d")
        if p is not None:
            _log.info("自动备份完成: %s", p.name)
        return p
    except Exception as exc:  # noqa: BLE001 — 备份失败不阻断服务
        _log.warning("自动备份失败（不影响服务）: %s", exc)
        return None


def daily_backup_if_due() -> None:
    """跨天后的首个请求触发当日备份（幂等，代价为一次日期比较）。"""
    if _last_backup_date == time.strftime("%Y-%m-%d"):
        return
    startup_backup()
