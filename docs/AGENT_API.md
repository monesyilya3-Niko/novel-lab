# novel-lab Agent 调用手册

面向外部智能体（Qoder / Cline / Claude / OpenCode / Antigravity 等）直接驱动
novel-lab 桌面后端进行小说工作。本文所有端点均经真实服务冒烟验证
（2026-10-04，`XUAN_DATA_DIR` 隔离环境）。

## 1. 启动后端

```bash
cd <novel-lab 根目录>
python3 -m gui.server --no-browser --port 8000
# 输出 [GUI] novel-lab 书籍分析服务已启动: http://127.0.0.1:8000/
# 端口被占时自动 +1（8000-8099）；单实例锁，重复启动会报错
# 也支持直接执行：python3 gui/server.py --no-browser --port 8000
```

用户数据目录默认 `~/.local/share/暮冬念春`
（Windows: `%LOCALAPPDATA%\暮冬念春`），可经 `XUAN_DATA_DIR` 环境变量覆盖。

## 2. 鉴权

- 未设置 `NOVEL_LAB_TOKEN` 时：本机请求无需鉴权。
- 设置了时：请求头 `X-Auth-Token: <token>`，或查询参数 `?auth=<token>`。
- CSRF：只校验带 `Origin`/`Referer` 的浏览器请求；Agent（curl/HTTP 库，
  无 Origin 头）不受影响，可直接发 POST/PUT/DELETE。

## 3. 通用约定

- 基地址：`http://127.0.0.1:<port>`，下文记为 `$B`。
- 响应信封统一为 JSON：`{"code": 0, "data": {...}, "message": ""}`。
  `code != 0` 即失败，看 `message`（如 `400 非法资产引用`、`404 资产不存在`、
  `429 写作任务已达上限`）。
- **非 ASCII 查询参数必须 percent-encode**（服务端按标准解码；裸传中文会乱码
  导致 404）。curl 用法：`curl -G "$B/api/writing/export" --data-urlencode "project=我的书"`；
  Python 用 `urllib.parse.quote`。项目 JSON body 不受影响。
- 资产引用格式为 `<kind>:<id>`，如 `"voice:chireng_chosen-voice-card"`，
  对应资产目录下 `<id>.json`。kind 错配（如拿蒸馏卡当 voice）会 400。
- 项目名禁 `default`（CLI 只读）、禁 `/ \ ..` 等。

### 3.1 发现可用资产

```bash
# kind 取值：voice / structure / commercial / craft / genre_pack / prose_card / trope
curl -s "$B/api/assets?kind=voice&limit=50" | python3 -c "
import json,sys
for it in json.load(sys.stdin)['data']['items']:
    print(it['id'])"   # 直接可用作 voice 参数，如 voice:chireng_chosen-voice-card

# 单个资产详情：注意 id 必须带 kind: 前缀（与列表返回的 id 字段完全一致）
curl -s "$B/api/assets/voice/voice:Lord_of_the_Mysteries-voice-card" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['data'];
print(d['kind'], d['name'], 'keys:', list(d['content'].keys()))"
```

## 4. 核心工作流

### 4.1 无 LLM 时的推荐流程（降级协作）

无模型时 `POST /api/writing/generate` **不会报错**，而是返回降级指引
（`status: "degraded"`, `mode: "no_model"`），并在项目目录落盘
`AI接管写作任务.md`（含任务、system prompt、及格线、操作步骤）。

```bash
# 1. 取写作指引（无模型）
curl -s -X POST $B/api/writing/generate -H 'Content-Type: application/json' \
  -d '{"project":"我的书","chapter_no":1,"task":"主角入学",
       "voice":"voice:chireng_chosen-voice-card","words":2400}' \
| python3 -c "import json,sys; d=json.load(sys.stdin)['data'];
print(d['status'], d['guide_path']); print(d['notice'])"
# → degraded  AI接管写作任务.md  未配置外部模型：请把指引与 prompt 交给会话内智能写作…

# 2. Agent 在外部写完正文后，手动入库（自动落盘 + 双维度打分）
curl -s -X POST $B/api/writing/chapters -H 'Content-Type: application/json' \
  -d '{"project":"我的书","chapter_no":1,"content":"正文……",
       "voice":"voice:chireng_chosen-voice-card"}'
# → {"code":0,"data":{"chapter_path":"arc-1/chapter-001.txt","chapter_no":1,
#     "char_count":1234,"consistency_score":92.5,"quality_score":88,
#     "quality_verdict":"PASS","pass_line":85,"overwrote":false}}
# overwrote=true 表示覆盖了已存在的章节；重复入库只记字数增量（改短则扣减），
# 不重复累加章节数——入库本身是幂等的，无需 Agent 自行去重
```

### 4.1b 单独取写作 prompt（注入）

```bash
# 资产 → 写作 prompt，不启动生成任务；返回 prompt 全文 + 注入的资产维度
curl -s -X POST $B/api/writing/inject -H 'Content-Type: application/json' \
  -d '{"voice":"voice:chireng_chosen-voice-card","prose_card":"prose_card:xxx"}'
# → {"code":0,"data":{"prompt":"……","char_count":3210,
#     "injected_kinds":["voice","prose_card"],"meta":{...}}}
# Agent 自己写正文时，用这个 prompt 当 system prompt
```

