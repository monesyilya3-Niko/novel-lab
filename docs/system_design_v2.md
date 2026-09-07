# novel-lab 蒸馏层二期 · 增量系统设计 + 任务分解

> 架构师：高见远。范围：任务 A（技法归一化）+ 任务 B（语义检索/RAG 桥接）。
> 硬约束（铁律）：零第三方依赖；原始资产永不改写；稳定 id；注入只走 `inject.py:build_prompt()`。

---

## 1. 实现方案

### 1.1 任务 A：技法归一化（修改 `distill_core.py`）

**问题根因**：`_aggregate_craft()` 第 669 行起对 `technique.name` 只做**精确匹配**计数，
导致「三段式钩子」与「三段式 钩子」、「反转式悬念」与「反转悬念」被当作不同技法，
产生碎片化 personal 规则（Bug4）。

**方案**：新增一层「归一化聚类」前置步骤，把同一维度内相似技法名聚成簇，再以簇为单位计数。
采用**纯字符串近似 + 双条件降误合并**，不引入任何 embedding。

**归一化算法流程（纯函数，可独立单测）**：

```
normalize_technique(name) -> str
    1. 小写化 lower()
    2. 去空格、标点：re.sub(r"[\s\p{P}]+", "", ...)（仅保留中日韩字符+字母数字）
    3. 去停用词：按停用词表过滤（"的""与""和""及""或""之"等）
    4. 返回规范化字符串（可为空串，空串不参与合并）

char_ngram_similarity(a, b, n=2) -> float
    对规范化后字符串生成字符 n-gram 多重集，
    返回 |A∩B| / |A∪B|（即字符级 Jaccard 相似度）

cluster_techniques(techniques) -> List[TechniqueCluster]
    对每个 technique（含 name + skeleton），
    与已有簇的代表（簇内频次最高者）比较：
        若 name_jaccard >= 0.5 且 skeleton_jaccard >= 0.3 → 合并进该簇
        否则新建簇
    单簇判定（单元素、无近邻）不合并、不丢数据，原样保留
```

**双条件判据（降误合并）**：技法名规范化后 Jaccard ≥ 0.5 **且** skeleton Jaccard ≥ 0.3 才合并。
只满足其一不合并。阈值与停用词表统一收敛在 `distill_core.py` 顶部常量区。

**同义词表兜底**：读取 `novel-lab/synonyms.json`（可编辑配置，非资产文件），缺失/损坏回退空表。
同义词表把多个别名映射到规范名，命中即视为同一簇（**不经过相似度计算**，优先于相似度判据）。
格式见 §3.3。

**可追溯**：归一化簇保留 `sources`（原文 name + book）与 `representative`（簇代表名），
不丢弃任何来源。归一化统计（簇数、合并对数）可选写入 `distilled.meta`（P2）。

### 1.2 任务 B：语义检索/RAG 桥接（新增 `scripts/retrieve.py`）

**方案**：新增零依赖词汇级检索模块，用「倒排索引 + 词项重叠打分」近似语义检索。

**倒排索引结构**：

```
Index:
    _inverted: dict[term, list[doc_id]]          # 词项 -> 文档列表
    _doc_freq: dict[term, int]                   # 文档频率 df（算 idf）
    _docs: list[DocEntry]                        # 文档元数据
    _idf_cache: dict[term, float]

DocEntry:
    asset_id: str        # 稳定 id，如 "<genre>-<dimension>-distilled"
    dimension: str
    asset_dict: dict     # 原 distilled dict（取 snippet 用）
    terms: Counter       # 该文档词项频次 tf
    snippet: str         # 预生成的约 200 字符摘要
```

**索引构建**：四类资产（`collect_assets` 的产出）全部进索引；`re` 分词（`[\w\u4e00-\u9fff]+`）
→ 规范化 → `collections.Counter` 记 tf → 写倒排表 + df。

**打分公式**（BM25 简化版，纯标准库可算）：

