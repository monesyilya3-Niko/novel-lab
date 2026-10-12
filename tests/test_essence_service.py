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

        # 4. 前端表单字段别名创建 (title, plant_chapter, climax_chapter, description, category)
        create_ui_resp, _ = router.dispatch(
            "POST",
            "/api/essence/chains",
            {
                "book_id": "test_book_chains",
                "title": "九品心法残页",
                "category": "力量伏笔",
                "plant_chapter": 3,
                "climax_chapter": 30,
                "description": "藏经阁拾取的残破经书，实为神级功法。",
                "status": "planted",
            },
            {},
        )
        self.assertEqual(create_ui_resp["code"], 0)
        ui_chain = create_ui_resp["data"]
        self.assertEqual(ui_chain["title"], "九品心法残页·力量伏笔")
        self.assertEqual(ui_chain["plantChapter"], 3)
        self.assertEqual(ui_chain["climaxChapter"], 30)
        self.assertEqual(ui_chain["category"], "力量伏笔")

    def test_essence_stats_endpoint(self):
        # 1. 初始空库统计
        resp, _ = router.dispatch("GET", "/api/essence/stats", {}, {})
        self.assertEqual(resp["code"], 0)
        data = resp["data"]
        self.assertEqual(data["totalBooks"], 0)
        self.assertEqual(data["total_books"], 0)
        self.assertEqual(data["totalAssets"], 0)
        self.assertEqual(data["totalChains"], 0)

        # 2. 插入一本书与资产后校验
        essence_service.create_or_update_book(
            book_id="b_stat_01",
            title="统计测试书",
            genre="xianxia",
            platform="qidian",
            total_chapters=10,
            total_chars=30000,
        )
        essence_service.create_asset(
            book_id="b_stat_01",
            category="outline",
            title="核心大纲卡",
            content="大纲内容",
        )
        resp2, _ = router.dispatch("GET", "/api/essence/stats", {}, {})
        self.assertEqual(resp2["code"], 0)
        data2 = resp2["data"]
        self.assertEqual(data2["totalBooks"], 1)
        self.assertEqual(data2["totalChars"], 30000)
        self.assertEqual(data2["totalAssets"], 1)
        self.assertIn("xianxia", data2["genreDistribution"])

    def test_essence_assets_fuzzy_search_and_category_synonyms(self):
        essence_service.create_or_update_book(
            book_id="b_search_01",
            title="斗破乾坤",
            genre="xuanhuan",
            platform="qidian",
            total_chapters=50,
            total_chars=150000,
        )
        # 插入开篇钩子 (category=opening)
        essence_service.create_asset(
            book_id="b_search_01",
            category="opening",
            title="三十年河东三十年河西",
            content="莫欺少年穷！",
            tags="退婚,逆袭",
        )
        # 插入人设反差 (category=persona)
        essence_service.create_asset(
            book_id="b_search_01",
            category="persona",
            title="戒指里的老爷爷药老",
            content="灵魂体状态的九品炼药宗师",
            tags="金手指,导师",
        )

        # 1. 模糊检索 query
        resp_q, _ = router.dispatch("GET", "/api/essence/assets", {}, {"query": "莫欺少年穷"})
        self.assertEqual(resp_q["code"], 0)
        self.assertEqual(len(resp_q["data"]["assets"]), 1)
        self.assertEqual(resp_q["data"]["assets"][0]["title"], "三十年河东三十年河西")

        # 2. 同义词 category="hook" 能查出 category="opening"
        resp_hook, _ = router.dispatch("GET", "/api/essence/assets", {}, {"category": "hook"})
        self.assertEqual(resp_hook["code"], 0)
        self.assertEqual(len(resp_hook["data"]["assets"]), 1)

        # 3. 同义词 category="character" 能查出 category="persona"
        resp_char, _ = router.dispatch("GET", "/api/essence/assets", {}, {"category": "character"})
        self.assertEqual(resp_char["code"], 0)
        self.assertEqual(len(resp_char["data"]["assets"]), 1)
        self.assertEqual(resp_char["data"]["assets"][0]["title"], "戒指里的老爷爷药老")

    def test_essence_invalid_param_400_intercept(self):
        # 1. DELETE asset 传入非数字 asset_id
        with self.assertRaises(ServiceError) as cm:
            router.dispatch("DELETE", "/api/essence/assets/invalid-id", {}, {})
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("asset_id 必须为整数", cm.exception.message)

        # 2. DELETE chain 传入非数字 chain_id
        with self.assertRaises(ServiceError) as cm:
            router.dispatch("DELETE", "/api/essence/chains/invalid-id", {}, {})
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("chain_id 必须为整数", cm.exception.message)

        # 3. POST adopt 传入非数字 asset_id
        with self.assertRaises(ServiceError) as cm:
            router.dispatch("POST", "/api/essence/adopt", {"asset_id": "not-an-int", "project": "default"}, {})
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("asset_id 必须为整数", cm.exception.message)

        # 4. POST chain 传入非数字 hook_chapter
        with self.assertRaises(ServiceError) as cm:
            router.dispatch("POST", "/api/essence/chains", {
                "book_id": "b1", "clue_name": "线索", "hook_chapter": "abc"
            }, {})
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("hook_chapter 必须为整数", cm.exception.message)

        # 5. POST asset 传入非数字 rating
        with self.assertRaises(ServiceError) as cm:
            router.dispatch("POST", "/api/essence/assets", {
                "book_id": "b1", "category": "style", "title": "标题", "content": "内容", "rating": "abc"
            }, {})
        self.assertEqual(cm.exception.code, 400)
        self.assertIn("rating 必须为整数", cm.exception.message)

    def test_export_book_outline_and_beats_markdown(self):
        # 创建测试书籍与配套资产
        essence_service.create_or_update_book(
            book_id="b_export_test",
            title="星河战记",
            genre="科幻末世",
            platform="起点中文网",
            total_chapters=10,
            total_chars=35000,
        )
        essence_service.create_asset(
            book_id="b_export_test",
            category="opening",
            title="开篇黄金危机钩",
            content="主角在荒原废墟中遭遇巡逻队...",
            summary="开篇高压求生",
        )
        essence_service.create_asset(
            book_id="b_export_test",
            category="persona",
            title="主角林恩",
            content="性格隐忍机智，擅长枪械改装",
        )
        essence_service.create_chain(
            book_id="b_export_test",
            clue_name="怀表里的神秘芯片",
            hook_chapter=1,
            payoff_chapter=8,
            hook_text="林恩拾得一枚斑驳怀表",
            status="resolved",
        )

        # 1. 直接调用导出
        outline_md = essence_service.export_book_outline_markdown("b_export_test")
        self.assertIn("# 《星河战记》全书结构大纲与解构报告", outline_md)
        self.assertIn("开篇黄金危机钩", outline_md)
        self.assertIn("主角林恩", outline_md)
        self.assertIn("怀表里的神秘芯片", outline_md)

        beats_md = essence_service.export_chapter_beats_markdown("b_export_test")
        self.assertIn("# 《星河战记》分章节拍与轻提纲清单", beats_md)
        self.assertIn("第 001 章", beats_md)
        self.assertIn("埋设伏笔", beats_md)

        # 2. 路由 GET 验证
        resp_out, _ = router.dispatch("GET", "/api/essence/books/b_export_test/export-outline", {}, {})
        self.assertEqual(resp_out["code"], 0)
        self.assertIn("星河战记", resp_out["data"]["markdown"])

        resp_beats, _ = router.dispatch("GET", "/api/essence/books/b_export_test/export-beats", {}, {})
        self.assertEqual(resp_beats["code"], 0)
        self.assertIn("分章节拍", resp_beats["data"]["markdown"])

    def test_constitution_compliance_check(self):
        # 1. 违宪文本：现代现实文出现超自然与恶俗台词
        bad_text = (
            "林晨站在街角。\n"
            "他心念一动，体内元婴飞快运转，一道灵气灌注双目。\n"
            "女人你这是在玩火，他冷冷地说道。\n"
        )
        res_bad = essence_service.check_constitution_compliance(bad_text)
        self.assertFalse(res_bad["is_compliant"])
        self.assertLess(res_bad["compliance_score"], 80)
        self.assertTrue(any(v["matched_term"] == "元婴" for v in res_bad["violations"]))
        self.assertTrue(any(v["matched_term"] == "灵气" for v in res_bad["violations"]))
        self.assertTrue(any(v["matched_term"] == "女人你这是在玩火" for v in res_bad["violations"]))

        # 2. 角色声线红线触发
        voice_text = "温霜禾看着窗外，大声说：我好痛苦，我非常悲伤！"
        char_forbidden = {"温霜禾": ["我好痛苦", "非常悲伤"]}
        res_voice = essence_service.check_constitution_compliance(voice_text, characters_forbidden=char_forbidden)
        self.assertGreater(len(res_voice["character_voice_alerts"]), 0)
        self.assertEqual(res_voice["character_voice_alerts"][0]["character"], "温霜禾")

        # 3. 正常合规文本
        good_text = "江春屿坐在长椅上，把围巾往上拉了拉。风穿过操场，落叶沙沙响着。"
        res_good = essence_service.check_constitution_compliance(good_text)
        self.assertTrue(res_good["is_compliant"])
        self.assertEqual(res_good["compliance_score"], 100)
        self.assertEqual(len(res_bad["violations"]), 3)

        # 4. 路由 POST 接口验证
        resp_api, _ = router.dispatch("POST", "/api/essence/constitution/check", {"text": bad_text}, {})
        self.assertEqual(resp_api["code"], 0)
        self.assertFalse(resp_api["data"]["is_compliant"])

    def test_ensure_curated_library(self):
        """验证 8 大传世神作编纂矩阵入库、资产与伏笔链完整绑定。"""
        res = essence_service.ensure_curated_library(clean_raw_corpus=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["curated_books_seeded"], 8)

        books = essence_service.list_books()
        titles = {b["title"] for b in books}
        self.assertIn("暮冬念春", titles)
        self.assertIn("诡秘之主", titles)
        self.assertIn("凡人修仙传", titles)
        self.assertIn("道诡异仙", titles)
        self.assertIn("大奉打更人", titles)
        self.assertIn("庆余年", titles)
        self.assertIn("雪中悍刀行", titles)
        self.assertIn("斗破苍穹", titles)

        # 验证《暮冬念春》五维资产与伏笔
        md_book = essence_service.get_book("curated_mudongnianchun")
        self.assertEqual(md_book["title"], "暮冬念春")
        self.assertEqual(md_book["total_chapters"], 157)
        self.assertEqual(md_book["genre"], "yanqing")

        assets = essence_service.list_assets(book_id="curated_mudongnianchun")
        self.assertGreaterEqual(len(assets), 5)

        chains = essence_service.list_chains(book_id="curated_mudongnianchun")
        self.assertGreaterEqual(len(chains), 2)

    def test_adopt_book_to_project(self):
        """验证一键转入整本神作资产到写作项目。"""
        essence_service.ensure_curated_library(clean_raw_corpus=False)
        res = essence_service.adopt_book_to_project("curated_mudongnianchun", "test_proj")
        self.assertTrue(res["adopted"])
        self.assertEqual(res["total_adopted"], 5)

        # 路由分发 POST /api/essence/books/{book_id}/adopt-all
        resp, _ = router.dispatch(
            "POST",
            "/api/essence/books/curated_mudongnianchun/adopt-all",
            {"project": "demo_novel"},
            {},
        )
        self.assertEqual(resp["code"], 0)
        self.assertTrue(resp["data"]["adopted"])
        self.assertEqual(resp["data"]["total_adopted"], 5)


