# -*- coding: utf-8 -*-
"""两个对外函数：align_property、align_object。"""
import re
import threading

from . import config
from .embed import EmbeddingClient, EmbeddingIndex
from .formula import composition_payload, format_formula, parse_composition
from .lexicon import Lexicon
from .normalize import clean_display, fold, split_name_and_unit
from .semantic import SemanticIndex, decide
from .units import parse_unit

_service = None


def _term_text(item):
    return f"{item.name_cn} {item.name_en}".strip()


def _resolve_method(method):
    chosen = (method or config.ALIGN_METHOD or "embedding").strip().lower()
    if chosen not in ("ngram", "embedding"):
        raise ValueError("method 必须是 ngram 或 embedding")
    return chosen


class TermService:
    def __init__(self):
        self.lexicon = Lexicon()
        self.lexicon.load()
        self.property_index = SemanticIndex(
            [_term_text(item).lower() for item in self.lexicon.properties]
        )
        self.entity_index = SemanticIndex(
            [_term_text(item).lower() for item in self.lexicon.entities]
        )
        self._embed_client = None
        self._property_embed = None
        self._entity_embed = None
        self._embed_lock = threading.Lock()

    def embed_index(self, kind):
        with self._embed_lock:
            if self._embed_client is None:
                self._embed_client = EmbeddingClient()
            if kind == "property":
                if self._property_embed is None:
                    texts = [_term_text(item) for item in self.lexicon.properties]
                    self._property_embed = EmbeddingIndex(texts, self._embed_client, "property")
                return self._property_embed
            if self._entity_embed is None:
                texts = [_term_text(item) for item in self.lexicon.entities]
                self._entity_embed = EmbeddingIndex(texts, self._embed_client, "entity")
            return self._entity_embed


def get_service():
    global _service
    if _service is None:
        _service = TermService()
    return _service


def align_property(name, unit=None, context_fields=None, method=None):
    """把属性名对齐到 property_term。

    name 必填。unit 可单独给，也可写在名称里，如「烧结温度(℃)」。
    context_fields 只在边界结果里用来调整候选次序，不把拒绝抬成接受。
    method 为 embedding（默认，Qwen3-Embedding-8B）或 ngram。
    """
    service = get_service()
    method = _resolve_method(method)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name 不能为空")
    if unit not in (None, "") and not isinstance(unit, str):
        raise ValueError("unit 必须是字符串")
    if context_fields is None:
        context_fields = []
    elif isinstance(context_fields, str):
        context_fields = [context_fields]
    elif not isinstance(context_fields, list):
        raise ValueError("context_fields 必须是字符串数组")
    parsed_name, embedded_unit = split_name_and_unit(name)
    unit_text = unit if unit not in (None, "") else embedded_unit
    canon_unit, unit_dim = parse_unit(unit_text)
    lexicon = service.lexicon

    exact_id = lexicon.property_exact.get(fold(parsed_name))
    if exact_id is not None:
        item = lexicon.properties[exact_id]
        if unit_dim and item.dimension and item.dimension != unit_dim:
            return _property_payload(
                query=name, normalized_name=parsed_name, unit=canon_unit, dimension=unit_dim,
                decision="reject", match_type="exact", reason="单位量纲与标准术语不符",
                score=1.0, margin=None, item=None, method=method,
                candidates=[_property_candidate(item, 1.0)],
            )
        return _property_payload(
            query=name, normalized_name=parsed_name, unit=canon_unit, dimension=unit_dim,
            decision="accept", match_type="exact", reason=None,
            score=1.0, margin=None, item=item, method=method,
            candidates=[_property_candidate(item, 1.0)],
        )

    allowed = _allowed_properties(lexicon, unit_dim)
    ranked, decision, score, margin, match_type = _search(
        service, "property", method, parsed_name, allowed,
    )
    if not ranked and unit_dim is not None:
        return _property_payload(
            query=name, normalized_name=parsed_name, unit=canon_unit, dimension=unit_dim,
            decision="reject", match_type=match_type, reason="没有量纲相符的候选",
            score=0.0, margin=None, item=None, method=method, candidates=[],
        )
    if decision == "borderline" and context_fields:
        ranked = _rerank_with_context(ranked, lexicon.properties, context_fields)
        decision, score, margin = decide(ranked, **_thresholds(method, "property"))
    item = lexicon.properties[ranked[0][0]] if decision != "reject" and ranked else None
    if decision == "reject":
        item = None
    return _property_payload(
        query=name, normalized_name=parsed_name, unit=canon_unit, dimension=unit_dim,
        decision=decision, match_type=match_type,
        reason=None if decision != "reject" else "未找到足够接近的标准属性",
        score=score, margin=margin, item=item, method=method,
        candidates=[_property_candidate(lexicon.properties[i], s) for i, s in ranked],
    )