### 4.2 有 LLM 时的一键生成

```bash
curl -s -X POST $B/api/writing/generate -H 'Content-Type: application/json' \
  -d '{"project":"我的书","chapter_no":2,"task":"主角入学",
       "voice":"voice:chireng_chosen-voice-card","target_score":90}'
# → {"code":0,"data":{"task_id":"w-xxxx","status":"running","mode":"llm",...}}

# 轮询任务状态（初稿 + 最多 2 轮改写，完成后 status 为 done）
curl -s $B/api/writing/tasks/w-xxxx
# 或订阅 SSE 看进度：curl -N $B/api/events
#   事件示例：{"task_type":"writing","task_id":"w-xxxx","phase":"generating","attempt":1}
#   phase 取值：generating → scored → done / error
```

### 4.3 打分（纯算法，无需 LLM）

```bash
# 一致性打分（voice-card 算法）+ 质量十二维；text 与 chapter_path 二选一
curl -s -X POST $B/api/writing/score -H 'Content-Type: application/json' \
  -d '{"voice":"voice:chireng_chosen-voice-card","text":"正文……","label":"第1章"}'
# → {"code":0,"data":{"consistency":{"score":92.5,"dims":{...},"details":[...]},
#     "quality":{"score":88,...},"verdict":"PASS","pass_line":75}}
# 章节入库时已自动打分；此接口用于单独对任意文本打分
```

### 4.4 项目 / 大纲 / 人物卡 / 便签

```bash
curl -s $B/api/writing/projects                                  # 项目列表
curl -s -X POST $B/api/writing/projects -H 'Content-Type: application/json' \
  -d '{"name":"我的书"}'                                          # 新建项目

curl -s -G $B/api/writing/outlines --data-urlencode "project=我的书"  # 大纲列表
curl -s -X POST $B/api/writing/outlines -H 'Content-Type: application/json' \
  -d '{"project":"我的书","kind":"chapter","title":"第1章","summary":"入学"}'
curl -s -X PUT $B/api/writing/outlines/1 -H 'Content-Type: application/json' \
  -d '{"status":"writing"}'                                       # planned/writing/done
curl -s -X DELETE $B/api/writing/outlines/1

# 人物卡 /api/writing/characters，灵感便签 /api/writing/notes：同 CRUD 形状
# 人物卡字段：{"project","name","role","description","extra":{}}
# 便签字段：{"project","title","content"}
```

### 4.5 统计与导出

```bash
curl -s -G "$B/api/writing/stats" --data-urlencode "project=我的书" --data-urlencode "days=7"
# → {"code":0,"data":{"project":"我的书","today_words":1234,"today_chapters":1,...}}

curl -s -G "$B/api/writing/export" --data-urlencode "project=我的书" \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['data'];
print(d['filename'], d['chapters'], '章', d['words'], '字')"
# → {"code":0,"data":{"filename":"我的书-全书导出-2026-10-04.txt",
#     "content":"第1章\n\n正文……\n","chapters":1,"words":1234}}
```

## 5. CLI 备选（不起服务时）

```bash
python3 novel.py 打分 <voice-card.json> <章节.txt>   # 一致性打分（纯算法）
python3 novel.py 校验 <资产.json> --kind voice-card  # schema 校验
python3 novel.py 注入 <voice-card.json>              # 资产 → 写作 prompt
python3 novel.py 报告 <voice-card.json>              # 拆书报告
# 注意：CLI 输出是给人看的文本（含 ✅/⚠️/❌），Agent 解析不如 API 的 JSON 可靠；
# `novel 写作` 需要 LLM，无模型时用 API 降级流程代替。
```

## 6. 模型配置（启用一键生成）

```bash
curl -s $B/api/config/models          # 查看已配模型（不含密钥）
curl -s -X POST $B/api/models -H 'Content-Type: application/json' \
  -d '{"id":"my-deepseek","protocol":"openai",
       "base_url":"https://api.deepseek.com/v1","model_name":"deepseek-chat",
       "api_key_env":"DEEPSEEK_API_KEY"}'
# 密钥走环境变量名或密钥存储，不直接写明文 key；
# 也可以：export OPENAI_API_KEY=... 或 python scripts/model_config.py key <id>
```

## 7. Agent 注意事项

1. **写操作幂等性**：`import_chapter` / AI 生成重复落盘同一章节时，
   字数统计只记增量（`overwrote=true`），不重复累加；无需 Agent 自行去重。
2. **并发上限**：同时最多 2 个写作任务，超了返回 429。
3. **项目名**：先 `GET /api/writing/projects` 确认存在再写；`default` 项目只读。
4. **voice 必填**：`generate` 的 `voice` 不能为空且必须引用真实资产；
   `import_chapter` 的 `voice` 可选（不传则只落盘不打分）。
5. **不要猜测端点**：本手册之外的路径以 `gui/router.py` 的 `ROUTES` 表为准。
