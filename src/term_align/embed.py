# -*- coding: utf-8 -*-
"""用已部署的 Qwen3-Embedding 把术语编码成向量，再按余弦相似度检索。"""
import hashlib
import json
import time
import urllib.error
import urllib.request

import numpy as np

from . import config


class EmbeddingError(RuntimeError):
    pass


class EmbeddingClient:
    """OpenAI 兼容的 /v1/embeddings。词表向量会落到 data/embed_cache。"""

    def __init__(self, endpoint=None, model=None):
        self.endpoint = endpoint or config.EMBED_ENDPOINT
        self.model = model or config.EMBED_MODEL
        self._cache = {}

    def embed(self, texts):
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        missing = []
        order = []
        for text in texts:
            if text not in self._cache:
                missing.append(text)
                order.append(text)
        if missing:
            fetched = self._embed_missing(missing)
            self._cache.update(fetched)
        rows = [self._cache[text] for text in texts]
        return np.stack(rows).astype(np.float32, copy=False)

    def _embed_missing(self, texts):
        found = {}
        batch = config.EMBED_BATCH
        total = len(texts)
        print(f"请求 {self.model} 嵌入 {total} 条", flush=True)
        done = 0
        for start in range(0, total, batch):
            chunk = texts[start:start + batch]
            vectors = _request_embeddings(self.endpoint, self.model, chunk)
            if len(vectors) != len(chunk):
                raise EmbeddingError(
                    f"嵌入条数不符：发送 {len(chunk)}，返回 {len(vectors)}"
                )
            for text, vector in zip(chunk, vectors):
                found[text] = np.asarray(vector, dtype=np.float32)
            done += len(chunk)
            if total > batch:
                print(f"  {done}/{total}", flush=True)
        return found


class EmbeddingIndex:
    def __init__(self, texts, client, cache_name):
        self.client = client
        self.texts = list(texts)
        self.matrix = self._load_or_build(cache_name)

    def _load_or_build(self, cache_name):
        digest = _digest(self.client.model, self.texts)
        path = config.EMBED_CACHE_DIR / f"{cache_name}-{digest}.npy"
        if path.is_file():
            matrix = np.load(path)
            if len(matrix) == len(self.texts):
                print(f"已载入嵌入缓存 {cache_name} {len(self.texts)} 条", flush=True)
                return matrix
        if not self.texts:
            return np.zeros((0, 0), dtype=np.float32)
        matrix = _normalize(self.client.embed(self.texts))
        config.EMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(path, matrix)
        return matrix

    def rank(self, query, allowed=None, top_k=config.SEMANTIC_TOP_K):
        text = (query or "").strip()
        if not text or self.matrix.size == 0:
            return []
        qvec = _normalize(self.client.embed([text]))[0]
        sims = self.matrix @ qvec
        if allowed is not None:
            mask = np.full(sims.shape, -1.0, dtype=np.float32)
            idx = np.fromiter(allowed, dtype=int)
            if len(idx):
                mask[idx] = sims[idx]
            sims = mask
        order = np.argsort(-sims)[:top_k]
        return [(int(i), float(sims[i])) for i in order if sims[i] > 0]


def _normalize(matrix):
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _digest(model, texts):
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(b"\0")
    for text in texts:
        hasher.update(text.encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()[:20]


def _request_embeddings(endpoint, model, texts):
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=config.EMBED_TIMEOUT) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
            rows = obj.get("data")
            if not isinstance(rows, list):
                raise EmbeddingError(f"嵌入响应缺少 data：{list(obj)[:6]}")
            rows = sorted(rows, key=lambda item: item.get("index", 0))
            return [item["embedding"] for item in rows]
        except EmbeddingError:
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            last_err = exc
            time.sleep(1.0 * (attempt + 1))
    raise EmbeddingError(f"嵌入请求失败（{endpoint}）：{last_err}")
