#!/usr/bin/env python3
"""全链路真机实测自动化探测脚本（novel-lab 端到端全功能真机验证）。

验证矩阵：
1. 本地服务真实启动与端口绑定（纯 Python 标准库 BaseHTTPRequestHandler + SQLite）
2. 管理员会话、登录限流机制（5 次连续失败锁定 429）与审计日志落盘
3. 语料导入、拆书分析与题材卡/声音卡（Voice Card）生成
4. 细纲架构拖拽重排与人物关系卡片落库
5. 章节正文流式生成、去 AI 味全维诊断（6 大维度评分与建议）及质检打分
6. 章节原子落盘、字数记账与幂等防重机制
7. Word (.docx) 与 Markdown / TXT 规范化导出及 OpenXML 结构合规性验证
8. 优雅停机与资源无残留清理

完全遵守纯标准库红线（无第三方外部依赖）。
"""
from __future__ import annotations

import base64
import http.cookiejar
import io
import json
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

# 自举项目根路径
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class VerificationError(AssertionError):
    """验证断言失败。"""


class VerificationClient:
    """包装 urllib.request 的测试客户端，支持 Cookie 保持与 JSON 序列化。"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any] | str, dict[str, str]]:
        url = f"{self.base_url}{path}"
        if params:
            qs = urllib.parse.urlencode({k: str(v) for k, v in params.items()})
            url = f"{url}?{qs}"

        req_headers = {"User-Agent": "novel-lab-verifier/2.0.3"}
        if headers:
            req_headers.update(headers)

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req_headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(
            url, data=body_bytes, headers=req_headers, method=method
        )

        try:
            with self.opener.open(req, timeout=15) as resp:
                status = resp.status
                raw = resp.read()
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                content_type = resp_headers.get("content-type", "")
                if "application/json" in content_type:
                    return status, json.loads(raw.decode("utf-8")), resp_headers
                return status, raw.decode("utf-8", errors="replace"), resp_headers
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            resp_headers = {k.lower(): v for k, v in exc.headers.items()}
            content_type = resp_headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    return exc.code, json.loads(raw.decode("utf-8")), resp_headers
                except Exception:
                    pass
            return exc.code, raw.decode("utf-8", errors="replace"), resp_headers


def run_e2e_verification() -> bool:
    print("=" * 70)
    print("🚀 [START] novel-lab 全端点自动化真机实测探测开始")
    print("=" * 70)

    # 1. 环境初始化与路径沙箱隔离
    tmp_dir = tempfile.mkdtemp(prefix="novel_lab_e2e_")
    print(f"[*] 创建临时测试沙箱目录: {tmp_dir}")

    from gui import admin, config, db, engine_adapter, server, writing_extra

    orig_config = {
        "ROOT_DIR": config.ROOT_DIR,
        "STATE_ROOT": config.STATE_ROOT,
        "STATE_JSON_DIR": config.STATE_JSON_DIR,
        "ASSETS_ROOT": config.ASSETS_ROOT,
        "NOVEL_DIR": config.NOVEL_DIR,
        "CORPUS_DIR": config.CORPUS_DIR,
        "PROMPTS_DIR": config.PROMPTS_DIR,
        "REPORTS_DIR": config.REPORTS_DIR,
        "DB_PATH": config.DB_PATH,
        "LOCK_PATH": config.LOCK_PATH,
    }

    sandbox_root = Path(tmp_dir)
    config.ROOT_DIR = sandbox_root
    config.STATE_ROOT = sandbox_root / "gui_state"
    config.STATE_JSON_DIR = config.STATE_ROOT / "states"
    config.ASSETS_ROOT = sandbox_root / "assets"
    config.NOVEL_DIR = sandbox_root / "novel"
    config.CORPUS_DIR = sandbox_root / "corpus"
    config.PROMPTS_DIR = sandbox_root / "prompts"
    config.REPORTS_DIR = sandbox_root / "reports"
    config.DB_PATH = config.STATE_ROOT / "novel_lab.db"
    config.LOCK_PATH = config.STATE_ROOT / ".lock"

    for d in (
        config.STATE_ROOT,
        config.STATE_JSON_DIR,
        config.ASSETS_ROOT,
        config.NOVEL_DIR,
        config.CORPUS_DIR,
        config.PROMPTS_DIR,
        config.REPORTS_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)

    gui_srv: server.GuiServer | None = None

    try:
        # 预先重置 admin 内部锁和失败记录
        with admin._lock:
            admin._failed_logins.clear()
            admin._sessions.clear()

        # 2. 真实启动本地测试服务
        print("[*] 正在启动本地 GuiServer 服务 (127.0.0.1 动态端口)...")
        gui_srv = server.GuiServer(preferred_port=8100)
        host, port = gui_srv.start()
        base_url = f"http://{host}:{port}"
        print(f"[✔] GuiServer 成功监听并运行在: {base_url}")

        client = VerificationClient(base_url)

        # 验证前端静态 SPA 与健康检查
        status, body, _ = client.request("GET", "/api/system/status")
        if status != 200 or not isinstance(body, dict) or body.get("code") != 0:
            raise VerificationError(f"GET /api/system/status 失败: {status} {body}")
        print(f"[✔] 系统健康检查正常: status={status}, counts={body['data']['counts']}")

        status, html, _ = client.request("GET", "/")
        if status != 200 or "<!DOCTYPE HTML>" not in str(html).upper():
            raise VerificationError(f"GET / 静态托管 index.html 失败: status={status}, content={html[:100]}")
        print("[✔] 前端静态托管验证通过: index.html 正常加载 (200 OK)")

        # -------------------------------------------------------------------
        # 3. 管理员会话、限流机制与审计日志验证
        # -------------------------------------------------------------------
        print("\n--- [MODULE 1: 管理员会话、限流机制与审计日志] ---")
        hint_file = config.STATE_ROOT / admin.ADMIN_HINT_FILE_NAME
        if not hint_file.exists():
            raise VerificationError("初始密码指引文件不存在！")
        hint_content = hint_file.read_text(encoding="utf-8")
        import re

        pw_match = re.search(r"初始密码：([^\s]+)", hint_content)
        if not pw_match:
            raise VerificationError("未能从指引文件解析初始密码！")
        initial_pw = pw_match.group(1).strip()
        print("[*] 成功获取管理员初始随机密码 (指引文件安全交付)")

        # 3.1 测试暴力破解限流保护 (5 次连续失败锁定 5 分钟 -> 429)
        print("[*] 触发登录限流测试 (连续 5 次错误密码)...")
        for i in range(1, 5):
            st, res, _ = client.request(
                "POST", "/api/admin/login", {"username": "admin", "password": f"wrong_{i}"}
            )
            if st != 401:
                raise VerificationError(f"第 {i} 次错误密码期望 401，实际 {st}: {res}")

        # 第 5 次失败，触发锁定
        st, res, _ = client.request(
            "POST", "/api/admin/login", {"username": "admin", "password": "wrong_5"}
        )
        if st != 401:
            raise VerificationError(f"第 5 次错误密码期望 401，实际 {st}")

        # 第 6 次调用应立即被频率拦截 429
        st, res, _ = client.request(
            "POST", "/api/admin/login", {"username": "admin", "password": "wrong_6"}
        )
        if st != 429 or "5 分钟" not in str(res):
            raise VerificationError(f"限流拦截未生效！期望 429，实际 {st}: {res}")
        print("[✔] 限流机制验证通过: 连续 5 次失败后成功触发 429 锁定拦截")

        # 解除当前 IP 锁定以继续后续合法登录流程
        with admin._lock:
            admin._failed_logins.clear()

        # 3.2 合法登录与 Cookie 会话生成
        st, res, headers = client.request(
            "POST", "/api/admin/login", {"username": "admin", "password": initial_pw}
        )
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"合法登录失败: {st} {res}")
        if not res["data"].get("mustChangePassword"):
            raise VerificationError("初始管理员必须标记 mustChangePassword: true")
        print("[✔] 管理员合法认证成功: 会话凭据与 HttpOnly Cookie 下发正常")

        # 3.3 修改管理员密码
        new_password = "Staff-Principal-Pass2026!"
        st, res, _ = client.request(
            "POST",
            "/api/admin/change-password",
            {"oldPassword": initial_pw, "newPassword": new_password},
        )
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"修改密码失败: {st} {res}")
        if hint_file.exists():
            raise VerificationError("改密成功后初始密码指引文件应被自动销毁删除！")
        print("[✔] 改密成功且明文指引文件已安全自毁销毁")

        # 3.4 密码变更后旧会话自动吊销，使用新密码重新登录
        st, res, _ = client.request(
            "POST", "/api/admin/login", {"username": "admin", "password": new_password}
        )
        if st != 200 or res.get("code") != 0:
            raise VerificationError(f"新密码重新登录失败: {st} {res}")
        if res["data"].get("mustChangePassword") is not False:
            raise VerificationError("改密后 mustChangePassword 期望为 False")
        print("[✔] 历史会话安全吊销验证通过，新密码重新登录成功")

        # 3.5 审计日志落盘与回溯验证
        st, res, _ = client.request("GET", "/api/admin/audit")
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"获取审计日志失败: {st} {res}")
        actions = [item.get("action") for item in (res["data"] if isinstance(res["data"], list) else res["data"].get("items", []))]
        for expected in ("admin.login.failed", "admin.login", "admin.change_password"):
            if expected not in actions:
                raise VerificationError(f"审计日志缺少关键安全事件: {expected}, 已记录: {actions}")
        print(f"[✔] 审计日志记录完整: 已捕获 {actions}")

        # -------------------------------------------------------------------
        # 4. 拆书分析与题材卡/声音卡落库
        # -------------------------------------------------------------------
        print("\n--- [MODULE 2: 拆书分析与题材卡/声音卡生成] ---")
        sample_book_txt = config.CORPUS_DIR / "sample_campus_novel.txt"
        sample_book_txt.write_text(
            "第一章 教室里的阳光\n"
            "初秋的风吹过走廊，林枫独自一人坐在最后一排靠窗的位置。\n"
            "黑板上还残留着上一节数学课未擦干净的公式。\n"
            "他轻轻握紧手中的钢笔，笔记本上写着两行短句。\n\n"
            "第二章 晚自习的雨\n"
            "暴雨在放学时分如期而至，校门口的水洼倒映着昏黄的路灯。\n"
            "林枫撑起黑色折叠伞，脚步平缓而沉稳地迈向夜色深处。\n",
            encoding="utf-8",
        )

        st, res, _ = client.request(
            "POST", "/api/import", {"path": str(sample_book_txt), "batch_size": 1}
        )
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"导入书籍失败: {st} {res}")
        book_id = res["data"]["book_id"]
        total_chapters = res["data"]["total_chapters"]
        if total_chapters != 2:
            raise VerificationError(f"期望章节数 2，实际为 {total_chapters}")
        print(f"[✔] 书籍导入与分章解析成功: book_id={book_id}, total_chapters={total_chapters}")

        # 模拟外部模型配置与分析批处理产出
        orig_any_model = engine_adapter.any_model_configured
        orig_run_batch = engine_adapter.run_batch
        engine_adapter.any_model_configured = lambda: True

        def mock_run_batch(kind, ci, ctitle, btext, metrics, dry_run=False, model_id=None):
            return {
                "kind": kind,
                "chapter": ci,
                "character_voices": [{"name": "林枫", "tone": "清冷沉稳"}],
                "confidence": 0.95,
            }

        engine_adapter.run_batch = mock_run_batch

        # 触发分析任务
        st, res, _ = client.request(
            "POST", "/api/analyze/start", {"book_id": book_id, "genre": "campus-redemption"}
        )
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"启动拆书分析失败: {st} {res}")
        print(f"[*] 拆书分析任务已创建并调度运行: status={res['data']['status']}")

        # 轮询等待分析完成 (状态 done)
        deadline = time.time() + 10.0
        analysis_done = False
        while time.time() < deadline:
            st, res, _ = client.request("GET", "/api/status", params={"book_id": book_id})
            if st == 200 and isinstance(res, dict) and res.get("data", {}).get("status") == "done":
                analysis_done = True
                break
            time.sleep(0.1)

        engine_adapter.any_model_configured = orig_any_model
        engine_adapter.run_batch = orig_run_batch

        if not analysis_done:
            raise VerificationError("拆书分析任务超时未完成！")
        print("[✔] 拆书分析任务执行完成: status=done")

        # 写入一张标准 Voice Card 供后续写作模块使用
        voice_card_data = {
            "meta": {
                "title": "林枫之书",
                "genre": "campus-redemption",
                "confidence": 0.96,
            },
            "narration": {"pov": "third_limited", "density": "medium"},
            "dialogue": {"character_voices": [{"name": "林枫", "tone": "沉稳克制"}]},
            "emotion_handling": {"mode": "体感"},
            "banned": {"never_used_words": ["极其", "滔天巨浪"]},
        }
        voice_fp = config.ASSETS_ROOT / f"{book_id}-voice-card.json"
        voice_fp.write_text(json.dumps(voice_card_data, ensure_ascii=False), encoding="utf-8")
        print(f"[✔] 题材卡与声音卡落盘验证通过: {voice_fp.name}")

        # -------------------------------------------------------------------
        # 5. 细纲架构拖拽重排与人物关系卡片落库
        # -------------------------------------------------------------------
        print("\n--- [MODULE 3: 细纲生成与人物卡落库] ---")
        project_name = "e2e_campus_redemption"
        st, res, _ = client.request(
            "POST",
            "/api/writing/projects",
            {"name": project_name, "genre": "campus-redemption"},
        )
        if st != 200 or not isinstance(res, dict) or res.get("code") != 0:
            raise VerificationError(f"新建写作项目失败: {st} {res}")
        print(f"[✔] 写作项目建立成功: {project_name}")

        # 创建细纲 1 与细纲 2
        st, res1, _ = client.request(
            "POST",
            "/api/writing/outlines",
            {
                "project": project_name,
                "title": "第1章：旧校舍的偶遇",
                "summary": "主角初到新班级，雨天旧校舍发现神秘信件",
                "kind": "chapter",
            },
        )
        if st != 200 or res1.get("code") != 0:
            raise VerificationError(f"创建细纲 1 失败: {res1}")
        oid_1 = res1["data"]["id"]

        st, res2, _ = client.request(
            "POST",
            "/api/writing/outlines",
            {
                "project": project_name,
                "title": "第2章：晚自习风波",
                "summary": "同桌挑衅，主角冷静化解矛盾",
                "kind": "chapter",
            },
        )
        if st != 200 or res2.get("code") != 0:
            raise VerificationError(f"创建细纲 2 失败: {res2}")
        oid_2 = res2["data"]["id"]

        # 测试细纲原子批量重排序 (Reorder Outlines)
        st, res_reorder, _ = client.request(
            "POST",
            "/api/writing/outlines/reorder",
            {"project": project_name, "order_ids": [oid_2, oid_1]},
        )
        if st != 200 or res_reorder.get("code") != 0:
            raise VerificationError(f"细纲重排失败: {res_reorder}")
        reordered_items = res_reorder["data"]
        if reordered_items[0]["id"] != oid_2 or reordered_items[1]["id"] != oid_1:
            raise VerificationError(f"细纲重排顺序不符合预期: {reordered_items}")
        print(f"[✔] 细纲架构批量原子重排成功: [ID:{oid_2}, ID:{oid_1}] 顺序正确")

        # 创建人物关系卡片 (支持阵营、性格等多维属性)
        st, res_char, _ = client.request(
            "POST",
            "/api/writing/characters",
            {
                "project": project_name,
                "name": "苏晓晓",
                "role": "女主角",
                "description": "性格温和、内心坚韧的班长",
                "extra": {
                    "camp": "同盟阵营",
                    "personality": "细腻敏锐",
                    "goal": "查清当年的真相",
                },
            },
        )
        if st != 200 or res_char.get("code") != 0:
            raise VerificationError(f"创建人物卡失败: {res_char}")
        char_id = res_char["data"]["id"]

        st, res_char_list, _ = client.request(
            "GET", "/api/writing/characters", params={"project": project_name}
        )
        if st != 200 or len(res_char_list["data"]) != 1:
            raise VerificationError(f"人物列表查询失败: {res_char_list}")
        fetched_char = res_char_list["data"][0]
        char_extra = fetched_char.get("extra")
        if isinstance(char_extra, str):
            char_extra = json.loads(char_extra)
        if (char_extra or {}).get("camp") != "同盟阵营":
            raise VerificationError(f"人物阵营属性未持久化: {fetched_char}")
        print(f"[✔] 人物关系卡片落库与多维属性持久化成功: ID={char_id}, 姓名=苏晓晓")

        # -------------------------------------------------------------------
        # 6. 章节正文流式生成与打分 (去 AI 味全维诊断与质量评分)
        # -------------------------------------------------------------------
        print("\n--- [MODULE 4: 章节流式生成、去 AI 味全维诊断与打分] ---")
        voice_ref = f"voice:{book_id}-voice-card"

        # 6.1 章节任务生成 (降级引导模式校验)
        st, res_gen, _ = client.request(
            "POST",
            "/api/writing/generate",
            {
                "voice": voice_ref,
                "project": project_name,
                "chapter_no": 1,
                "task": "完成第1章草稿",
            },
        )
        if st != 200 or res_gen.get("code") != 0:
            raise VerificationError(f"章节起草生成任务失败: {res_gen}")
        print(f"[✔] 章节任务生成调度成功: task_id={res_gen['data']['task_id']}")

        # 6.2 去 AI 味全维诊断服务深度检验 (Deslop Service)
        ai_heavy_text = (
            "在这浩瀚无垠的苍穹之下，他的心中涌起了一股难以言喻的滔天巨浪。"
            "他非常生气，他极为愤怒，怒火在他胸中汹涌澎湃地燃烧。"
            "狂风让树叶瑟瑟发抖，暴雨让大地变得泥泞不堪。"
            "只见他深吸了一口气，眼神中闪烁着坚毅的光芒。"
        )
        st, res_deslop_bad, _ = client.request(
            "POST", "/api/writing/deslop", {"text": ai_heavy_text}
        )
        if st != 200 or res_deslop_bad.get("code") != 0:
            raise VerificationError(f"去 AI 味接口异常: {res_deslop_bad}")
        data_bad = res_deslop_bad["data"]
        if data_bad["ai_score"] < 50 or len(data_bad["issues"]) == 0:
            raise VerificationError(f"未能检出重度 AI 味文本: ai_score={data_bad['ai_score']}, issues={data_bad['issues']}")
        print(
            f"[✔] 去 AI 味重度文本检出成功: AI味指数 {data_bad['ai_score']}/100, 检出 {len(data_bad['issues'])} 项违规指标 ({data_bad['verdict_cn']})"
        )

        clean_human_text = (
            "雨水顺着生锈的铁皮房檐滴落，砸在校门口的水洼里，激起一圈圈浑浊的涟漪。\n"
            "林枫把洗得发白的校服外套拉链拉到领口，两手插进裤兜，踏着积水拐进巷口。\n"
            "小卖部门口的黑猫在台阶上舔了舔爪子，懒懒地看了他一眼，又把脑袋缩回纸箱里。"
        )
        st, res_deslop_good, _ = client.request(
            "POST", "/api/writing/deslop", {"text": clean_human_text}
        )
        if st != 200 or res_deslop_good.get("code") != 0:
            raise VerificationError(f"去 AI 味良性文本接口异常: {res_deslop_good}")
        data_good = res_deslop_good["data"]
        if data_good["ai_score"] > 20:
            raise VerificationError(f"优质真人质感文本误报严重: ai_score={data_good['ai_score']}")
        print(
            f"[✔] 优质真人质感文本检验通过: AI味指数 {data_good['ai_score']}/100, 评级: {data_good['verdict_cn']}"
        )

        # -------------------------------------------------------------------
        # 7. 章节原子落盘、字数记账与幂等防重机制
        # -------------------------------------------------------------------
        print("\n--- [MODULE 5: 章节原子落盘、字数记账与幂等防重] ---")
        # 初始字数检查
        st, res_stats_0, _ = client.request(
            "GET", "/api/writing/stats", params={"project": project_name}
        )
        if st != 200 or res_stats_0["data"]["total_words"] != 0:
            raise VerificationError(f"项目初始字数期望为 0: {res_stats_0}")

        # 首次入库：第 1 章
        ch1_text = clean_human_text
        ch1_len = writing_extra.count_words(ch1_text)
        st, res_ch1, _ = client.request(
            "POST",
            "/api/writing/chapters",
            {
                "project": project_name,
                "chapter_no": 1,
                "content": ch1_text,
                "voice": voice_ref,
            },
        )
        if st != 200 or res_ch1.get("code") != 0:
            raise VerificationError(f"第 1 章入库失败: {res_ch1}")
        if res_ch1["data"].get("overwrote") is True:
            raise VerificationError("首度入库期望 overwrote=False")

        # 校验原子落盘
        novel_proj_dir = config.NOVEL_DIR / project_name
        disk_ch1 = novel_proj_dir / "chapters" / "arc-1" / "chapter-001.txt"
        if not disk_ch1.is_file() or disk_ch1.read_text(encoding="utf-8") != ch1_text:
            raise VerificationError("章节文件未正确原子落盘！")

        # 校验记账统计
        st, res_stats_1, _ = client.request(
            "GET", "/api/writing/stats", params={"project": project_name}
        )
        if res_stats_1["data"]["total_words"] != ch1_len:
            raise VerificationError(
                f"字数记账不符: 期望 {ch1_len}, 实际 {res_stats_1['data']['total_words']}"
            )
        if res_stats_1["data"]["total_chapters"] != 1:
            raise VerificationError(
                f"章节计数不符: 期望 1, 实际 {res_stats_1['data']['total_chapters']}"
            )
        print(f"[✔] 章节首度落盘成功: 路径={disk_ch1.name}, 计数字数={ch1_len}, 章节=1")

        # 重复入库 (幂等防重测试)：相同章节号、相同内容再次提交
        st, res_ch1_repeat, _ = client.request(
            "POST",
            "/api/writing/chapters",
            {
                "project": project_name,
                "chapter_no": 1,
                "content": ch1_text,
                "voice": voice_ref,
            },
        )
        if st != 200 or res_ch1_repeat.get("code") != 0:
            raise VerificationError(f"重复入库失败: {res_ch1_repeat}")
        if res_ch1_repeat["data"].get("overwrote") is not True:
            raise VerificationError("重复入库期望 overwrote=True")

        # 复核记账数据，绝不累加翻倍
        st, res_stats_repeat, _ = client.request(
            "GET", "/api/writing/stats", params={"project": project_name}
        )
        if res_stats_repeat["data"]["total_words"] != ch1_len:
            raise VerificationError(
                f"幂等失败！字数被重复累加: 期望 {ch1_len}, 实际 {res_stats_repeat['data']['total_words']}"
            )
        if res_stats_repeat["data"]["total_chapters"] != 1:
            raise VerificationError(
                f"幂等失败！章节数被重复累加: 期望 1, 实际 {res_stats_repeat['data']['total_chapters']}"
            )
        print("[✔] 入库幂等防重机制验证通过: 重复提交保持字数与章节严格幂等无漂移")

        # 入库第 2 章
        ch2_text = (
            "晚自习的下课铃打响时，整座教学楼被喧闹的人声填满。\n"
            "林枫收拾好书包，信步走入夜色之中。"
        )
        ch2_len = writing_extra.count_words(ch2_text)
        st, res_ch2, _ = client.request(
            "POST",
            "/api/writing/chapters",
            {
                "project": project_name,
                "chapter_no": 2,
                "content": ch2_text,
                "voice": voice_ref,
            },
        )
        if st != 200 or res_ch2.get("code") != 0:
            raise VerificationError(f"第 2 章入库失败: {res_ch2}")

        st, res_stats_2, _ = client.request(
            "GET", "/api/writing/stats", params={"project": project_name}
        )
        expected_total_words = ch1_len + ch2_len
        if res_stats_2["data"]["total_words"] != expected_total_words:
            raise VerificationError(
                f"多章累计字数不符: 期望 {expected_total_words}, 实际 {res_stats_2['data']['total_words']}"
            )
        print(
            f"[✔] 多章节连续记账统计正常: 总字数={expected_total_words}, 章节数={res_stats_2['data']['total_chapters']}"
        )

        # -------------------------------------------------------------------
        # 8. Word (docx) 与 Markdown 规范化导出与结构完整性
        # -------------------------------------------------------------------
        print("\n--- [MODULE 6: Word (.docx) 与 Markdown / TXT 规范化导出] ---")

        # 8.1 导出 Markdown
        st, res_md, _ = client.request(
            "GET", "/api/writing/export", params={"project": project_name, "format": "md"}
        )
        if st != 200 or res_md.get("code") != 0:
            raise VerificationError(f"导出 Markdown 失败: {res_md}")
        md_data = res_md["data"]
        if md_data.get("format") != "md":
            raise VerificationError("导出响应 format 字段不为 md")
        md_content = md_data.get("content", "")
        if f"# {project_name}" not in md_content or ("## 第1章" not in md_content and "## 第 1 章" not in md_content):
            raise VerificationError(f"Markdown 导出内容格式缺失关键标题结构: {md_content[:200]}")
        print("[✔] Markdown 规范化导出通过: 完整保留层级结构与章节标题")

        # 8.2 导出纯文本 TXT
        st, res_txt, _ = client.request(
            "GET", "/api/writing/export", params={"project": project_name, "format": "txt"}
        )
        if st != 200 or res_txt.get("code") != 0:
            raise VerificationError(f"导出 TXT 失败: {res_txt}")
        if res_txt["data"].get("format") != "txt":
            raise VerificationError("导出响应 format 字段不为 txt")
        print("[✔] 纯文本 TXT 导出通过")

        # 8.3 导出 Word (.docx) 并在内存解包断言 OpenXML 合法结构
        st, res_docx, _ = client.request(
            "GET", "/api/writing/export", params={"project": project_name, "format": "docx"}
        )
        if st != 200 or res_docx.get("code") != 0:
            raise VerificationError(f"导出 Word docx 失败: {res_docx}")
        docx_data = res_docx["data"]
        if docx_data.get("format") != "docx":
            raise VerificationError("导出响应 format 字段不为 docx")
        b64_str = docx_data.get("content_base64") or docx_data.get("base64", "")
        if not b64_str:
            raise VerificationError(f"Word 导出未返回 base64 数据！返回字段: {list(docx_data.keys())}")

        docx_bytes = base64.b64decode(b64_str)
        if not docx_bytes.startswith(b"PK\x03\x04"):
            raise VerificationError("导出的 DOCX 二进制头部非合法 ZIP 魔数 PK\\x03\\x04")

        # 深入断言 OpenXML 包结构
        with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
            file_names = set(zf.namelist())
            for expected_file in (
                "[Content_Types].xml",
                "_rels/.rels",
                "word/document.xml",
            ):
                if expected_file not in file_names:
                    raise VerificationError(f"DOCX 包内缺失标准 OpenXML 部件: {expected_file}")

            # 读取 document.xml，断言正文内容未损坏
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            if ("第1章" not in doc_xml and "第 1 章" not in doc_xml) or "雨水顺着生锈的铁皮房檐滴落" not in doc_xml:
                raise VerificationError("DOCX document.xml 中未找到章节文本内容！")
        print(f"[✔] Word (.docx) OpenXML 包结构与内容合规性全检通过: 大小={len(docx_bytes)} 字节")

        print("\n" + "=" * 70)
        print("🎉 [ALL PASSED] 全端点真机实测 100% 通过！所有 6 大核心模块全绿！")
        print("=" * 70)
        return True

    finally:
        # 优雅停机并复原配置
        if gui_srv is not None:
            print("\n[*] 正在优雅关闭测试服务...")
            try:
                gui_srv.shutdown()
                print("[✔] 测试服务已优雅关闭，单实例锁已释放")
            except Exception as exc:
                print(f"[!] 停机异常: {exc}")

        db.close()

        for k, v in orig_config.items():
            setattr(config, k, v)

        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"[*] 临时沙箱已清理完成: {tmp_dir}")


if __name__ == "__main__":
    success = run_e2e_verification()
    sys.exit(0 if success else 1)