def align_object(name, method=None):
    """把材料对象名对齐到 entity_term。化学式和牌号返回实例标识，不进模糊检索。

    method 为 embedding（默认，Qwen3-Embedding-8B）或 ngram。
    """
    service = get_service()
    method = _resolve_method(method)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name 不能为空")
    text = clean_display(name)
    lexicon = service.lexicon
    exact_id = lexicon.entity_exact.get(fold(text))
    if exact_id is not None:
        return _class_result(name, "exact", "accept", 1.0, None, lexicon.entities[exact_id], [
            _entity_candidate(lexicon.entities[exact_id], 1.0),
        ], method=method)

    composition = parse_composition(text)
    if composition is not None:
        return _instance_result(name, "formula", composition, lexicon, method)
    if re.search(r"\d", text):
        return _instance_result(name, "grade", None, lexicon, method)

    ranked, decision, score, margin, match_type = _search(service, "entity", method, text)
    item = lexicon.entities[ranked[0][0]] if decision != "reject" and ranked else None
    if decision == "reject":
        item = None
    return _class_result(
        name, match_type, decision, score, margin, item,
        [_entity_candidate(lexicon.entities[i], s) for i, s in ranked],
        reason=None if decision != "reject" else "未找到足够接近的标准实体",
        method=method,
    )


def _thresholds(method, kind):
    if method != "embedding":
        return {}
    if kind == "property":
        return {
            "accept": config.EMBED_PROPERTY_ACCEPT,
            "borderline": config.EMBED_PROPERTY_BORDERLINE,
            "margin_min": config.EMBED_PROPERTY_MARGIN,
        }
    return {
        "accept": config.EMBED_OBJECT_ACCEPT,
        "borderline": config.EMBED_OBJECT_BORDERLINE,
        "margin_min": config.EMBED_OBJECT_MARGIN,
    }


def _search(service, kind, method, text, allowed=None):
    if method == "embedding":
        ranked = service.embed_index(kind).rank(text, allowed=allowed)
        match_type = "embedding"
    else:
        index = service.property_index if kind == "property" else service.entity_index
        ranked = index.rank(text, allowed=allowed)
        match_type = "semantic"
    decision, score, margin = decide(ranked, **_thresholds(method, kind))
    return ranked, decision, score, margin, match_type


def _allowed_properties(lexicon, unit_dim):
    if not unit_dim:
        return None
    return {
        i for i, item in enumerate(lexicon.properties)
        if item.dimension is None or item.dimension == unit_dim
    }


def _context_bonus(name_cn, context_fields):
    bonus = 0
    for field in context_fields or []:
        other, _unit = split_name_and_unit(str(field))
        if len(other) >= 2 and other in name_cn:
            bonus += 1
    return bonus


def _rerank_with_context(ranked, entries, context_fields):
    decorated = [
        (_context_bonus(entries[i].name_cn, context_fields), score, i)
        for i, score in ranked
    ]
    decorated.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [(i, score) for _bonus, score, i in decorated]


def _round_score(score):
    if score is None:
        return None
    return round(float(score), 4)


def _property_candidate(item, score):
    return {
        "name_cn": item.name_cn,
        "name_en": item.name_en,
        "score": _round_score(score),
        "role": item.role,
        "dimension": item.dimension,
    }


def _property_payload(query, normalized_name, unit, dimension, decision, match_type,
                      reason, score, margin, item, candidates, method):
    return {
        "query": query,
        "method": method,
        "normalized_name": normalized_name,
        "unit": unit,
        "dimension": dimension,
        "decision": decision,
        "match_type": match_type,
        "reason": reason,
        "canonical_name": item.name_cn if item else None,
        "canonical_name_en": item.name_en if item else None,
        "role": item.role if item else None,
        "score": _round_score(score),
        "margin": _round_score(margin),
        "candidates": candidates,
    }


def _entity_candidate(item, score):
    return {
        "name_cn": item.name_cn,
        "name_en": item.name_en,
        "uri": item.uri,
        "score": _round_score(score),
    }


def _parent_payload(entity):
    if entity is None:
        return None
    return {"name_cn": entity.name_cn, "name_en": entity.name_en, "uri": entity.uri}


def _class_result(query, match_type, decision, score, margin, item, candidates, reason=None, method=None):
    return {
        "query": query,
        "method": method,
        "kind": "class",
        "decision": decision,
        "match_type": match_type,
        "reason": reason,
        "canonical_name": item.name_cn if item else None,
        "canonical_name_en": item.name_en if item else None,
        "uri": item.uri if item else None,
        "score": _round_score(score),
        "margin": _round_score(margin),
        "instance_id": None,
        "canonical_formula": None,
        "composition": None,
        "parent_class": None,
        "candidates": candidates,
    }


def _instance_result(query, kind, composition, lexicon, method):
    formula = format_formula(composition) if composition else None
    parent = lexicon.longest_class_in(clean_display(query))
    return {
        "query": query,
        "method": method,
        "kind": kind,
        "decision": "instance_only",
        "match_type": "instance",
        "reason": "化学式或牌号作为实例标识，不对实体词表做模糊匹配",
        "canonical_name": None,
        "canonical_name_en": None,
        "uri": None,
        "score": None,
        "margin": None,
        "instance_id": formula if kind == "formula" else clean_display(query),
        "canonical_formula": formula,
        "composition": composition_payload(composition) if composition else None,
        "parent_class": _parent_payload(parent),
        "candidates": [],
    }
