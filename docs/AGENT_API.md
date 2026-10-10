# novel-lab Agent 调用手册

面向外部智能体（Qoder / Cline / Claude / OpenCode / Antigravity 等）直接驱动 novel-lab 桌面后端进行网文创作、拆书、质检与多格式交付。

本文所有端点均经过真实本地测试服务（HTTP 127.0.0.1 动态端口）真机实测验证通过。

---

## 目录
- [1. 启动后端服务](#1-启动后端服务)
- [2. 安全与鉴权体系](#2-安全与鉴权体系)
- [3. 通用约定与错误信封](#3-通用约定与错误信封)
- [4. 核心业务工作流 (RESTful API)](#4-核心业务工作流-restful-api)
  - [4.0 拆书第一步：语料导入](#40-拆书第一步语料导入)
  - [4.1 拆书分析与资产检索](#41-拆书分析与资产检索)
  - [4.2 细纲架构拖拽重排与人物关系卡](#42-细纲架构拖拽重排与人物关系卡)
  - [4.3 智能写作与章节原子入库（幂等防重）](#43-智能写作与章节原子入库幂等防重)
  - [4.4 去 AI 味全维诊断服务 (Deslop)](#44-去-ai-味全维诊断服务-deslop)
  - [4.5 统计与多格式规范导出 (DOCX / MD / TXT)](#45-统计与多格式规范导出-docx--md--txt)
  - [4.6 质量检查与合规体检](#46-质量检查与合规体检)
  - [4.7 平台投稿规则自检](#47-平台投稿规则自检)
  - [4.8 管理员系统、限流与审计日志](#48-管理员系统限流与审计日志)
- [5. 全量 REST API 端点清单（97 端点速查）](#5-全量-rest-api-端点清单97-端点速查)
- [6. Python SDK 客户端封装范例（纯标准库，Agent 即拷即用）](#6-python-sdk-客户端封装范例纯标准库agent-即拷即用)
- [7. Agent 调用注意事项与铁律](#7-agent-调用注意事项与铁律)

---

## 1. 启动后端服务

```bash
cd <novel-lab 根目录>
python -m gui.server --no-browser --port 8000
# 输出：[GUI] novel-lab 书籍分析服务已启动: http://127.0.0.1:8000/
# 端口被占时自动 +1（8000-8099）；单实例锁自动防御重复启动与 Stale 自愈
```

> **Windows 系统提示**：请使用 `python` 而非部分系统下的空壳别名 `python3`。
> 用户数据目录默认 `~/.local/share/暮冬念春`（Windows: `%LOCALAPPDATA%\暮冬念春`），可经 `XUAN_DATA_DIR` 环境变量重定向到沙箱目录。

---

## 2. 安全与鉴权体系

- **单机隔离**：服务严格硬绑定 `127.0.0.1`，无公网暴露。
- **Token 鉴权**：若设置了 `NOVEL_LAB_TOKEN`，请求必须携带请求头 `X-Auth-Token: <token>` 或查询参数 `?auth=<token>`。
- **CSRF 纵深防御**：非 Electron 模式下，仅拦截来自外部域名的浏览器写请求；Agent（curl/urllib/requests 等无非本地 Origin 头的脚本客户端）直接通行。
- **管理后台安全**：
  - 基于 PBKDF2-HMAC-SHA256（200,000 轮）加密密码哈希；
  - 登录会话由随机 32 字节 HttpOnly Cookie（`nl_admin_session`）托管；
  - **登录限流**：同一 IP 连续 5 次失败，触发 429 锁定 5 分钟；
  - **历史会话吊销**：改密成功后自动吊销该用户所有活跃会话，强制重新登录。

---

## 3. 通用约定与错误信封

- 基地址：`http://127.0.0.1:<port>`，下文简写为 `$B`。
- **统一响应信封**：
  ```json
  {
    "code": 0,
    "data": { ... },
    "message": ""
  }
  ```
- **错误码约定**：
  - `0`: 成功；
  - `400`: 参数校验失败（如非法章节号、必填项缺失）；
  - `401`: 未认证或会话已过期；
  - `403`: 权限受限或未完成强制初始改密；
  - `404`: 资源不存在；
  - `409`: 状态冲突（如任务已在运行、单实例冲突）；
  - `429`: 触发并发额度上限或登录限流锁定；
  - `500`: 内部错误。

---

## 4. 核心业务工作流 (RESTful API)

### 4.0 拆书第一步：语料导入

```bash
# 路径式就地引用导入（支持磁盘任意安全常规文本）
curl -s -X POST $B/api/import -H 'Content-Type: application/json' \
  -d '{"path":"D:/写作语料/凡人修仙传.txt","batch_size":2048}'
```
**响应 JSON 示例**：
```json
{
  "code": 0,
  "data": {
    "book_id": "凡人修仙传-b8c2d1ef",
    "title": "凡人修仙传",
    "source_path": "D:\\写作语料\\凡人修仙传.txt",
    "total_chapters": 120,
    "chapters": [
      {
        "index": 1,
        "title": "第一章 山边小村",
        "batch_count": 1,
        "batches": [{ "chapter_index": 1, "batch_index": 0, "status": "pending" }]
      }
    ]
  },
  "message": ""
}
```

### 4.1 拆书分析与资产检索

```bash
# 1. 发起拆书长任务（串行五遍扫描）
curl -s -X POST $B/api/analyze/start -H 'Content-Type: application/json' \
  -d '{"book_id":"凡人修仙传-b8c2d1ef","genre":"xuanhuan"}'

# 2. 查询分析任务状态
curl -s -G "$B/api/status" --data-urlencode "book_id=凡人修仙传-b8c2d1ef"
# 终态时 data.status == "done"

# 3. 获取沉淀的声音卡 Voice Card
curl -s "$B/api/assets?kind=voice&limit=20"
```

### 4.2 细纲架构拖拽重排与人物关系卡

```bash
# 1. 创建写作项目
curl -s -X POST $B/api/writing/projects -H 'Content-Type: application/json' \
  -d '{"name":"凡骨逆天录","genre":"xuanhuan"}'

# 2. 新增大纲节点
curl -s -X POST $B/api/writing/outlines -H 'Content-Type: application/json' \
  -d '{"project":"凡骨逆天录","title":"第1章：杂役少年","summary":"灵根未显，受尽嘲讽","kind":"chapter"}'

# 3. 批量原子重排大纲 (Reorder Outlines)
curl -s -X POST $B/api/writing/outlines/reorder -H 'Content-Type: application/json' \
  -d '{"project":"凡骨逆天录","order_ids":[2, 1, 3]}'

# 4. 创建带阵营与深度设定的人物卡
curl -s -X POST $B/api/writing/characters -H 'Content-Type: application/json' \
  -d '{
    "project": "凡骨逆天录",
    "name": "韩立",
    "role": "主角",
    "description": "相貌平平，心思缜密，坚忍果决",
    "extra": {
      "camp": "散修盟",
      "personality": "稳健低调，杀伐果断",
      "goal": "求得长生与大道"
    }
  }'
```

### 4.3 智能写作与章节原子入库（幂等防重）

```bash
# 章节正文入库（原子落盘 + 记账 + 自动质量与文风一致性打分）
curl -s -X POST $B/api/writing/chapters -H 'Content-Type: application/json' \
  -d '{
    "project": "凡骨逆天录",
    "chapter_no": 1,
    "content": "青牛镇的清晨泛着湿气，少年背着柴篓，目光平静而深沉……",
    "voice": "voice:凡人修仙传-b8c2d1ef-voice-card"
  }'
```
**响应 JSON 示例**：
```json
{
  "code": 0,
  "data": {
    "chapter_path": "arc-1/chapter-001.txt",
    "chapter_no": 1,
    "char_count": 2450,
    "consistency_score": 93.5,
    "quality_score": 91.0,
    "quality_verdict": "PASS",
    "pass_line": 85,
    "overwrote": false
  },
  "message": ""
}
```
> **原子幂等说明**：若重复提交相同章节，响应中 `overwrote: true`，字数统计仅记增量差值，章节计数绝不翻倍，数据严格一致。

### 4.4 去 AI 味全维诊断服务 (Deslop)

系统内置 6 大维度纯算法深度检测，毫秒级响应：

```bash
curl -s -X POST $B/api/writing/deslop -H 'Content-Type: application/json' \
  -d '{
    "text": "在这浩瀚无垠的苍穹之下，林枫心中涌起一股滔天巨浪。他非常愤怒，狂风让大地变色。"
  }'
```
**响应 JSON Schema 结构**：
```json
{
  "code": 0,
  "data": {
    "ai_score": 100.0,
    "verdict": "SEVERE",
    "verdict_cn": "重度 AI 味（需深度重塑润色）",
    "stats": {
      "word_count": 42,
      "sentence_count": 3,
      "issues_count": 3,
      "rang_density": 23.8
    },
    "issues": [
      {
        "type": "hollow_rhetoric",
        "label": "假大空玄虚修辞",
        "snippet": "浩瀚无垠",
        "weight": 12,
        "index": 2,
        "suggestion": "替换为具象体感、道具细节或可度量的环境感知。"
      },
      {
        "type": "direct_emotion",
        "label": "直陈式情绪词",
        "snippet": "非常愤怒",
        "weight": 8,
        "index": 24,
        "suggestion": "用生理反应（手抖、后槽牙咬紧、发冷）或即时动作演出情绪。"
      },
      {
        "type": "rang_overuse",
        "label": "「让」字密度超标",
        "snippet": "全篇共出现 1 个「让」字（千字密度 23.8）",
        "weight": 15,
        "index": 0,
        "suggestion": "过度使用'让…产生…'被动句型是翻译腔与 AI 味的重灾区。将其重构为主谓主动句。"
      }
    ],
    "suggestions": [
      "减少概念性宏大空洞叙述，增加地气、环境粗糙度与道具细节描写。",
      "秉持'Show, don't tell'原则，用呼吸急促、眼神闪烁等具体动作代替直白情绪声明。"
    ]
  },
  "message": ""
}
```

### 4.5 统计与多格式规范导出 (DOCX / MD / TXT)

```bash
# 1. 导出出版级 Word (.docx) - 包含合法 OpenXML 结构、扉页、大纲与格式排版
curl -s -G "$B/api/writing/export" \
  --data-urlencode "project=凡骨逆天录" \
  --data-urlencode "format=docx"

# 响应含 content_base64，解码后即可还原为合法的 .docx 二进制包：
# {"code":0,"data":{"filename":"凡骨逆天录-全书导出-2026-10-10.docx","content_base64":"UEsDBBQAAAAIA...","format":"docx","chapters":12,"words":32400}}

# 2. 导出 Markdown (.md) - 带规范层级与章节元数据
curl -s -G "$B/api/writing/export" \
  --data-urlencode "project=凡骨逆天录" \
  --data-urlencode "format=md"

# 3. 导出纯文本 (.txt)
curl -s -G "$B/api/writing/export" \
  --data-urlencode "project=凡骨逆天录" \
  --data-urlencode "format=txt"
```

### 4.6 质量检查与合规体检

```bash
# 单章快速质检（纯算法 12 维）
curl -s -X POST "$B/api/quality/check" -H 'Content-Type: application/json' \
  -d '{"text":"章节全文……"}'

# 全书四层十二维深度 QC 质检（长任务）
curl -s -X POST "$B/api/quality/qc" -H 'Content-Type: application/json' \
  -d '{"target":"D:/写作项目/凡骨逆天录"}'
# → {"task_id":"q-xxxx","status":"running"}
curl -s "$B/api/quality/tasks/q-xxxx"
```

### 4.7 平台投稿规则自检

```bash
# 查询支持的平台规则
curl -s "$B/api/platform/list"

# 起点 / 番茄单章过审自检
curl -s -X POST "$B/api/platform/check" -H 'Content-Type: application/json' \
  -d '{"platform_id":"qidian","chapter_title":"第1章 惊变","chapter_text":"正文……"}'
```

### 4.8 管理员系统、限流与审计日志

```bash
# 1. 登录认证 (生成 HttpOnly Cookie 会话)
curl -s -i -X POST "$B/api/admin/login" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<初始密码或已设密码>"}'

# 2. 修改管理员密码 (改密后历史会话自动全部吊销)
curl -s -X POST "$B/api/admin/change-password" -b "nl_admin_session=<sid>" \
  -H 'Content-Type: application/json' \
  -d '{"oldPassword":"<旧密码>","newPassword":"<新密码至少8位>"}'

# 3. 查询安全审计日志
curl -s "$B/api/admin/audit" -b "nl_admin_session=<sid>"
```

---

## 5. 全量 REST API 端点清单（97 端点速查）

| 分类 | 方法 | 路径 | 描述 |
|---|---|---|---|
| **语料与导入** | `POST` | `/api/import` | 本地路径式分章分批导入 |
| | `GET` | `/api/samples` | 获取系统内置示例语料列表 |
| | `POST` | `/api/samples/import` | 一键导入内置样例语料 |
| | `GET` | `/api/book/{book_id}` | 获取书籍元数据与批次摘要 |
| | `GET` | `/api/book/{book_id}/chapter/{idx}` | 获取单章正文与批次元信息 |
| | `POST` | `/api/book/{book_id}/chapter/{idx}/batch` | 重新切分单章批次 |
| **拆书与分析** | `POST` | `/api/analyze/start` | 启动五遍扫描拆书长任务 |
| | `GET` | `/api/genres` | 获取已知题材注册表 |
| | `POST` | `/api/analyze/pause` | 暂停分析任务 |
| | `POST` | `/api/analyze/resume` | 恢复分析任务（支持断点续传） |
| | `POST` | `/api/analyze/retry-failed` | 重试失败批次 |
| | `GET` | `/api/status` | 查询拆书分析进度与状态 |
| | `GET` | `/api/overview` | 拆书总览数据 |
| | `GET` | `/api/tropes` | 桥段库查询 |
| | `GET` | `/api/book/{book_id}/results` | 拆书明细结果 |
| | `GET` | `/api/book/{book_id}/scores` | 拆书打分分布 |
| | `POST` | `/api/analyze/full` | 全量深度分析流程 |
| **资产中心** | `GET` | `/api/asset` | 单个资产卡片查询 |
| | `GET` | `/api/assets` | 资产库分页与分类列表 |
| | `GET` | `/api/assets/{kind}/{id}` | 资产详情获取 |
| | `PUT` | `/api/assets/{kind}/{id}` | 资产更新修改 |
| | `DELETE` | `/api/assets/{kind}/{id}` | 资产删除 |
| | `POST` | `/api/assets` | 新增自定义资产 |
| | `GET` | `/api/reports` | 拆书报告列表 |
| | `GET` | `/api/reports/{id}` | 拆书报告详情 |
| **创作工作台** | `GET` | `/api/writing/projects` | 写作项目列表 |
| | `POST` | `/api/writing/projects` | 新建写作项目 |
| | `POST` | `/api/writing/inject` | 资产注入生成 System Prompt |
| | `POST` | `/api/writing/generate` | 章节智能起草（支持无模型降级） |
| | `GET` | `/api/writing/tasks/{task_id}` | 查询写作生成任务状态 |
| | `POST` | `/api/writing/chapters` | 章节正文入库（原子落盘与记账） |
| | `POST` | `/api/writing/score` | 章节双维度打分（一致性+质量） |
| | `POST` | `/api/writing/assemble` | 题材资产聚合装配 |
| | `GET` | `/api/writing/assemble-candidates` | 题材装配候选书籍 |
| | `GET` | `/api/writing/outlines` | 大纲树列表 |
| | `POST` | `/api/writing/outlines` | 新增细纲节点 |
| | `POST` | `/api/writing/outlines/reorder` | **细纲批量原子重排序** |
| | `PUT` | `/api/writing/outlines/{oid}` | 更新单条细纲 |
| | `DELETE` | `/api/writing/outlines/{oid}` | 删除细纲节点 |
| | `GET` | `/api/writing/characters` | 人物关系卡片列表 |
| | `POST` | `/api/writing/characters` | 新增人物卡（支持阵营与 extra） |
| | `PUT` | `/api/writing/characters/{cid}` | 更新人物卡 |
| | `DELETE` | `/api/writing/characters/{cid}` | 删除人物卡 |
| | `GET` | `/api/writing/notes` | 灵感便签列表 |
| | `POST` | `/api/writing/notes` | 新建便签 |
| | `PUT` | `/api/writing/notes/{nid}` | 更新便签 |
| | `DELETE` | `/api/writing/notes/{nid}` | 删除便签 |
| | `GET` | `/api/writing/stats` | 码字统计与创作大盘指标 |
| | `GET` | `/api/writing/export` | **全格式导出 (DOCX / MD / TXT)** |
| | `POST` | `/api/writing/deslop` | **去 AI 味全维度诊断与润色评估** |
| **质检引擎** | `POST` | `/api/quality/check` | 单章质量快速检查 |
| | `POST` | `/api/quality/book` | 全书目录质检 |
| | `POST` | `/api/quality/qc` | 四层十二维 QC 综合长任务 |
| | `GET` | `/api/quality/tasks/{task_id}` | 查询 QC 任务详情与报告路径 |
| | `GET` | `/api/quality/reports` | 历史 QC 质检报告清单 |
| **文风与高级** | `POST` | `/api/style/analyze` | 文风样本特征分析 |
| | `POST` | `/api/style/save` | 保存文风模型 |
| | `GET` | `/api/style/list` | 已存文风列表 |
| | `GET` | `/api/style/{name}` | 文风详情 |
| | `DELETE` | `/api/style/{name}` | 删除文风 |
| | `POST` | `/api/style/apply` | 文风应用与迁移 |
| | `GET` | `/api/advanced/distill/{genre}` | 题材高级蒸馏状态 |
| | `POST` | `/api/advanced/distill/{genre}` | 执行题材规则蒸馏 |
| | `GET` | `/api/advanced/aggregate/{genre}`| 题材聚合特征 |
| | `GET` | `/api/advanced/batch-status` | 高级批处理状态 |
| **平台投稿** | `GET` | `/api/platform/list` | 支持的网文平台规范列表 |
| | `GET` | `/api/platform/{pid}` | 单平台详细规则参数 |
| | `POST` | `/api/platform/check` | 单章投前合规检查 |
| | `POST` | `/api/platform/format` | 平台规范格式化排版 |
| | `POST` | `/api/platform/export` | 投前整书合规检查与打包导出 |
| **模型与系统** | `GET` | `/api/system/status` | 系统健康、版本与存储统计 |
| | `POST` | `/api/system/compliance` | 运行合规性审计检查 |
| | `GET` | `/api/system/models` | 系统模型概况 |
| | `GET` | `/api/system/settings` | 系统设置 |
| | `PUT` | `/api/system/settings` | 更新系统设置 |
| | `POST` | `/api/system/settings/reset`| 重置设置 |
| | `GET` | `/api/config/models` | 外部 LLM 模型配置列表 |
| | `GET` | `/api/models` | 模型列表 |
| | `POST` | `/api/models` | 注册外部模型配置 |
| | `GET` | `/api/models/presets` | 预置模型模板 |
| | `GET` | `/api/models/{id}` | 模型配置详情 |
| | `PUT` | `/api/models/{id}` | 更新模型配置 |
| | `DELETE` | `/api/models/{id}` | 删除模型配置 |
| | `POST` | `/api/models/{id}/key` | 设置模型 API 密钥 |
| | `POST` | `/api/models/{id}/test` | 测试外部模型连通性 |
| **管理后台** | `POST` | `/api/admin/login` | 管理员认证登录（设置 Cookie） |
| | `POST` | `/api/admin/logout` | 管理员安全登出 |
| | `GET` | `/api/admin/me` | 当前会话状态与强制改密标记 |
| | `GET` | `/api/admin/dashboard` | 管理员全景大盘统计 |
| | `GET` | `/api/admin/books` | 管理员书库查看 |
| | `DELETE`| `/api/admin/books/{book_id}`| 删除书库指定书籍及语料 |
| | `GET` | `/api/admin/assets` | 管理员资产视图 |
| | `DELETE`| `/api/admin/assets/{kind}/{id}`| 管理员物理删除资产 |
| | `GET` | `/api/admin/reports` | 管理员报告清单 |
| | `GET` | `/api/admin/audit` | 管理员安全审计日志清单 |
| | `POST` | `/api/admin/change-password` | **修改密码（吊销旧会话）** |
| | `GET` | `/api/admin/sessions` | 查看活跃管理会话 |
| | `DELETE`| `/api/admin/sessions/{sid}` | 强踢指定管理会话 |

---

## 6. Python SDK 客户端封装范例（纯标准库，Agent 即拷即用）

为方便外部智能体无依赖集成，以下提供 100% 纯 Python 标准库的 SDK 实现：

```python
"""novel_lab_sdk.py - 面向 Agent 的 novel-lab 纯标准库客户端。"""
from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from typing import Any


class NovelLabClient:
    """包装 novel-lab 本地 RESTful API 的高阶客户端。"""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, data: dict[str, Any] | None = None,
                 params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if params:
            url += f"?{urllib.parse.urlencode({k: str(v) for k, v in params.items()})}"

        headers = {"User-Agent": "NovelLab-Agent-SDK/2.0.3"}
        if self.token:
            headers["X-Auth-Token"] = self.token

        body_bytes = None
        if data is not None:
            body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            if res_json.get("code") != 0:
                raise RuntimeError(f"API Error [{res_json.get('code')}]: {res_json.get('message')}")
            return res_json.get("data")

    # --- 拆书与资产 ---
    def import_book(self, path: str, batch_size: int = 2048) -> dict[str, Any]:
        return self._request("POST", "/api/import", {"path": path, "batch_size": batch_size})

    def list_assets(self, kind: str = "voice", limit: int = 50) -> list[dict[str, Any]]:
        data = self._request("GET", "/api/assets", params={"kind": kind, "limit": limit})
        return data.get("items", [])

    # --- 创作与大纲 ---
    def create_project(self, name: str, genre: str = "xuanhuan") -> dict[str, Any]:
        return self._request("POST", "/api/writing/projects", {"name": name, "genre": genre})

    def reorder_outlines(self, project: str, order_ids: list[int]) -> list[dict[str, Any]]:
        return self._request("POST", "/api/writing/outlines/reorder",
                             {"project": project, "order_ids": order_ids})

    def create_character(self, project: str, name: str, role: str,
                         camp: str, personality: str) -> dict[str, Any]:
        return self._request("POST", "/api/writing/characters", {
            "project": project, "name": name, "role": role,
            "extra": {"camp": camp, "personality": personality}
        })

    def save_chapter(self, project: str, chapter_no: int, content: str,
                     voice: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/api/writing/chapters", {
            "project": project, "chapter_no": chapter_no, "content": content, "voice": voice
        })

    # --- 去 AI 味诊断 ---
    def diagnose_deslop(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/api/writing/deslop", {"text": text})

    # --- 规范导出 ---
    def export_docx_to_file(self, project: str, output_path: str) -> int:
        data = self._request("GET", "/api/writing/export", params={"project": project, "format": "docx"})
        docx_bytes = base64.b64decode(data["content_base64"])
        with open(output_path, "wb") as f:
            f.write(docx_bytes)
        return len(docx_bytes)


# --- 使用示例 ---
if __name__ == "__main__":
    client = NovelLabClient()
    # 1. 检测文本 AI 味
    diag = client.diagnose_deslop("在这浩瀚无垠的星空下，少年紧紧握拳，心中泛起滔天巨浪。他非常愤怒。")
    print(f"AI味得分: {diag['ai_score']} | 诊断: {diag['verdict_cn']}")
    for issue in diag["issues"]:
        print(f" - [{issue['label']}] 命中: {issue['snippet']} -> 优化建议: {issue['suggestion']}")
```

---

## 7. Agent 调用注意事项与铁律

1. **写操作幂等保障**：
   `POST /api/writing/chapters` 具备服务端原子锁保护。对同一章节号重复提交时，底层只更新最新内容与正文字数增量差额，章节数与历史总字数不会发生翻倍失真。
2. **非 ASCII 参数编码规范**：
   GET 请求中若查询参数含中文（如 `project=我的小说`），请务必使用标准百分号编码（`urllib.parse.quote` 或 curl `--data-urlencode`），避免 URL 解码乱码。
3. **资产引用格式规范**：
   所有资产参数均需遵循 `<kind>:<asset_id>` 规范（例如 `voice:campus-voice-card`）。禁止将 `distilled` 或 `prose_card` 强行填入 `voice` 字段，服务端将执行硬校验拦截（返回 400）。
4. **并发配额约束**：
   后台耗算力的生成与深度 QC 质检任务各设有并发上限（默认为 2），超出时将返回 HTTP 429。调用方应在遇到 429 时实施指数退避重试（Backoff）。
