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

`POST /api/align/property`

```json
{"name": "烧结温度(℃)", "unit": null, "context_fields": ["保温时间"], "method": "embedding"}
```

`unit` 可省略。

`POST /api/align/object`

```json
{"name": "Fe2O3"}
```

`GET /health` 返回已装载的词条数。

Python 调用：

```python
import sys
sys.path.insert(0, "src")
from term_align import align_property, align_object

align_property("HRC")
align_object("304不锈钢")
```
