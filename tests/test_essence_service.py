"""小说精华数据库（Novel Essence Database）单元测试与回归测试。

覆盖范围：
1. 数据库表与迁移 0003 幂等性；
2. 书籍档案 CRUD 及级联删除收敛性（不留孤儿资产）；
3. 五维资产卡片 CRUD、标签检索与创作者个人笔记修改；
4. 伏笔暗线回收链增删查；
5. 纯本地离线宏观节奏与文风快速萃取、黄金三章开篇解构；
6. 一键反哺写作工坊（转入大纲 writing_outlines、人物卡 writing_characters、灵感便签 writing_notes）；
7. 路由层 /api/essence/* 真实分发测试与脏参数 400 拦截。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
ROOT = _TESTS_DIR.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_TESTS_DIR))
import _isolation  # noqa: E402

from gui import db, essence_service, router
from gui.services import ServiceError


class TestEssenceService(unittest.TestCase):
    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="essence_test_")))
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()

    def tearDown(self):
        db.close()
        self._iso.__exit__(None, None, None)

    def test_migrations_applied_and_tables_exist(self):
        conn = db.get_conn()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        self.assertIn("essence_books", tables)
        self.assertIn("essence_assets", tables)
        self.assertIn("essence_chains", tables)
        self.assertIn("essence_tasks", tables)

    def test_book_crud_and_cascade_delete(self):
        # 1. 创建书籍
        b = essence_service.create_or_update_book(
            book_id="book_xuanhuan_01",
            title="仙道求索",
            genre="xiuxian",
            platform="qidian",
            total_chapters=100,
            total_chars=300000,
        )
        self.assertEqual(b["book_id"], "book_xuanhuan_01")
        self.assertEqual(b["title"], "仙道求索")

        # 2. 查询列表与详情
        books = essence_service.list_books(genre="xiuxian")
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0]["title"], "仙道求索")

        b_get = essence_service.get_book("book_xuanhuan_01")
        self.assertEqual(b_get["total_chapters"], 100)

        # 3. 创建关联资产与伏笔链
        a = essence_service.create_asset(
            book_id="book_xuanhuan_01",
            category="persona",
            title="韩立原型反差",
            content="表面平平无奇，暗藏掌天瓶，杀伐果决",
            tags="隐忍,反差,修仙",
        )
        c = essence_service.create_chain(
            book_id="book_xuanhuan_01",
            clue_name="神秘绿瓶",
            hook_chapter=1,
            payoff_chapter=15,
            hook_text="在山间捡到一枚看似普通的绿瓶",
            payoff_text="催熟千年灵草，一战惊天下",
        )
        self.assertEqual(len(essence_service.list_assets(book_id="book_xuanhuan_01")), 1)
        self.assertEqual(len(essence_service.list_chains(book_id="book_xuanhuan_01")), 1)

        # 4. 级联删除：删除书时关联资产与伏笔链原子化清空（收敛验证）
        del_res = essence_service.delete_book("book_xuanhuan_01")
        self.assertTrue(del_res["deleted"])
        self.assertEqual(len(essence_service.list_books()), 0)
        self.assertEqual(len(essence_service.list_assets(book_id="book_xuanhuan_01")), 0)
        self.assertEqual(len(essence_service.list_chains(book_id="book_xuanhuan_01")), 0)

    def test_asset_crud_and_tag_filtering(self):
        # 创建两条资产
        a1 = essence_service.create_asset(
            book_id="book_01",
            category="opening",
            title="黄金三章退婚开篇",
            content="主角当场撕毁婚约，立下三年之约",
            tags="退婚,爽点,三年之约",
            genre="xuanhuan",
            platform="fanqie",
            rating=5,
        )
        a2 = essence_service.create_asset(
            book_id="book_02",
            category="trope",
            title="拍卖会扮猪吃老虎",
            content="主角伪装低调，最后一掷千金拿下压轴丹药",
            tags="拍卖会,打脸,伪装",
            genre="xuanhuan",
            platform="qidian",
            rating=4,
        )

        # 按分类筛选
        openings = essence_service.list_assets(category="opening")
        self.assertEqual(len(openings), 1)
        self.assertEqual(openings[0]["id"], a1["id"])

        # 按标签检索
        tagged = essence_service.list_assets(tag="打脸")
        self.assertEqual(len(tagged), 1)
        self.assertEqual(tagged[0]["id"], a2["id"])

        # 按生态平台筛选
        qidian_assets = essence_service.list_assets(platform="qidian")
        self.assertEqual(len(qidian_assets), 1)
        self.assertEqual(qidian_assets[0]["id"], a2["id"])

        fanqie_assets = essence_service.list_assets(platform="fanqie")
        self.assertEqual(len(fanqie_assets), 1)
        self.assertEqual(fanqie_assets[0]["id"], a1["id"])

        # 更新个人笔记与评分
        updated = essence_service.update_asset(a1["id"], user_note="这个切入点适合写都市退婚时套用", rating=5)
        self.assertEqual(updated["user_note"], "这个切入点适合写都市退婚时套用")

        # 删除资产
        del_res = essence_service.delete_asset(a1["id"])
        self.assertTrue(del_res["deleted"])
        self.assertEqual(len(essence_service.list_assets(category="opening")), 0)

    def test_macro_extraction_and_opening_slice(self):
        sample_novel = (
            "第1章 惊变退婚\n"
            "林轩冷笑道：“就凭你们也配？”\n"
            "萧家大厅内，气氛肃杀，众人拔剑相对。忽然，门外传来一阵轰鸣……\n\n"
            "第2章 绝境逆袭\n"
            "林轩深吸一口气，运转玄天功法。四方灵气汇聚，天地为之震动。\n\n"
            "第3章 震动全城\n"
            "整个青云城都在议论林轩的奇迹，那一刻，无人敢再轻视。\n"
        )
        macro = essence_service.extract_macro_essence(sample_novel, "剑啸九天", genre="xuanhuan", platform="fanqie")
        self.assertEqual(macro["title"], "剑啸九天")
        self.assertEqual(macro["total_chapters"], 3)
        self.assertGreater(macro["dialogue_ratio"], 0)
        self.assertIn("top_characters", macro)

        # 开篇切片解构
        chapters = essence_service.split_chapters_simple(sample_novel)
        opening_slice = essence_service.extract_opening_slice(chapters)
        self.assertTrue(opening_slice["has_immediate_conflict"])
        self.assertTrue(opening_slice["hook_detected"])
        self.assertIn("A", opening_slice["opening_grade"])

    def test_adopt_asset_to_writing_workbench(self):
        # 1. 创建一条精华资产
        asset = essence_service.create_asset(
            book_id="book_01",
            category="persona",
            title="楚风",
            content="表面慵懒市井商贩，实为隐世神王传人",
            summary="市井隐忍与神王底牌",
            tags="神王,反差",
        )

        # 2. 一键转入大纲
        adopt_outline = essence_service.adopt_asset_to_project(asset["id"], "my_new_book", target_kind="outline")
        self.assertTrue(adopt_outline["adopted"])
        self.assertEqual(adopt_outline["target_kind"], "outline")
        # 验证写入 writing_outlines 表
        row = db.get_conn().execute("SELECT * FROM writing_outlines WHERE id = ?", (adopt_outline["adopted_id"],)).fetchone()
        self.assertEqual(row["title"], "楚风")

        # 3. 一键转入人物卡
        adopt_char = essence_service.adopt_asset_to_project(asset["id"], "my_new_book", target_kind="character")
        self.assertTrue(adopt_char["adopted"])
        self.assertEqual(adopt_char["target_kind"], "character")
        # 验证写入 writing_characters 表
        char_row = db.get_conn().execute("SELECT * FROM writing_characters WHERE id = ?", (adopt_char["adopted_id"],)).fetchone()
        self.assertEqual(char_row["name"], "楚风")

        # 4. 一键转入灵感便签
        adopt_note = essence_service.adopt_asset_to_project(asset["id"], "my_new_book", target_kind="note")
        self.assertTrue(adopt_note["adopted"])
        self.assertEqual(adopt_note["target_kind"], "note")
        note_row = db.get_conn().execute("SELECT * FROM writing_notes WHERE id = ?", (adopt_note["adopted_id"],)).fetchone()
        self.assertIn("楚风", note_row["title"])

    def test_router_endpoints_dispatch(self):
        # 1. POST /api/essence/analyze 提取宏观数据并建档
        resp, _ = router.dispatch(
            "POST",
            "/api/essence/analyze",
            {
                "title": "大道朝天",
                "text": "第1章 朝天\n井九背着铁剑，走在风雪中。赵腊月微笑道：“走吧。”\n",
                "genre": "xianxia",
                "platform": "qidian",
            },
            {},
        )
        self.assertEqual(resp["code"], 0)
        self.assertEqual(resp["data"]["title"], "大道朝天")
        book_id = resp["data"]["book_id"]

        # 2. GET /api/essence/books
        b_list_resp, _ = router.dispatch("GET", "/api/essence/books", {}, {})
        self.assertEqual(b_list_resp["code"], 0)
        self.assertEqual(len(b_list_resp["data"]["books"]), 1)

        # 3. POST /api/essence/assets 创建资产
        asset_resp, _ = router.dispatch(
            "POST",
            "/api/essence/assets",
            {
                "book_id": book_id,
                "category": "style",
                "title": "猫腻极简风",
                "content": "短句克制，留白丰富，多用冷幽默与潜台词交锋",
            },
            {},
        )
        self.assertEqual(asset_resp["code"], 0)
        asset_id = asset_resp["data"]["id"]

        # 4. POST /api/essence/adopt 反哺
        adopt_resp, _ = router.dispatch(
            "POST",
            "/api/essence/adopt",
            {
                "asset_id": asset_id,
                "project": "test_proj",
                "target_kind": "note",
            },
            {},
        )
        self.assertEqual(adopt_resp["code"], 0)
        self.assertTrue(adopt_resp["data"]["adopted"])

        # 5. 脏输入拦截 400
        with self.assertRaises(ServiceError) as cm:
            router.dispatch(
                "POST",
                "/api/essence/analyze",
                {"title": "", "text": ""},
                {},
            )
        self.assertEqual(cm.exception.code, 400)

    def test_essence_chains_router_endpoints(self):
        # 1. 创建伏笔暗线
        create_resp, _ = router.dispatch(
            "POST",
            "/api/essence/chains",
            {
                "book_id": "test_book_chains",
                "clue_name": "神秘玉佩",
                "hook_chapter": 2,
                "payoff_chapter": 25,
                "hook_text": "爷爷临死前塞给他的残破玉佩",
                "payoff_text": "在古修洞府中玉佩发烫开启密室",
                "status": "resolved",
                "analysis": "标准双向闭环伏笔",
            },
            {},
        )
        self.assertEqual(create_resp["code"], 0)
        chain_id = create_resp["data"]["id"]

        # 2. 查询伏笔列表
        list_resp, _ = router.dispatch("GET", "/api/essence/chains", {}, {"book_id": "test_book_chains"})
        self.assertEqual(list_resp["code"], 0)
        self.assertEqual(len(list_resp["data"]["chains"]), 1)

        # 3. 删除伏笔
        del_resp, _ = router.dispatch("DELETE", f"/api/essence/chains/{chain_id}", {}, {})
        self.assertEqual(del_resp["code"], 0)
        self.assertTrue(del_resp["data"]["deleted"])


if __name__ == "__main__":
    unittest.main()
