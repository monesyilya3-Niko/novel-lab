"""防线：``AGENTS.md`` §7「当前实测口径」的**确定性**指标必须与实测一致。

背景（2026-09-23 总工排查）
--------------------------
项目文档口径长期漂移，同一时期各文件互相打架：

| 文件 | 声称 | 当时实测 |
|---|---|---|
| ``README.md`` | 测试基线 782 | 857 |
| ``AGENTS.md`` | 测试 853 | 857 |
| ``PROJECT_SUMMARY.md`` 正文 | 测试 782 / 资产 55 | 857 / 65 |
| ``PROJECT_SUMMARY.md`` 页脚 | 测试 853 / 资产 65 | 857 / 65 |
| ``HANDOFF.md`` | 780 / 801 / 55 / 60 | 857 / 65 |

而 ``AGENTS.md`` §7 自己声明「所有资产/报告数字**以实测磁盘为准**」——文档本身
违反了这条红线。手工维护多份重复数字已被证明不可靠，故加此自动守卫。

只锁定**确定性**指标
--------------------
- 测试用例数（``unittest`` discover 结果）
- API 端点数（``gui/router.py::ROUTES``）
- 版本号（``gui.__version__``）

资产 / 报告 / 书目数量随用户业务变化（拆一本新书就变），**不纳入断言**——
否则会变成「干正事就挂」的假警报。

纯标准库（铁律三）。
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

AGENTS_MD = ROOT / "AGENTS.md"
TESTS_DIR = ROOT / "tests"

# 「- 当前实测口径（YYYY-MM-DD）：资产 **65** / 报告 **12** / 书 **8**（已拆 6）
#  / 测试 **876** / API 端点 **65** / 版本 **1.1.2**」
# 锚定到列表项：正文里任何"提到这个短语"的句子都不该顶掉真正的口径行
# （2026-10-08 实测踩过：§4 补了一句解释文字，search() 抓到它，报的是"缺 tests 字段"这种误导性失败）。
_METRIC_LINE_RE = re.compile(r"^- 当前实测口径.*$", re.M)
_TEST_RE = re.compile(r"测试\s*\*\*(\d+)\*\*")
_ENDPOINT_RE = re.compile(r"API\s*端点\s*\*\*(\d+)\*\*")
_VERSION_RE = re.compile(r"版本\s*\*\*([0-9]+\.[0-9]+\.[0-9]+)\*\*")


def _actual_test_count() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")
    return suite.countTestCases()


def _actual_endpoint_count() -> int:
    from gui import router
    return len(router.ROUTES)


def _actual_version() -> str:
    import gui
    return gui.__version__


def _metric_line(text: str) -> str:
    """取 AGENTS.md 的权威口径行；多义或缺失都当场失败（不得静默取第一条）。"""
    matches = _METRIC_LINE_RE.findall(text)
    assert matches, (
        "AGENTS.md 未找到「- 当前实测口径」行；该行是文档数字的单一权威位置，"
        "不得删除、改名或改成非列表项。"
    )
    assert len(matches) == 1, (
        f"AGENTS.md 出现 {len(matches)} 条「当前实测口径」行，"
        "会造成双真相源，请只保留 §7 那一条。"
    )
    return matches[0]


def _stated_metrics(text: str | None = None) -> dict:
    if text is None:
        text = AGENTS_MD.read_text(encoding="utf-8")
    line = _metric_line(text)
    out = {}
    for key, rx in (("tests", _TEST_RE), ("endpoints", _ENDPOINT_RE), ("version", _VERSION_RE)):
        m = rx.search(line)
        assert m, f"「当前实测口径」行缺少 {key} 字段（应为 **值** 加粗格式）：{line}"
        out[key] = m.group(1)
    return out


class TestDocMetricsMatchReality(unittest.TestCase):
    """AGENTS.md §7 的确定性指标必须等于实测值。"""

    def test_metric_line_is_parseable(self):
        stated = _stated_metrics()
        self.assertEqual(set(stated), {"tests", "endpoints", "version"})

    def test_prose_mention_does_not_shadow_metric_line(self):
        """别处只是"提到"这个说法时，不得顶掉权威行的解析（2026-10-08 实修回归）。"""
        real = AGENTS_MD.read_text(encoding="utf-8")
        line = _metric_line(real)
        polluted = real.replace(
            "## 4. 测试规范",
            "## 4. 测试规范\n\n（下文提到「当前实测口径」这个说法，但它不是数据行）",
            1,
        )
        self.assertNotEqual(polluted, real, "构造的污染文本没生效，用例失去意义")
        self.assertEqual(_metric_line(polluted), line)
        self.assertEqual(_stated_metrics(polluted), _stated_metrics(real))

    def test_metric_line_is_unique(self):
        """口径行必须只有一条——多写一份就是双真相源，正是要防的事故形态。"""
        real = AGENTS_MD.read_text(encoding="utf-8")
        self.assertEqual(len(_METRIC_LINE_RE.findall(real)), 1)
        self.assertRaises(AssertionError, _metric_line, real + "\n- 当前实测口径（2099-01-01）：测试 **1**\n")

    def test_test_baseline_matches_actual(self):
        stated = int(_stated_metrics()["tests"])
        actual = _actual_test_count()
        self.assertEqual(
            stated,
            actual,
            f"AGENTS.md 声称测试基线 {stated}，实测 {actual}。"
            "新增/删除测试后必须同步更新 AGENTS.md §7 的「当前实测口径」行"
            "（这是有意的摩擦：防止文档数字再次漂移）。",
        )

    def test_endpoint_count_matches_actual(self):
        stated = int(_stated_metrics()["endpoints"])
        actual = _actual_endpoint_count()
        self.assertEqual(
            stated,
            actual,
            f"AGENTS.md 声称 API 端点 {stated}，实测 {actual}（gui/router.py::ROUTES）。",
        )

    def test_version_matches_actual(self):
        stated = _stated_metrics()["version"]
        actual = _actual_version()
        self.assertEqual(
            stated,
            actual,
            f"AGENTS.md 声称版本 {stated}，实测 {actual}（gui/__init__.py）。",
        )

    def test_readme_does_not_duplicate_a_test_baseline(self):
        """README 不得再写死测试基线数字——它是最容易被读到的文件，也是最易漂移处。

        设计取舍：**单一权威来源**。当前口径只允许写在 ``AGENTS.md`` §7
        （由本模块的其它用例守住）；README 改为指路，从根上消除「多份数字互相打架」
        这一类问题（README 曾写 782、AGENTS 写 853、HANDOFF 写 780/801）。
        """
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        stale = re.findall(r"(\d{3,4})\s*用例基线", text)
        self.assertEqual(
            stale, [],
            "README 又出现了写死的测试基线数字 "
            f"{stale}——请改为指向 AGENTS.md §7（单一权威来源）。",
        )


if __name__ == "__main__":
    sys.exit(unittest.main(verbosity=2))