class TestGarbageCleanupWildcard(unittest.TestCase):
    """ensure_curated_library 的垃圾清理不得误伤用户书（2026-10-12 修）。

    缺陷：清理用 LIKE 'book_%'，而 SQL 的  是**单字符通配符**——
    它会同时匹配 bookA1 / bookabc 等，而 book_id 可由 API 调用方任意指定
    （router 的 extract 端点取 b.get("book_id")）。实测：用户以 bookA1 建的
    书与资产，在下次 ensure_curated_library 时被静默删除（数据丢失）。

    修法：LIKE ? ESCAPE '\\\\' + 模式 'book\\\\_%'，让下划线只匹配字面量。

    注意现有用例的 book_id 恰好是 book_xuanhuan_01（真以 book_ 开头），
    因此从未暴露此缺陷——本用例专门用 bookA1 / bookabc 这类 ID。
    """

    def setUp(self):
        self._iso = _isolation.isolate_paths(Path(tempfile.mkdtemp(prefix="wildcard_")))
        self._iso.__enter__()
        db.init_schema()
        db.apply_migrations()

    def tearDown(self):
        db.close()
        self._iso.__exit__(None, None, None)

    def test_user_books_not_matching_literal_prefix_survive(self):
        """bookA1 / bookabc 这类 ID 不属于 book_ 前缀，必须幸存。"""
        for bid in ("bookA1", "bookabc", "bookZ9"):
            essence_service.create_or_update_book(
                book_id=bid, title=f"用户书{bid}", genre="xuanhuan")
            essence_service.create_asset(
                book_id=bid, category="hook", title="用户资产", content="用户内容")

        essence_service.ensure_curated_library(clean_raw_corpus=True)

        conn = db.get_conn()
        for bid in ("bookA1", "bookabc", "bookZ9"):
            n = conn.execute(
                "SELECT COUNT(*) FROM essence_books WHERE book_id=?", (bid,)).fetchone()[0]
            self.assertEqual(n, 1, f"用户书 {bid} 被垃圾清理误删（LIKE 通配符缺陷）")
            na = conn.execute(
                "SELECT COUNT(*) FROM essence_assets WHERE book_id=?", (bid,)).fetchone()[0]
            self.assertEqual(na, 1, f"用户书 {bid} 的资产被误删")

    def test_literal_book_prefix_garbage_is_cleaned(self):
        """反向守卫：真正以 book_ 开头的垃圾记录仍须被清理。"""
        for bid in ("book_1", "book_x", "book_生僻语料"):
            essence_service.create_or_update_book(
                book_id=bid, title="垃圾书", genre="xuanhuan")

        essence_service.ensure_curated_library(clean_raw_corpus=True)

        conn = db.get_conn()
        for bid in ("book_1", "book_x", "book_生僻语料"):
            n = conn.execute(
                "SELECT COUNT(*) FROM essence_books WHERE book_id=?", (bid,)).fetchone()[0]
            self.assertEqual(n, 0, f"垃圾书 {bid} 未被清理（清理逻辑失效）")

    def test_cleanup_does_not_touch_curated_or_other(self):
        """curated_ 前缀与普通 ID 都不受影响。"""
        essence_service.create_or_update_book(
            book_id="curated_mycustom", title="我的定制", genre="xuanhuan")
        essence_service.create_or_update_book(
            book_id="novel001", title="普通书", genre="xuanhuan")

        essence_service.ensure_curated_library(clean_raw_corpus=True)

        conn = db.get_conn()
        for bid in ("curated_mycustom", "novel001"):
            n = conn.execute(
                "SELECT COUNT(*) FROM essence_books WHERE book_id=?", (bid,)).fetchone()[0]
            self.assertEqual(n, 1, f"{bid} 不应被清理")

    def test_clean_raw_corpus_false_skips_cleanup(self):
        """clean_raw_corpus=False 时完全跳过清理。"""
        essence_service.create_or_update_book(
            book_id="book_keepme", title="保留", genre="xuanhuan")
        essence_service.ensure_curated_library(clean_raw_corpus=False)
        conn = db.get_conn()
        n = conn.execute(
            "SELECT COUNT(*) FROM essence_books WHERE book_id='book_keepme'").fetchone()[0]
        self.assertEqual(n, 1, "clean_raw_corpus=False 时不应清理")


if __name__ == "__main__":
    unittest.main()

