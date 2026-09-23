"""测试隔离公共设施：把 ``gui.config`` 的项目内数据路径常量重定向到临时目录。

R1 回归防线（根因：``STATE_JSON_DIR`` 新增后，多个测试只 patch ``STATE_ROOT``，
导致夹具写进真实 ``gui/state/`` 并跨轮累积）。本模块提供：

- ``DATA_PATH_CONSTANTS``：**必须被测试隔离**的 config 路径常量登记表；
- ``discover_data_path_constants()``：内省 config，自动发现所有项目内 Path 常量；
- ``isolate_paths()``：上下文管理器，成对重定向全部登记常量并还原；
- ``snapshot_real_state_json_dir()``：真实 ``gui/state/`` 快照，供泄漏守卫比对。

新增 config 路径常量而忘记登记时，``tests/test_config_isolation.py`` 会失败——
这正是防线生效点，禁止为让它变绿而删除断言。

纯标准库，不 import 任何第三方包（铁律三）。
"""
from __future__ import annotations

import contextlib
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

from gui import config

ROOT_DIR = config.ROOT_DIR
CONFIG_SOURCE = ROOT_DIR / "gui" / "config.py"

# 代码布局类常量（非「可重定向的数据目录」），不参与隔离。
INFRASTRUCTURE_CONSTANTS: Tuple[str, ...] = (
    "GUI_DIR",
    "ROOT_DIR",
    "SCRIPTS_DIR",
    "WEB_DIR",
    "DIST_DIR",
)

# 项目内数据路径常量登记表 —— 新增 config 路径常量必须在此登记。
DATA_PATH_CONSTANTS: Tuple[str, ...] = (
    "ASSETS_ROOT",
    "STATE_ROOT",
    "STATE_JSON_DIR",
    "DB_PATH",
    "LOCK_PATH",
    "REPORTS_DIR",
    "CORPUS_DIR",
    "CONFIG_DIR",
    "NOVEL_DIR",
    "PROMPTS_DIR",
)

# 真实状态 JSON 目录：由项目根推导，**不读 config**，避免被 patch 影响。
REAL_STATE_JSON_DIR = ROOT_DIR / "gui" / "state"

# 真实运行时状态目录（SQLite 索引 + settings.json + 锁）。
# 2026-09-23 新增：既有守卫只覆盖 REAL_STATE_JSON_DIR（派生镜像），而当日发现的隔离
# 事故发生在 **gui_state/**（settings.json 被测试覆写），故必须单独守卫。
REAL_GUI_STATE_DIR = ROOT_DIR / "gui_state"


def _canonical_config_namespace() -> Dict[str, Any]:
    """在全新命名空间里重新执行 ``gui/config.py`` 源码，取**规范值**。

    不能用运行时 ``getattr(config, name)``：其它测试会 monkeypatch config 常量
    （指向临时目录），使「是否位于项目根内」的判定失真。重新执行源码可得到
    与任何 patch 无关的、定义期的真实值。
    """
    namespace: Dict[str, Any] = {
        "__file__": str(CONFIG_SOURCE),
        "__name__": "gui._config_canonical_probe",
    }
    exec(compile(CONFIG_SOURCE.read_text(encoding="utf-8"), str(CONFIG_SOURCE), "exec"), namespace)
    return namespace


def discover_data_path_constants() -> Dict[str, Path]:
    """内省 ``gui/config.py``，返回所有「位于项目根内」的模块级 Path 常量。

    基于**定义期规范值**（非运行时被 patch 的值），排除下划线私有名与
    ``INFRASTRUCTURE_CONSTANTS``（代码布局，非数据目录）。
    """
    namespace = _canonical_config_namespace()
    root = namespace["ROOT_DIR"]
    found: Dict[str, Path] = {}
    for name, value in namespace.items():
        if name.startswith("_") or name in INFRASTRUCTURE_CONSTANTS:
            continue
        if isinstance(value, Path) and value.is_relative_to(root):
            found[name] = value
    return found


@contextlib.contextmanager
def isolate_paths(tmp_root: Path) -> Iterator[Dict[str, Path]]:
    """把全部 ``DATA_PATH_CONSTANTS`` 重定向到 ``tmp_root/<常量名小写>``，退出还原。

    Yields:
        重定向前的原值映射（便于断言还原正确）。
    """
    tmp_root = Path(tmp_root)
    saved = {name: getattr(config, name) for name in DATA_PATH_CONSTANTS}
    for name in DATA_PATH_CONSTANTS:
        setattr(config, name, tmp_root / name.lower())
    try:
        yield saved
    finally:
        for name, value in saved.items():
            setattr(config, name, value)


def snapshot_real_state_json_dir() -> frozenset:
    """返回真实 ``gui/state/`` 下状态 JSON 文件名集合（目录不存在则为空集）。"""
    if not REAL_STATE_JSON_DIR.is_dir():
        return frozenset()
    return frozenset(p.name for p in REAL_STATE_JSON_DIR.glob("gui_state_*.json"))


def snapshot_real_gui_state() -> Dict[str, Any]:
    """真实 ``gui_state/`` 的可观测快照：文件集合 + ``settings.json`` 内容 sha256 + mtime。

    只取「稳定可判定的可观测量」：**不含** SQLite 的 ``-wal`` / ``-shm`` 边车——
    SQLite 在只读打开 WAL 库时也可能创建它们，纳入比对会造成假阳性。

    同时记录 **mtime** 而不只是内容哈希：若测试把文件覆写成**相同内容**
    （例如真实文件恰好已是测试写入值），哈希不变会漏报，mtime 仍会变化。
    测试期间没有任何合法理由写这个文件，故 mtime 变化本身就是泄漏信号。

    2026-09-23 新增：用于捕获「模块级路径常量在导入期固化、config patch 失效」
    这一类隔离漏洞（既有登记表机制只能覆盖通过 config 属性访问的代码）。
    """
    if not REAL_GUI_STATE_DIR.is_dir():
        return {"files": frozenset(), "settings_exists": False,
                "settings_sha256": None, "settings_mtime_ns": None}
    files = frozenset(p.name for p in REAL_GUI_STATE_DIR.iterdir() if p.is_file())
    settings = REAL_GUI_STATE_DIR / "settings.json"
    exists = settings.is_file()
    digest = mtime = None
    if exists:
        st = settings.stat()
        digest = hashlib.sha256(settings.read_bytes()).hexdigest()
        mtime = st.st_mtime_ns
    return {"files": files, "settings_exists": exists,
            "settings_sha256": digest, "settings_mtime_ns": mtime}


# 测试会话开始时的真实目录快照（本模块在 discover 阶段被首个测试模块 import，
# 早于任何测试执行），供末位泄漏守卫比对。
SESSION_START_STATE_JSON_SNAPSHOT = snapshot_real_state_json_dir()
SESSION_START_GUI_STATE_SNAPSHOT = snapshot_real_gui_state()