```
score(q, d) = Σ_{t∈q∩d} idf(t) * tf(t,d) * (k1+1) / (tf(t,d) + k1)
    idf(t) = ln( (N - df(t) + 0.5) / (df(t) + 0.5) + 1 )
    N = 文档总数，k1 = 1.5（常量）
    查询词项重叠度 = |q∩d| / |q|（权重因子，可乘入）
```

**意图映射**：查询分词后若命中「关键词 → 维度/标签」映射表（`retrieve.py` 顶部常量），
提升对应维度文档的召回（加权/额外命中词项）。

**输出**：`list[{asset_id, dimension, score, snippet}]`，按 score 降序、同分按稳定 id 升序；
`top_k=5`，snippet 截断约 200 字符（参数可调）。

### 1.3 注入接入（修改 `inject.py`）

`build_prompt()` 新增可选参数 `context_intent: str`：

```python
def build_prompt(voice, structure, commercial, genre_pack=None,
                 craft_card=None, distilled=None, context_intent=None) -> str:
    ...
    ds = render_distilled(distilled)
    if ds:
        sections.append(ds)
    # 新增：context_intent 非空时，在蒸馏段后追加「针对性注入段」
    if context_intent:
        hits = retrieve_for_intent(context_intent, ...)   # 见 §4
        if hits:
            sections.append(render_retrieval(hits))       # 新增渲染函数
    ...
```

**回归兼容铁律**：`context_intent` 未传（默认 None）时，`build_prompt()` 输出与一期
**字节级一致**，33 用例零改动。

---

## 2. 文件列表

| 文件 | 动作 | 说明 |
|------|------|------|
| `scripts/distill_core.py` | 修改 | 顶部新增归一化阈值/停用词/同义词常量；新增 `_normalize_technique`、`_char_ngram_similarity`、`_load_synonyms`、`_cluster_techniques`；`_aggregate_craft` 改用簇计数 |
| `scripts/retrieve.py` | 新增 | 倒排索引 + 检索 + `retrieve_for_intent()` + `render_retrieval()` + 意图映射常量 |
| `scripts/inject.py` | 修改 | `build_prompt()` 新增 `context_intent` 参数 + 针对性注入段（未传时零改动） |
| `scripts/distill_render.py` | 修改（可选 P2） | 若渲染检索结果段落，也可复用；否则由 retrieve.py 自带 `render_retrieval` |
| `synonyms.json` | 新增 | 人工同义词表（可编辑配置，非资产，缺失回退空表） |
| `tests/test_distill.py` | 修改 | 新增任务 A 归一化 + 任务 B 检索的用例（保留原 33 用例） |

---

## 3. 数据与接口

### 3.1 归一化簇（任务 A）

```python
@dataclass
class TechniqueCluster:
    representative: str              # 簇代表名（频次最高原文名）
    names: List[str]                 # 簇内所有原始 name（去重）
    skeletons: List[str]             # 簇内对应 skeleton（去重）
    sources: List[SourceValue]       # 来源（book + raw name），可追溯
    count: int                       # 出现频次（跨书）
    books: List[str]                 # 贡献该簇的书籍
```

### 3.2 检索结果条目（任务 B）

```python
@dataclass
class HitEntry:
    asset_id: str      # 稳定 id
    dimension: str
    score: float
    snippet: str       # 约 200 字符
```

### 3.3 同义词表 `synonyms.json` 格式

```json
{
  "craft-card": {
    "三段式钩子": ["三段式 钩子", "三段式悬念钩子", "三段式钩子法"],
    "反转式悬念": ["反转悬念", "反转式 悬念"]
  }
}
```
顶层按维度分组；每组 `规范名 -> [别名...]`。文件缺失/JSON 损坏 → 回退空表 `{}`。

### 3.4 关键函数签名

