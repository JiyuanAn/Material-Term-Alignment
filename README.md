# Material Term Alignment

把材料属性名、材料对象名分别对齐到规范术语。

词表都在本项目 `data/` 下：

- `data/entity_term/matched_terms.csv`：对象术语
- `data/property_term/extracted_terms_trimmed.csv`：属性术语
- `data/property_aliases.csv`：属性缩写别名

可用环境变量 `ENTITY_TERM_CSV`、`PROPERTY_TERM_CSV`、`PROPERTY_ALIAS_CSV` 改路径。

## 判定

1. 名称先规范化，属性名里的单位（如 `烧结温度(℃)`）会拆出来。
2. 中文名、英文名或别名精确命中则直接接受，`match_type` 为 `exact`。
3. 精确层落空后，默认用 Qwen3-Embedding-8B 把名称编码成向量，在对应词表里按余弦相似度取前几名。第一名分数够高，且与第二名拉开差距，才接受；分差过小为 `borderline`，并带回候选。`method` 设为 `ngram` 时，这一步改用字符 n-gram。
4. 没有够格候选则 `reject`。
5. 属性查询若带单位，量纲不符的候选会被去掉。
6. 化学式解析为成分并写成按元素字母排序的规范式；牌号保持原字符串。二者都是 `instance_only`。名称里如果明确含有词表中的类名（如 `304不锈钢`），额外给出 `parent_class`。

## 启动

```bash
cd src
python -m term_align.server
```

默认地址 `http://127.0.0.1:8030`。依赖见 `requirements.txt`（numpy、scikit-learn）。

嵌入检索默认请求 `http://compute3:8111/v1/embeddings`，模型名 `Qwen3-Embedding-8B`。可用环境变量 `EMBED_ENDPOINT`、`EMBED_MODEL` 修改，`ALIGN_METHOD=ngram` 则全程使用字符 n-gram。词表向量缓存在 `data/embed_cache/`。

## 接口

请求体为 JSON，`Content-Type: application/json`。成功时 HTTP 200，形如 `{"ok": true, "result": {...}}`。失败时 `{"ok": false, "error": "..."}`：

| 状态码 | 条件 |
| --- | --- |
| 400 | 请求体不是 JSON 对象；`name` 为空；`method` 不是 `embedding` 或 `ngram`；属性接口的 `unit` 不是字符串，或 `context_fields` 不是字符串 / 字符串数组 |
| 404 | 路径不是下面三个 |
| 503 | 嵌入服务不可用 |

`method` 可省略，省略时用环境变量 `ALIGN_METHOD`（默认 `embedding`）。对象接口没有 `unit`、`context_fields`。

### `GET /health`

```json
{
  "ok": true,
  "method": "embedding",
  "embed_model": "Qwen3-Embedding-8B",
  "n_properties": 200,
  "n_entities": 6000
}
```

`n_properties`、`n_entities` 为已装载词条数。

### `POST /api/align/property`

```json
{"name": "烧结温度(℃)", "unit": null, "context_fields": ["保温时间"], "method": "embedding"}
```

`name` 必填。单位可以写在名称里，也可以用 `unit` 单独给；两者都有时以 `unit` 为准。`context_fields` 只在 `borderline` 时调整候选次序。

`result` 字段：

| 字段 | 含义 |
| --- | --- |
| `query` | 原始名称 |
| `method` | `embedding` 或 `ngram` |
| `normalized_name` | 去掉单位后的名称 |
| `unit` / `dimension` | 解析出的单位及其量纲，如 `℃` / `temperature`；没有则为 `null` |
| `decision` | `accept`、`borderline`、`reject` |
| `match_type` | 精确命中为 `exact`；嵌入检索为 `embedding`；`method=ngram` 时为 `semantic` |
| `reason` | 拒绝原因；接受时为 `null` |
| `canonical_name` / `canonical_name_en` | 命中的规范中文名、英文名；拒绝时为 `null` |
| `role` | 词表角色，如 `工艺`、`结果` |
| `score` / `margin` | 第一名分数，以及与第二名的分差；精确命中时 `score` 为 `1.0`，`margin` 为 `null` |
| `candidates` | `{name_cn, name_en, score, role, dimension}`，按分数降序 |

