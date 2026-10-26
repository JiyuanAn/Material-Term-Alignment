# -*- coding: utf-8 -*-
"""对齐接口测试脚本。

在项目根目录运行：

    python test_api.py
    python test_api.py --property 烧结温度
    python test_api.py --object Fe2O3

不带参数时跑内置样例：核对预期字段，并打印每一条的判定。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from term_align import align_object, align_property  # noqa: E402


PROPERTY_CASES = [
    {"name": "烧结温度", "expect": {"decision": "accept", "canonical_name": "烧结温度", "role": "工艺"}},
    {"name": "烧结温度(℃)", "expect": {"decision": "accept", "canonical_name": "烧结温度", "unit": "℃"}},
    {"name": "HRC", "expect": {"decision": "accept", "canonical_name": "硬度", "role": "结果"}},
    {"name": "YS", "expect": {"decision": "accept", "canonical_name": "屈服强度"}},
    {"name": "密度", "unit": "℃", "expect": {"decision": "reject"}},
    {"name": "zzzz-not-a-property", "expect": {"decision": "reject"}},
    {"name": "温度", "expect": {"decision_in": ("accept", "borderline")}},
]

OBJECT_CASES = [
    {"name": "不锈钢", "expect": {"kind": "class", "decision": "accept", "canonical_name": "不锈钢"}},
    {"name": "双相钢", "expect": {"kind": "class", "decision": "accept", "canonical_name": "双相钢"}},
    {"name": "Fe2O3", "expect": {"kind": "formula", "decision": "instance_only", "canonical_formula": "Fe2O3"}},
    {"name": "Q235", "expect": {"kind": "grade", "decision": "instance_only", "instance_id": "Q235"}},
    {"name": "304不锈钢", "expect": {"kind": "grade", "decision": "instance_only", "parent_class": "不锈钢"}},
    {"name": "Ti-6Al-4V", "expect": {"kind": "formula", "decision": "instance_only", "canonical_formula": "Al6TiV4"}},
    {"name": "not-a-material-zzzz", "expect": {"kind": "class", "decision": "reject"}},
]


def _parent_name(result):
    parent = result.get("parent_class") or {}
    return parent.get("name_cn")


def format_property(result):
    target = result.get("canonical_name") or "-"
    role = result.get("role") or "-"
    unit = result.get("unit") or "-"
    score = result.get("score")
    score_txt = "-" if score is None else f"{score:.3f}"
    return f"{result['decision']:<14} {result['match_type']:<10} {target:<16} 角色={role:<4} 单位={unit:<6} 分数={score_txt}"


def format_object(result):
    if result["decision"] == "instance_only":
        ident = result.get("canonical_formula") or result.get("instance_id") or "-"
        parent = _parent_name(result) or "-"
        comp = result.get("composition") or "-"
        return f"{result['kind']:<10} {result['decision']:<14} 实例={ident:<12} 父类={parent:<8} 成分={comp}"
    target = result.get("canonical_name") or "-"
    score = result.get("score")
    score_txt = "-" if score is None else f"{score:.3f}"
    return f"{result['kind']:<10} {result['decision']:<14} {result.get('match_type') or '-':<10} 术语={target:<12} 分数={score_txt}"


def check_expect(result, expect):
    errors = []
    for key, wanted in expect.items():
        if key == "decision_in":
            if result.get("decision") not in wanted:
                errors.append(f"decision={result.get('decision')} 不在 {wanted}")
            continue
        if key == "parent_class":
            got = _parent_name(result)
        else:
            got = result.get(key)
        if got != wanted:
            errors.append(f"{key}={got!r} 期望 {wanted!r}")
    return errors


def run_cases(title, cases, align_fn, formatter):
    print(f"\n== {title} ==")
    failed = 0
    for case in cases:
        kwargs = {"name": case["name"]}
        if case.get("unit"):
            kwargs["unit"] = case["unit"]
        result = align_fn(**kwargs)
        label = case["name"] if not case.get("unit") else f"{case['name']} unit={case['unit']}"
        print(f"  {label:<22} {formatter(result)}")
        errors = check_expect(result, case["expect"])
        if errors:
            failed += 1
            print("    未通过: " + "；".join(errors))
    return failed


def run_one(kind, name, unit):
    if kind == "property":
        result = align_property(name, unit=unit)
        print(format_property(result))
        for cand in result.get("candidates") or []:
            print(f"    候选 {cand['name_cn']}  {cand['score']}  {cand.get('role')}")
        return
    result = align_object(name)
    print(format_object(result))
    for cand in result.get("candidates") or []:
        print(f"    候选 {cand['name_cn']}  {cand['score']}")


def main():
    parser = argparse.ArgumentParser(description="测试属性名对齐与对象名对齐")
    parser.add_argument("--property", help="只查询这一条属性名")
    parser.add_argument("--object", help="只查询这一条对象名")
    parser.add_argument("--unit", help="配合 --property，单独指定单位")
    args = parser.parse_args()
    if args.property and args.object:
        parser.error("--property 和 --object 只能指定一个")
    if args.property:
        run_one("property", args.property, args.unit)
        return
    if args.object:
        run_one("object", args.object, None)
        return

    print("装载词表并运行内置样例...")
    failed = 0
    failed += run_cases("属性名对齐", PROPERTY_CASES, align_property, format_property)
    failed += run_cases("对象名对齐", OBJECT_CASES, align_object, format_object)
    total = len(PROPERTY_CASES) + len(OBJECT_CASES)
    print(f"\n{total - failed}/{total} 通过")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
