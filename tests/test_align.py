# -*- coding: utf-8 -*-
import json
import os
import sys
import threading
import urllib.request

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)

from term_align.align import align_object, align_property  # noqa: E402
from term_align.formula import format_formula, parse_composition  # noqa: E402
from term_align.server import Handler  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_formula():
    comp = parse_composition("Fe2O3")
    check(comp == {"Fe": 2.0, "O": 3.0}, comp)
    check(format_formula(comp) == "Fe2O3", format_formula(comp))
    dashed = parse_composition("Ti-6Al-4V")
    check(dashed == {"Ti": 1.0, "Al": 6.0, "V": 4.0}, dashed)
    check(format_formula(dashed) == "Al6TiV4", format_formula(dashed))
    check(parse_composition("304不锈钢") is None, "含汉字不按化学式解析")
    check(parse_composition("Q235") is None, "牌号不是化学式")


def test_property():
    sintering = align_property("烧结温度")
    check(sintering["decision"] == "accept" and sintering["match_type"] == "exact", sintering)
    check(sintering["canonical_name"] == "烧结温度", sintering)
    check(sintering["role"] == "工艺", sintering["role"])

    embedded = align_property("烧结温度(℃)")
    check(embedded["decision"] == "accept" and embedded["unit"] == "℃", embedded)
    check(embedded["dimension"] == "temperature", embedded)

    conflict = align_property("密度", unit="℃")
    check(conflict["decision"] == "reject" and "量纲" in (conflict["reason"] or ""), conflict)

    hardness = align_property("HRC")
    check(hardness["decision"] == "accept" and hardness["canonical_name"] == "硬度", hardness)
    check(hardness["role"] == "结果", hardness["role"])

    missing = align_property("zzzz-not-a-property")
    check(missing["decision"] == "reject", missing)

    vague = align_property("温度")
    check(vague["decision"] in ("accept", "borderline"), vague)
    check(vague["candidates"] and "温度" in vague["candidates"][0]["name_cn"], vague["candidates"][:3])


def test_object():
    steel = align_object("不锈钢")
    check(steel["kind"] == "class" and steel["decision"] == "accept", steel)
    check(steel["match_type"] == "exact" and "stainless_steel" in steel["uri"], steel)

    oxide = align_object("Fe2O3")
    check(oxide["kind"] == "formula" and oxide["decision"] == "instance_only", oxide)
    check(oxide["canonical_formula"] == "Fe2O3" and oxide["composition"] == {"Fe": 2, "O": 3}, oxide)
    check(oxide["parent_class"] is None and oxide["uri"] is None, oxide)

    grade = align_object("Q235")
    check(grade["kind"] == "grade" and grade["decision"] == "instance_only", grade)
    check(grade["instance_id"] == "Q235" and grade["parent_class"] is None, grade)

    mixed = align_object("304不锈钢")
    check(mixed["kind"] == "grade" and mixed["decision"] == "instance_only", mixed)
    check(mixed["parent_class"]["name_cn"] == "不锈钢", mixed["parent_class"])

    alloy = align_object("Ti-6Al-4V")
    check(alloy["kind"] == "formula" and alloy["canonical_formula"] == "Al6TiV4", alloy)


def test_http():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as resp:
            health = json.loads(resp.read().decode("utf-8"))
        check(health["ok"] and health["n_properties"] > 100 and health["n_entities"] > 1000, health)
        body = json.dumps({"name": "屈服强度"}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/align/property",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        check(payload["ok"] and payload["result"]["canonical_name"] == "屈服强度", payload)
        body = json.dumps({"name": "双相钢"}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/align/object",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        check(payload["result"]["decision"] == "accept" and payload["result"]["canonical_name"] == "双相钢", payload)
    finally:
        server.shutdown()


if __name__ == "__main__":
    test_formula()
    test_property()
    test_object()
    test_http()
    print("ok")
