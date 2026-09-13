"""novel-lab 统一日志配置（纯标准库，铁律三）。

策略：
- 服务内部诊断 → ``logging.getLogger("novellab.<模块>")``；
  ``setup_logging()`` 由服务入口（gui.launch / gui.server.main）调用一次，
  落盘 ``gui_state/logs/gui.log``（RotatingFileHandler 5MB × 3 轮转）。
- 用户交互输出（launch 启动横幅、migrate CLI 报告）保留 ``print``——
  它们是产品接口，不是日志。
- 测试/未初始化场景：未配置 handler 时 logger 走标准 lastResort
  （仅 WARNING+ 到 stderr），不会在测试中落盘。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from gui import config

LOGGER_NAME = "novellab"
LOG_DIR = config.STATE_ROOT / "logs"
LOG_FILE = LOG_DIR / "gui.log"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

_FMT = "%(asctime)s %(levelname)-7s %(name)s %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> str:
    """初始化 novellab 根 logger（幂等）。返回日志文件路径。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger(LOGGER_NAME)
    if root.handlers:
        return str(LOG_FILE)
    root.setLevel(level)
    root.propagate = False

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    console.setLevel(logging.WARNING)  # 控制台只出告警以上，正常路径仍由 print 承担
    root.addHandler(console)
    return str(LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """按约定取模块 logger：get_logger("server") → novellab.server。"""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
