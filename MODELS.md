# 模型配置说明

> **当前状态（2026-09-23 实测，取代下方历史声明）**
>
> 本仓库**已配置 1 个外部模型**，本手册**当前有效**，不是存档：
>
> | 项 | 实测值 |
> |---|---|
> | 模型 id | `workbuddy-deepseek` |
> | 协议 / model_name | `openai` / `DeepSeek-V4-Pro-plus` |
> | 配置来源 | `config/models.json`（入库跟踪） |
> | 密钥 | `config/.secrets.bin`（DPAPI 密文，**不入库**）；`secret_store.load_secrets()` 实测可读到 `workbuddy-deepseek` 条目 |
> | GUI 判定 | `/api/overview` 返回 `model_configured: true` |
> | roles / routes | default / cheap / strong 均指向该模型；pass1-5、writing、consistency_check 均有路由 |
>
> ⚠️ **历史声明（已被上述实测取代，保留以存档决策脉络）**：
> 「2026-09-01 起本手册仅作参考存档：外部模型（mimo/ds）及密钥已按用户指令删除，
> 当前项目**不调用任何外部 LLM API**——拆书分析与写作由内置智能在会话内直接完成。」
> 该声明在 2026-09-01 当时为真；后续重新配置了 `workbuddy-deepseek`，故不再成立。
> 无模型时（密钥缺失 / 额度失败）仍会走会话内接管路径，见 `docs/internal/HANDOFF.md` 第六节。

零依赖，只用 Python 标准库。不需要 `pip install` 任何东西。

```
PY=C:/Users/monesy/.niko/binaries/python/versions/3.13.12/python.exe
cd novel-lab/scripts
```

---

## 三步上手

```bash
# 1. 看有哪些预设
$PY model_config.py presets

# 2. 加一个（以 DeepSeek 为例）
$PY model_config.py add --preset deepseek --id ds --key sk-你的密钥

# 3. 测通不通
$PY model_config.py test ds
```

第 3 步必做。配完不测，出问题时你分不清是密钥错、地址错还是模型名错。

---

## 内置预设

| 预设 id | 服务商 | 上下文 | 定价（元/百万 tok） | 备注 |
|---|---|---|---|---|
| `deepseek` | DeepSeek | 64K | 2 / 8 | 拆书主力候选，中文强且便宜 |
| `siliconflow` | 硅基流动 | 32K | 4.13 | 模型可换，部分小模型免费 |
| `moonshot` | Kimi | 128K | 60 | 超长上下文，贵 |
| `zhipu` | 智谱 GLM | 128K | 50 | 中文稳 |
| `dashscope` | 阿里通义 | 32K | 20 / 60 | 网文语感好 |
| `openai` | OpenAI | 128K | 18 / 72 | |
| `anthropic` | Claude | 200K | 21 / 105 | 定性判断强，适合 Pass3/4 |
| `ollama` | 本地 Ollama | 32K | 0 | 反复调 prompt 用 |
| `lmstudio` | 本地 LM Studio | 32K | 0 | OpenAI 兼容 |
| `vllm` | 本地 vLLM | 32K | 0 | 吞吐高，批量拆书 |
| `custom` | 任意兼容接口 | — | — | 中转站、自建代理 |

价格是写文档时的参考值，会变。真实成本以 `test` 返回的 token 数和你的账单为准。

---

## 三种协议

配置里的 `protocol` 字段决定请求怎么发：

| 值 | 适用 |
|---|---|
| `openai` | **通吃**。DeepSeek、Kimi、智谱、通义、硅基流动、LM Studio、vLLM、绝大多数中转站 |
| `anthropic` | Claude 官方 API |
| `ollama` | 本地 Ollama（`/api/chat` 端点，参数格式不同） |

不确定用哪个就选 `openai`——现在绝大多数服务商都兼容这个格式。

---

## 角色与路由

不是每个任务都值得用最贵的模型。系统用「角色」做中间层：

```
任务  →  角色  →  具体模型
```

三个角色：`cheap`（抽取型任务）、`strong`（判断型任务）、`default`（兜底）。

```bash
$PY model_config.py role cheap local14b    # 便宜活交给本地
$PY model_config.py role strong ds         # 硬活交给云端
$PY model_config.py routes                 # 看当前路由
```

### 默认路由

| 任务 | 角色 | 为什么 |
|---|---|---|
| Pass1 结构层 | cheap | 抽取型——标注章节功能、节拍、钩子类型。小模型够用 |
| Pass2 人物层 | cheap | 抽取型——提口头禅、拒绝方式。结构化任务 |
| Pass3 文风层 | **strong** | 判断型——"这作者写愤怒用体感还是直陈"。小模型会给一堆看着对但没用的空话 |
| Pass4 商业层 | **strong** | 判断型——爽点铺垫多少字才够。需要品味 |
| Pass5 聚合 | strong | 要区分「题材铁律」和「个人风格」，判断失误会让所有作品一个味 |
| 章节生成 | strong | 直接决定成稿质量 |
| 一致性自检 | cheap | 打分比对，机械活 |

分界线是**「抽取」还是「判断」**。抽取是把已有信息结构化，判断需要品味。

改路由：
```bash
$PY model_config.py route pass1_structure strong
```

---

## 密钥安全

**两种存法，优先级：环境变量 > `.secrets.json`**

```bash
# A. 环境变量（推荐）
setx DEEPSEEK_API_KEY "sk-xxx"        # Windows 永久
export DEEPSEEK_API_KEY="sk-xxx"      # Git Bash 当前会话

# B. 本地文件
$PY model_config.py key ds
```

设计上做了三件事：

1. **密钥与配置分离**。`models.json` 可以进 git，`.secrets.json` 不行。
2. **`.gitignore` 已配好**，包括 `corpus/` 和 `*.txt`——范文是别人的版权材料，不能提交。
3. **展示时打码**，`list` 只显示 `sk-tes...cdef`。

验证过：`models.json` 里搜不到密钥字符串。

---

## 常见问题

**HTTP 401** — 密钥错或没生效。`list` 看密钥状态，环境变量方式要重开终端。

**连接失败 WinError 10061** — 本地服务没启动。`ollama serve` 或打开 LM Studio 的 server。

**HTTP 400** — 通常是 `model_name` 写错，或该服务商不支持 `response_format`。把配置里的 `json_mode` 去掉试试。

**本地模型输出乱七八糟** — 检查 `num_ctx`。很多本地模型标称长上下文，实际 8K 之后就丢信息。拆书至少要 32K，配置里默认已拉到 32768。

---

## 在代码里调用

```python
import sys; sys.path.insert(0, "scripts")
from llm_client import chat

# 按任务自动选模型
r = chat(user="...", system="...", task="pass3_style")
print(r["text"], r["cost"], r["elapsed"])

# 或指定模型
r = chat(user="...", model_id="ds")
```

返回带 `cost` 字段（按配置的价格估算，本地模型为 0），拆书时能实时看花了多少钱。

失败自动重试 2 次，指数退避。
