# -*- coding: utf-8 -*-
"""装载属性词表、实体词表和属性别名，并建立精确匹配索引。"""
import csv
from dataclasses import dataclass
from typing import Optional

from . import config
from .normalize import fold

_PROCESS = [
    "工艺", "process", "烧结", "回火", "温度", "时间", "路线", "制备",
    "route", "treatment", "sinter", "anneal", "method", "方法",
    "压力", "压强", "保温", "冷却", "加热", "气氛", "转速", "球磨",
    "时效", "淬火", "退火", "轧制", "锻造", "固溶", "升温", "时长",
]
_RESULT = [
    "性能", "硬度", "韧性", "强度", "hardness", "toughness", "strength",
    "modulus", "energy", "enthalpy", "密度", "density", "疲劳", "fatigue",
    "模量", "延伸", "屈服", "抗拉", "导电", "热导", "磁化", "剩磁", "矫顽",
    "孔隙", "晶粒", "塑性", "冲击",
]
_DIMENSIONS = [
    ("temperature", ["温度", "熔点", "temperature", "melting"]),
    ("time", ["时间", "时长", "time"]),
    ("magnetic", ["矫顽", "磁通", "磁化", "coerciv"]),
    ("density", ["密度", "density"]),
    ("hardness", ["硬度", "hardness"]),
    ("pressure", ["压力", "压强", "应力", "强度", "pressure", "stress", "strength"]),
    ("length", ["长度", "厚度", "粒径", "尺寸", "length", "thickness"]),
    ("fraction", ["含量", "孔隙率", "分数", "比例"]),
]


@dataclass
class PropertyTerm:
    name_cn: str
    name_en: str
    role: str
    dimension: Optional[str]


@dataclass
class EntityTerm:
    name_cn: str
    name_en: str
    uri: str
    local_name: str


def _rightmost(name, groups):
    """groups: list[(label, keywords)]。取最靠右的关键词，对应中文复合词的中心语。"""
    if not name:
        return None
    lower = str(name).lower()
    hits = []
    for label, keywords in groups:
        for kw in keywords:
            idx = lower.find(kw.lower())
            if idx >= 0:
                hits.append((idx, len(kw), label))
    if not hits:
        return None
    hits.sort()
    return hits[-1][2]


def property_role(name_cn, name_en=""):
    groups = [("工艺", _PROCESS), ("结果", _RESULT)]
    return _rightmost(name_cn, groups) or _rightmost(name_en, groups) or "结果"


def property_dimension(name_cn, name_en=""):
    groups = list(_DIMENSIONS)
    return _rightmost(name_cn, groups) or _rightmost(name_en, groups)


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Lexicon:
    def __init__(self):
        self.properties: list[PropertyTerm] = []
        self.entities: list[EntityTerm] = []
        self.property_exact: dict[str, int] = {}
        self.entity_exact: dict[str, int] = {}
        self.entity_names_by_length: list[str] = []

    def load(self):
        self._load_properties()
        self._load_entities()
        self._load_aliases()
        self.entity_names_by_length = sorted(
            {item.name_cn for item in self.entities if len(item.name_cn) >= 2},
            key=len,
            reverse=True,
        )

    def _add_exact(self, index, key, row_id):
        key = fold(key)
        if key and key not in index:
            index[key] = row_id

    def _load_properties(self):
        seen = set()
        for row in _read_csv(config.PROPERTY_TERM_CSV):
            name_cn = (row.get("name_cn") or "").strip()
            name_en = (row.get("name_en") or "").strip()
            if not name_cn or name_cn in config.PROPERTY_DENYLIST:
                continue
            key = fold(name_cn)
            if not key or key in seen:
                continue
            seen.add(key)
            item = PropertyTerm(
                name_cn=name_cn,
                name_en=name_en,
                role=property_role(name_cn, name_en),
                dimension=property_dimension(name_cn, name_en),
            )
            row_id = len(self.properties)
            self.properties.append(item)
            self._add_exact(self.property_exact, name_cn, row_id)
            self._add_exact(self.property_exact, name_en, row_id)

    def _load_entities(self):
        seen = set()
        for row in _read_csv(config.ENTITY_TERM_CSV):
            name_cn = (row.get("name_cn") or "").strip()
            if not name_cn:
                continue
            key = fold(name_cn)
            if not key or key in seen:
                continue
            seen.add(key)
            item = EntityTerm(
                name_cn=name_cn,
                name_en=(row.get("name_en") or "").strip(),
                uri=(row.get("uri") or "").strip(),
                local_name=(row.get("local_name") or "").strip(),
            )
            row_id = len(self.entities)
            self.entities.append(item)
            self._add_exact(self.entity_exact, name_cn, row_id)
            self._add_exact(self.entity_exact, item.name_en, row_id)
            self._add_exact(self.entity_exact, item.local_name, row_id)

    def _load_aliases(self):
        if not config.PROPERTY_ALIAS_CSV.is_file():
            return
        by_cn = {fold(item.name_cn): idx for idx, item in enumerate(self.properties)}
        for row in _read_csv(config.PROPERTY_ALIAS_CSV):
            alias = (row.get("alias") or "").strip()
            target = fold(row.get("canonical_name_cn") or "")
            if alias and target in by_cn:
                self._add_exact(self.property_exact, alias, by_cn[target])

    def longest_class_in(self, text):
        """名称里显式出现的最长实体类名。用于牌号/化学式附带父类，不做模糊匹配。"""
        if not text:
            return None
        for name in self.entity_names_by_length:
            if name != text and name in text:
                return self.entities[self.entity_exact[fold(name)]]
        return None
