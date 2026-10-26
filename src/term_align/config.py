# -*- coding: utf-8 -*-
"""路径与判定阈值。词表默认读本项目 data/，可用环境变量覆盖。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ENTITY_TERM_CSV = Path(os.environ.get(
    "ENTITY_TERM_CSV",
    ROOT / "data" / "entity_term" / "matched_terms.csv",
))
PROPERTY_TERM_CSV = Path(os.environ.get(
    "PROPERTY_TERM_CSV",
    ROOT / "data" / "property_term" / "extracted_terms_trimmed.csv",
))
PROPERTY_ALIAS_CSV = Path(os.environ.get(
    "PROPERTY_ALIAS_CSV",
    ROOT / "data" / "property_aliases.csv",
))

# 精确层命中后不再看下面的阈值。
# ngram：字符 n-gram。embedding：Qwen3-Embedding-8B 余弦相似度。
ALIGN_METHOD = os.environ.get("ALIGN_METHOD", "embedding")

SEMANTIC_ACCEPT = 0.55
SEMANTIC_BORDERLINE = 0.32
SEMANTIC_MARGIN = 0.06
SEMANTIC_TOP_K = 5

# Qwen3-Embedding-8B，vLLM OpenAI 兼容接口。见 LLMs/run/Qwen3-Embedding-8B.sh。
EMBED_ENDPOINT = os.environ.get("EMBED_ENDPOINT", "http://compute3:8111/v1/embeddings")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "Qwen3-Embedding-8B")
EMBED_TIMEOUT = float(os.environ.get("EMBED_TIMEOUT", "180"))
EMBED_BATCH = int(os.environ.get("EMBED_BATCH", "32"))
EMBED_CACHE_DIR = ROOT / "data" / "embed_cache"
# 余弦分数高于字符 n-gram。0.80 且与第二名相差 0.05 才接受；0.735 以上记为边界。
EMBED_PROPERTY_ACCEPT = 0.80
EMBED_PROPERTY_BORDERLINE = 0.735
EMBED_PROPERTY_MARGIN = 0.05
EMBED_OBJECT_ACCEPT = 0.80
EMBED_OBJECT_BORDERLINE = 0.735
EMBED_OBJECT_MARGIN = 0.05

HOST = os.environ.get("ALIGN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ALIGN_PORT", "8030"))

# 元数据词条会变成语义检索的吸附点，不进入属性词表。
PROPERTY_DENYLIST = {
    "数据名称", "数据生成", "数据来源", "名称", "研究人员编号",
    "权利", "材料名称", "CAS编号",
    "数据", "数据_", "原始数据", "数据收集", "数据库",
    "电子邮件地址", "隶属关系", "韩国分类代码", "数据开放访问的禁令期限",
}
