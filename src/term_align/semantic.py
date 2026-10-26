# -*- coding: utf-8 -*-
"""词表上的字符 n-gram 向量检索。只在精确层落空后调用。"""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import config


class SemanticIndex:
    def __init__(self, texts):
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3), min_df=1)
        self.matrix = self.vectorizer.fit_transform(texts if texts else [""])

    def rank(self, query, allowed=None, top_k=config.SEMANTIC_TOP_K):
        """返回 [(row_index, score), ...]，分数降序。allowed 为可保留的行号集合。"""
        text = (query or "").strip().lower()
        if not text or self.matrix is None:
            return []
        sims = cosine_similarity(self.vectorizer.transform([text]), self.matrix)[0]
        if allowed is not None:
            mask = np.full(sims.shape, -1.0)
            idx = np.fromiter(allowed, dtype=int)
            if len(idx):
                mask[idx] = sims[idx]
            sims = mask
        order = np.argsort(-sims)[:top_k]
        return [(int(i), float(sims[i])) for i in order if sims[i] > 0]


def decide(ranked):
    """绝对分数加上与第二名的分差。分差过小保持边界，不自动接受。"""
    if not ranked:
        return "reject", 0.0, None
    top_score = ranked[0][1]
    second = ranked[1][1] if len(ranked) > 1 else None
    margin = None if second is None else top_score - second
    if top_score >= config.SEMANTIC_ACCEPT and (margin is None or margin >= config.SEMANTIC_MARGIN):
        return "accept", top_score, margin
    if top_score >= config.SEMANTIC_BORDERLINE:
        return "borderline", top_score, margin
    return "reject", top_score, margin
