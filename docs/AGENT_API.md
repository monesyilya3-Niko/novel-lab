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

> **Windows 上把 `python3` 换成 `python`**（本文其余示例同理，不再逐处标注）。
> 实测：本机 `python3` 命中 `WindowsApps\python3.exe` 商店别名，`-V` 无任何输出、退出码 49，
> `python3 -c "print('ok')"` 也一样静默——照抄本文命令会得到"什么都没发生"的假成功。
> 解释器名按平台替换：macOS/Linux 用 `python3`，Windows 用 `python`。

用户数据目录默认 `~/.local/share/暮冬念春`
（Windows: `%LOCALAPPDATA%\暮冬念春`），可经 `XUAN_DATA_DIR` 环境变量覆盖。

## 2. 鉴权

- 未设置 `NOVEL_LAB_TOKEN` 时：本机请求无需鉴权。
- 设置了时：请求头 `X-Auth-Token: <token>`，或查询参数 `?auth=<token>`。
- CSRF：只校验带 `Origin`/`Referer` 的浏览器请求；Agent（curl/HTTP 库，
  无 Origin 头）不受影响，可直接发 POST/PUT/DELETE。

### 2.1 Electron 握手令牌（桌面安装版必读；2026-10-08 实机复现）

同一个 `--no-browser` 标志，在两个入口的行为**不一样**（下表均为实测，不是读代码猜的）：

| 启动方式 | `/api/*` 是否要握手令牌 | 实测证据 |
|---|---|---|
| §1 的命令：`python -m gui.server --no-browser --port 8123` | **不要**。不带、带错、带对都返回 200 | `gui/server.py::main()` 只用该标志决定是否弹浏览器，从不生成 `handshake_token` |
| 桌面安装版「暮冬念春」2.0.3（`gui/launch.py` 起的服务） | **必须要** `X-Handshake-Token` | 对 `http://127.0.0.1:8000/api/overview` 等端点的无令牌请求，全部返回 `403 {"message":"握手失败：非法客户端"}`；令牌由 `gui/launch.py` 生成、打印在 stdout，Electron 主进程用正则 `\[GUI\] 握手令牌:` 解析（`desktop/main.js`） |

对调用方的实际含义：

- **自己起后端（推荐，照 §1 做）**：不涉及握手，只管 `NOVEL_LAB_TOKEN` 那一层。
- **想连用户已经开着的桌面版**：拿不到令牌——它只在 Electron 主进程 stdout 里，图形界面下用户看不到。
  别去猜或爆破；改为自己起一个实例，并用 `XUAN_DATA_DIR` 指向独立目录，免得和运行中的实例抢同一份数据。
- 若确实持有令牌（例如用户从控制台贴给你）：请求头 `X-Handshake-Token: <token>`；
  SSE 端点 `/api/events` 发不了自定义头，等效写法是查询参数 `?handshake_token=<token>`。
- 静态文件（`/`、前端资源）**豁免**握手，只有 `/api` 与 `/api/*` 受管控。

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

### 4.6 质检（单章 / 全书 / QC 综合）

三个 POST + 两个 GET。**`target` 支持 `novel/` 与 `corpus/` 之外的任意本机路径，
单文件和整个目录都可以**（2026-10-08 起；此前外部目录会被一句"请先放入 novel/"挡掉）。
目录按章节加载器的规则采集 `*.txt`，跳过 `备份 / _备份 / backup / .git / build / dist`
这些子目录，非 `.txt` 一律不进质检。上限：单章 50MB、单目录 2000 个 `.txt` / 累计 200MB；
超限或目录里没有 `.txt` 时返回 400 并说明原因（不会留下半份副本）。

```bash
# 单章检查（同步、纯算法、不耗 LLM）：body 支持 target|text、voice、genre_pack
curl -s -X POST "$B/api/quality/check" -H 'Content-Type: application/json' \
  -d '{"target":"C:/书稿/我的书/第001章.txt"}'
# → data.quality = {score, max_score, verdict, details[逐维打分明细]}
#   实测：660 字单章 → score 46.0 / verdict FAIL（字数严重不足、对话占比 0…）

# 全书质检（同步）：body 支持 target|text、voice；target 可给目录
curl -s -X POST "$B/api/quality/book" -H 'Content-Type: application/json' \
  -d '{"target":"C:/书稿/我的书"}'
# 实测（2 章的外部目录）→ data = {"total_chapters":2,"total_issues":3,
#   "severity":{"high":2,"medium":1},"types":{"intra_chapter_repeat":2,
#   "excessive_environment":1},"verdict":"WARN","issues":[…]}

# QC 综合（异步长任务，四层十二维）：body 另有 genre_pack/asset/book/novel_dir/llm_hook
curl -s -X POST "$B/api/quality/qc" -H 'Content-Type: application/json' \
  -d '{"target":"C:/书稿/我的书"}'
# → {"task_id":"q-eaef25e5c090","status":"running","target":"…"}
curl -s "$B/api/quality/tasks/q-eaef25e5c090"
# 实测终态 → {"status":"done","verdict":"WARN","total_score":82.1,
#             "layers":[{"layer":"L1","label":"剧情层","score":66.7,…}],
#             "report_json":"…","report_md":"…"}        # 相对 reports/qc/ 的路径
curl -s "$B/api/quality/reports"                        # 历史质检报告清单
```

- 质检并发上限 2，第三个任务返回 **429**（与生成任务各自的额度独立）。
- `llm_hook=true` 透传给引擎的 `enable_llm_hook`，默认关闭（纯算法层）。
- 外部路径的隔离副本落在 `<用户数据目录>/scratch/qc-external-*/`，任务结束即回收；
  **不要**去那儿读文件，用任务状态里的 `report_json` / `report_md`。

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
