# -*- coding: utf-8 -*-
"""单位到量纲。只用于过滤明显不符的属性候选。"""

# 别名 → (规范写法, 量纲)
_UNIT_ALIASES = {
    "℃": ("℃", "temperature"),
    "°c": ("℃", "temperature"),
    "degc": ("℃", "temperature"),
    "k": ("K", "temperature"),
    "kelvin": ("K", "temperature"),
    "℉": ("℉", "temperature"),
    "°f": ("℉", "temperature"),
    "s": ("s", "time"),
    "sec": ("s", "time"),
    "秒": ("s", "time"),
    "ms": ("ms", "time"),
    "min": ("min", "time"),
    "分钟": ("min", "time"),
    "h": ("h", "time"),
    "hr": ("h", "time"),
    "小时": ("h", "time"),
    "pa": ("Pa", "pressure"),
    "kpa": ("kPa", "pressure"),
    "mpa": ("MPa", "pressure"),
    "gpa": ("GPa", "pressure"),
    "nm": ("nm", "length"),
    "μm": ("μm", "length"),
    "um": ("μm", "length"),
    "µm": ("μm", "length"),
    "mm": ("mm", "length"),
    "cm": ("cm", "length"),
    "m": ("m", "length"),
    "oe": ("Oe", "magnetic"),
    "koe": ("kOe", "magnetic"),
    "t": ("T", "magnetic"),
    "g/cm3": ("g/cm3", "density"),
    "g/cm³": ("g/cm3", "density"),
    "kg/m3": ("kg/m3", "density"),
    "%": ("%", "fraction"),
    "wt%": ("wt%", "fraction"),
    "at%": ("at%", "fraction"),
}


def parse_unit(unit):
    """返回 (规范单位, 量纲)。认不出时量纲为 None，调用方不做过滤。"""
    if unit is None:
        return None, None
    raw = str(unit).strip()
    if not raw:
        return None, None
    hit = _UNIT_ALIASES.get(raw.lower()) or _UNIT_ALIASES.get(raw)
    if hit:
        return hit
    return raw, None
