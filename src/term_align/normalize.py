# -*- coding: utf-8 -*-
"""查询规范化：折叠比较键，并从属性名里拆出夹带的单位。"""
import re

_SPACE_RE = re.compile(r"[\s_\-]+")
_UNIT_SPLIT_RE = re.compile(r"^(?P<name>.+?)[\(（\[/](?P<unit>[^)）\]/]{1,16})[\)）\]]?$")


def fold(text):
    """精确匹配用的比较键：去空白、下划线和连字符，拉丁字母小写。"""
    if text is None:
        return ""
    return _SPACE_RE.sub("", str(text).strip().lower())


def clean_display(text):
    return re.sub(r"\s+", " ", str(text).strip())


def split_name_and_unit(raw):
    """从「烧结温度(℃)」「烧结温度/℃」里拆出名称和单位。拆不开则单位为 None。"""
    text = clean_display(raw)
    text = text.replace("（", "(").replace("）", ")").replace("【", "[").replace("】", "]")
    match = _UNIT_SPLIT_RE.match(text.replace(" ", ""))
    if not match:
        return text, None
    name = match.group("name").strip()
    unit = match.group("unit").strip()
    if not name or not unit:
        return text, None
    return name, unit
