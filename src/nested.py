"""The central experiment: do RELATIONAL specs travel where BOUNDS do not?

Pilot observation that motivates this script: with a generic predicate battery, a mined
spec for `sum` transfers to held-out buggy implementations 100% of the time, while
specs for `count_positive` and `is_sorted` transfer 0% of the time. Inspecting what was
mined explains it: the successful spec contained a *relational* predicate
(`ret == sum(xs)`) linking output to input, whereas the failures contained only
*bounds* (`ret >= 0`, `ret <= len(xs)`) plus type trivia (`isinstance(ret, bool)`,
which makes `ret >= 0` vacuously true and therefore meaningless).

Hypothesis: transfer rate is governed by whether the mined spec contains at least one
predicate that relates the output to the *contents* of the input, not merely its shape
or type.

This script separates the predicate battery into two families (BOUND vs RELATIONAL),
runs all four combinations, and reports the transfer rate for each.
"""
from __future__ import annotations

import json
from pathlib import Path

from .families import FAMILIES, gen_inputs
from .miner import candidate_predicates, mine, detect


# ------------------------------------------------------------------ taxonomy
RELATIONAL_NAMES = {
    "ret_eq_sum",          # ret == sum(xs)
    "ret_ge_sum",          # ret >= sum(xs)
    "ret_le_sum",          # ret <= sum(xs)
    "ret_ge_min",          # ret >= min(xs)
    "ret_le_max",          # ret <= max(xs)
    "ret_le_maxabs",       # ret <= max|x|
    "ret_eq_len_or_zero",  # ret == 0 or ret == len(xs)
}

BOUND_NAMES = {
    "ret_int", "ret_bool", "ret_le_len", "ret_ge_zero", "ret_ge_0_or_present",
}


def split_predicates(preds):
    relational = [p for p in preds if p.name in RELATIONAL_NAMES]
    bounds = [p for p in preds if p.name in BOUND_NAMES]
    return relational, bounds


def run_condition(fam: str, fam_data: dict, preds, n_inputs: int) -> dict:
    """Mine from all-but-one correct solution, test on bugs planted in the held-out one."""
    correct, bugs = fam_data["correct"], fam_data["bugs"]
    train = gen_inputs(fam, n_inputs, seed=1)
    val = gen_inputs(fam, n_inputs, seed=7)
    evalx = gen_inputs(fam, n_inputs, seed=99)

    rows = []
    for target in correct:
        sources = {k: v for k, v in correct.items() if k != target}
        raw = mine(sources, train, preds, min_support=1.0)

        # soundness gate: keep only predicates that hold on ALL correct solutions
        keep = []
        for p in raw["predicates"]:
            if all(detect({"predicates": [p]}, fn, val)["violations"] == 0
                   for fn in correct.values()):
                keep.append(p)

        spec = {"predicates": keep}
        clean = detect(spec, correct[target], evalx)

        for bname, bfn in bugs.items():
            res = detect(spec, bfn, evalx)
            rows.append({
                "family": fam, "target": target, "bug": bname,
                "spec": [p.name for p in keep],
                "spec_size": len(keep),
                "has_relational": any(p.name in RELATIONAL_NAMES for p in keep),
                "clean_fp": int(clean["violations"] > 0),
                "caught": int(res["violations"] > 0),
                "violations": res["violations"],
            })
    return rows


def main(out: Path = Path("results/nested"), n_inputs: int = 400) -> dict:
    preds = candidate_predicates()
    relational, bounds = split_predicates(preds)
    conditions = {
        "bounds_only": bounds,
        "relational_only": relational,
        "both": preds,
    }
    all_rows = {}
    for cname, cpreds in conditions.items():
        rows = []
        for fam, fam_data in FAMILIES.items():
            rows += run_condition(fam, fam_data, cpreds, n_inputs)
        all_rows[cname] = rows

    out.mkdir(parents=True, exist_ok=True)
    (out / "nested.json").write_text(json.dumps(all_rows, indent=1))

    summary = {}
    for cname, rows in all_rows.items():
        n = len(rows)
        caught = sum(r["caught"] for r in rows)
        fp = sum(r["clean_fp"] for r in rows)
        with_rel = [r for r in rows if r["has_relational"]]
        summary[cname] = {
            "n": n,
            "transfer_rate": caught / n,
            "fp_rate": fp / n,
            "mean_spec_size": sum(r["spec_size"] for r in rows) / n,
            "n_with_relational": len(with_rel),
            "transfer_rate_when_relational": (
                sum(r["caught"] for r in with_rel) / len(with_rel) if with_rel else None),
        }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    s = main()
    print(f"{'condition':18s} {'n':>4} {'transfer':>9} {'FP':>7} {'spec':>6} {'with relational':>16} {'transfer|rel':>13}")
    for k, v in s.items():
        tr = v["transfer_rate_when_relational"]
        print(f"{k:18s} {v['n']:>4} {v['transfer_rate']:>8.1%} {v['fp_rate']:>6.1%} "
              f"{v['mean_spec_size']:>6.1f} {v['n_with_relational']:>16} "
              f"{(f'{tr:.1%}' if tr is not None else 'n/a'):>13}")
