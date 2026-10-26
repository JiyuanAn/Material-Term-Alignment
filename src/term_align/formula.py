# -*- coding: utf-8 -*-
"""化学式解析。能整段解析才算化学式，否则交给牌号或类名。"""
import re

_ELEMENTS = [
    "He", "Li", "Be", "Ne", "Na", "Mg", "Al", "Si", "Cl", "Ar", "Ca", "Sc", "Ti", "Cr", "Mn",
    "Fe", "Co", "Ni", "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Zr", "Nb",
    "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn", "Sb", "Te", "Xe", "Cs", "Ba", "La",
    "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu", "Hf",
    "Ta", "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi", "Th", "Pa", "Np", "Pu",
    "H", "B", "C", "N", "O", "F", "P", "S", "K", "V", "Y", "I", "W", "U",
]
_ELEM_LOWER = {el.lower(): el for el in _ELEMENTS}
_ELEM_BY_LEN = sorted(_ELEM_LOWER, key=len, reverse=True)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")


def _read_element(text, index):
    lower = text.lower()
    for token in _ELEM_BY_LEN:
        if lower.startswith(token, index):
            return _ELEM_LOWER[token], index + len(token)
    return None, index


def _read_number(text, index):
    match = _NUMBER_RE.match(text, index)
    if not match:
        return None, index
    return float(match.group()), match.end()


def _add(comp, element, count):
    comp[element] = comp.get(element, 0.0) + (count if count else 1.0)


def _parse_concat(text):
    comp = {}
    index = 0
    while index < len(text):
        element, index = _read_element(text, index)
        if element is None:
            return None
        count, index = _read_number(text, index)
        _add(comp, element, count)
    return comp or None


def _parse_dashed(text):
    parts = [part for part in re.split(r"[-_/]", text) if part]
    if len(parts) < 2:
        return None
    comp = {}
    for part in parts:
        index = 0
        count, index = _read_number(part, index)
        element, index = _read_element(part, index)
        if element is None:
            return None
        trailing, index = _read_number(part, index)
        if index != len(part):
            return None
        _add(comp, element, count if count is not None else trailing)
    return comp or None


def parse_composition(text):
    """返回 {元素: 计数}。含汉字、或无法整段吃完的字符串返回 None。"""
    raw = re.sub(r"\s+", "", str(text))
    if not raw or _HAS_CJK.search(raw):
        return None
    if re.fullmatch(r"[A-Za-z0-9.]+", raw):
        parsed = _parse_concat(raw)
        if parsed:
            return parsed
    if re.fullmatch(r"[A-Za-z0-9.\-/]+", raw):
        return _parse_dashed(raw)
    return None


def format_formula(comp):
    parts = []
    for element in sorted(comp):
        count = comp[element]
        if abs(count - round(count)) < 1e-6:
            shown = "" if int(round(count)) == 1 else str(int(round(count)))
        else:
            shown = f"{count:g}"
        parts.append(element + shown)
    return "".join(parts)


def composition_payload(comp):
    payload = {}
    for element, count in comp.items():
        if abs(count - round(count)) < 1e-6:
            payload[element] = int(round(count))
        else:
            payload[element] = round(count, 4)
    return payload