```python
# distill_core.py
def _normalize_technique(name: str) -> str
def _char_ngram_similarity(a: str, b: str, n: int = 2) -> float
def _load_synonyms() -> Dict[str, Dict[str, List[str]]]
def _cluster_techniques(techniques: List[dict]) -> List[TechniqueCluster]

# retrieve.py
def build_index(assets: Dict[str, Dict[str, dict]]) -> Index
def retrieve_for_intent(intent: str, index: Index, top_k: int = 5) -> List[HitEntry]
def render_retrieval(hits: List[HitEntry]) -> str

# inject.py
def build_prompt(voice, structure, commercial, genre_pack=None,
                 craft_card=None, distilled=None, context_intent=None) -> str
```

---

## 4. 程序调用流程

### 4.1 任务 A 归一化流程（文字步骤）

1. `_aggregate_craft()` 收集某维度所有书的 `techniques`（含 name + skeleton）。
2. `_load_synonyms()` 读同义词表；对每个 name 先查同义词 → 命中直接归到规范名簇。
3. 未命中同义词的 name，调 `_normalize_technique()` 规范化。
4. `_cluster_techniques()`：与已有簇代表比较 name Jaccard + skeleton Jaccard，双阈值合并。
5. 以簇为单位统计 count / books，产出一条 `AggregatedRule`（替代原来的逐 name 计数）。
6. 单元素簇 / 无法语义去重者保留各自来源，不强行合并、不丢数据。

### 4.2 任务 B 检索-注入流程（Mermaid 时序图）

见 `docs/sequence-diagram.mermaid`（同目录已单独导出）。

文字版：
1. 外部调用 `build_prompt(..., context_intent="悬疑反转钩子")`。
2. `build_prompt` 先渲染蒸馏段（同现有逻辑），再判 `context_intent` 非空。
3. 调 `retrieve_for_intent(intent, index)`：分词 → 意图映射加权 → 倒排索引打分 → 排序 → 截 top_k。
4. `render_retrieval(hits)` 渲染「针对性注入段」，追加到蒸馏段之后。
5. 未传 `context_intent` 时跳过 2–4，输出与一期字节级一致。

---

## 5. 任务列表（有序，按依赖）

| Task | 名称 | 源文件 | 依赖 | 优先级 | 验收标准 |
|------|------|--------|------|--------|----------|
| T01 | 技法归一化核心（含同义词表） | `distill_core.py`、`synonyms.json` | — | P0 | `_normalize_technique`/`_char_ngram_similarity`/`_cluster_techniques` 可独立单测；双条件合并正确；原 33 用例不回归；新增归一化用例通过 |
| T02 | 检索模块 + 注入接入 | `retrieve.py`、`inject.py` | T01 | P0 | 倒排索引构建/检索打分正确；`build_prompt(context_intent=...)` 追加针对性注入段；未传时字节级一致；top_k/snippet 可调 |
| T03 | 测试补充 + 回归 | `tests/test_distill.py` | T02 | P1 | 新增任务 A/B 用例；全量测试通过（含原 33 用例零改动） |

> 任务控制在 3 个以内，符合「不超过 5 个任务」硬性上限。T01 为数据层基础，T02 为检索+集成，T03 为验证收尾，依赖链最短。

---

## 6. 共享知识（跨文件约定）

- **阈值常量位置**：`distill_core.py` 顶部（与现有 `CONFIDENCE_HARD` 等并列），新增：
  `TECHNIQUE_NAME_JACCARD=0.5`、`TECHNIQUE_SKELETON_JACCARD=0.3`、`NGRAM_N=2`、
  `STOPWORDS=frozenset({...})`。`retrieve.py` 顶部另放 `TOP_K=5`、`SNIPPET_LEN=200`、`BM25_K1=1.5`。