样例（与 `tests/test_align.py` 一致）：

| 请求 | 结果 |
| --- | --- |
| `{"name": "烧结温度"}` | `accept`，`match_type=exact`，`canonical_name=烧结温度`，`role=工艺` |
| `{"name": "烧结温度(℃)"}` | `accept`，`unit=℃`，`dimension=temperature` |
| `{"name": "密度", "unit": "℃"}` | `reject`，`reason` 含「量纲」（名称精确命中，但单位量纲不符） |
| `{"name": "HRC"}` | `accept`，`canonical_name=硬度`，`role=结果` |
| `{"name": "屈服应力"}` | `method=embedding`，`match_type=embedding`，`accept`，`canonical_name=屈服强度` |
| `{"name": "sintering temp"}` | `accept`，`canonical_name=烧结温度` |
| `{"name": "温度", "method": "ngram"}` | `accept` 或 `borderline`，`candidates[0].name_cn` 含「温度」 |
| `{"name": "zzzz-not-a-property"}` | `reject`；默认方法下 `match_type=embedding` |
| `{"name": "屈服强度"}` | `ok=true`，`result.canonical_name=屈服强度` |

`borderline` 仍带回 `canonical_name` 和 `candidates`，调用方自行决定是否采用。

### `POST /api/align/object`

```json
{"name": "Fe2O3", "method": "embedding"}
```

`result` 在属性字段之外使用这些字段：`canonical_name_en`、`score`、`margin`、`candidates` 含义相同。`candidates` 每项为 `{name_cn, name_en, uri, score}`。

| 字段 | 含义 |
| --- | --- |
| `kind` | `class`（词表类名）、`formula`（化学式）、`grade`（牌号） |
| `decision` | 类名为 `accept` / `borderline` / `reject`；化学式和牌号固定为 `instance_only` |
| `match_type` | 类名同属性接口；化学式和牌号为 `instance` |
| `uri` | 词表 URI；实例或拒绝时为 `null` |
| `instance_id` | 化学式为规范式，牌号为原始字符串；类名为 `null` |
| `canonical_formula` | 元素按字母排序的规范式；非化学式为 `null` |
| `composition` | `{元素: 计数}`，整数计数写成整数；非化学式为 `null` |
| `parent_class` | 名称里能认出的词表类，形如 `{name_cn, name_en, uri}`；没有则为 `null` |

化学式和牌号不进模糊检索，`score`、`margin`、`candidates` 为空，`reason` 说明它们只作为实例标识。名称含汉字时不当作化学式（如 `304不锈钢` 是牌号）。

样例：

| 请求 | 结果 |
| --- | --- |
| `{"name": "不锈钢"}` | `kind=class`，`accept`，`match_type=exact`，`uri` 含 `stainless_steel` |
| `{"name": "双相钢"}` | `accept`，`canonical_name=双相钢` |
| `{"name": "不锈钢材料"}` | `accept`，`match_type=embedding`，`canonical_name=不锈钢` |
| `{"name": "Fe2O3"}` | `kind=formula`，`instance_only`，`canonical_formula=Fe2O3`，`composition={"Fe": 2, "O": 3}`，`parent_class` 与 `uri` 为 `null` |
| `{"name": "Ti-6Al-4V"}` | `kind=formula`，`canonical_formula=Al6TiV4` |
| `{"name": "Q235"}` | `kind=grade`，`instance_only`，`instance_id=Q235`，`parent_class` 为 `null` |
| `{"name": "304不锈钢"}` | `kind=grade`，`instance_only`，`parent_class.name_cn=不锈钢` |
| `{"name": "not-a-material-zzzz"}` | `kind=class`，`reject` |

### Python

与 HTTP 同一套函数，参数对应请求字段，直接返回 `result` 对象（没有 `ok` 包装）。非法参数抛 `ValueError`。

```python
import sys
sys.path.insert(0, "src")
from term_align import align_property, align_object

align_property("HRC")
align_property("密度", unit="℃")
align_property("温度", method="ngram")
align_object("304不锈钢")
align_object("不锈钢材料")
```