- **同义词表**：`novel-lab/synonyms.json`，缺失/损坏回退空表；同义词优先于相似度判据。
- **打分公式**：BM25 简化（见 §1.2）；查询词项重叠度可作权重乘入。
- **id 约定**：`distilled.meta.id = "<genre>-<dimension>-distilled"`；`rule.id = "<dimension>-<field-slug>-<4位序号>"`；检索返回的 `asset_id` 复用 `meta.id`，保证稳定可追溯。
- **回归兼容**：`build_prompt()` 未传 `context_intent` 时输出与一期字节级一致，33 用例零改动。
- **import 白名单**：新增代码仅用 `argparse/json/re/sys/collections/statistics/pathlib/copy/datetime/uuid/dataclasses/unittest`（测试可加 `importlib.util`）。
- **资产只读**：归一化与检索只读资产，不改写；聚合结果另存 `*-distilled.json`。

---

## 7. 待明确事项

1. **同义词表初始内容**：建议先空表 `{}` 或仅 1–2 个示例条目，由产品经理后续补充；默认回退空表，不影响相似度主路径。
2. **skeleton 缺失时的合并判据**：若某 technique 无 skeleton 字段，建议 name Jaccard ≥ 0.7 才合并（提高单条件阈值）；默认采纳。
3. **意图映射表覆盖范围**：建议首版只挂「钩子/悬念/爽点/铺垫/伏笔」等高频领域词 → 对应维度；默认按此实现，后续可扩展。
4. **归一化统计写入 meta**：P2 可选；默认二期先不写入，避免改动 schema 影响一期兼容，待产品经理确认后再加。
5. **检索结果渲染格式**：建议「### 针对性注入（来自检索）」+ 每条 `- {snippet}`；默认采纳，可后续调。

---

## 8. 实施结果（落地记录，与代码一致）

> 本节为交付后补记，记录最终落地状态，替代 §7 中「同义词表初始内容」等占位假设。

### 8.1 同义词表（synonyms.json 真实数据）

按「同维度内、跨书」原则收敛出 8 个有效近义组（另保留 2 个占位示例组「三段式钩子」「反转式悬念」，对三本书真实技法命中为 0，属预期）。因 `_cluster_techniques` 按 craft 十维各自独立聚类，跨维度技法永不合并，故表内别名必须与规范名同维度才生效。

| 规范名 | 维度 | 命中书 |
|--------|------|--------|
| 利用物品细节埋下关联伏笔 | foreshadowing | chireng+qingning |
| 内心戏与外部反应的错位 | pov_control | qingning+sangshi |
| 以铃声为界硬切冲突 | scene_transition | chireng+sangshi |
| 内心独白与说出口的话错位 | dialogue_craft | qingning+sangshi |
| 以沉默与肢体替代言语回应 | dialogue_craft | qingning+sangshi |
| 触觉外化内心生理反应 | sensory_craft | qingning+sangshi |
| 暗恋的“未言明”悬念驱动 | narrative_engine | qingning+sangshi |
| 暴力场景短句连击加速节奏 | rhythm_control | chireng+qingning+sangshi（3 书，唯一 hard） |

### 8.2 分层口径修正（Bug）

`_aggregate_craft` 原传 `explicit_count=cluster.count`（簇内技法总频次，同书多技法会叠加），与 `_kind_for_count` 的「按贡献书数分层」语义不符，导致 `scene_transition`/`sensory_craft` 被虚标 hard。已改为 `explicit_count=len(cluster.books)`（去重书数），`kind` 与 `books_count` 口径统一。

### 8.3 代表名选取修正

`_most_frequent_name` 在频次并列时原回退 `names[0]`（首次遇到者），使 `sensory_craft` 代表名落为语义偏窄的「嗅觉作为情感记忆的触发器」。新增 `canon_map` 可选参数，并列时优先取同义词表规范名（`canon_map.get(name)==name`），缺省 None 时行为向后兼容。

### 8.4 最终蒸馏统计（campus-redemption craft-card）

`hard_rules=1`（仅 rhythm_control，3 书命中）、`soft_rules=10`、`personal_styles=39`、`total_rules=11`。代表名均取自簇内真实技法名，sources 可完整溯源至三本书 craft_analysis。
