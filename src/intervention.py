"""Intervention: if bounds don't travel, does supplying problem-appropriate RELATIONS
recover transfer?

The nested experiment showed relational predicates transfer (75% when present) while
bounds transfer 0% -- but for `count_positive` and `is_sorted`, no relational predicate
from the generic battery was ever mined, because none of the generic relations express
"count" or "sortedness" over the *contents*.

This script tests the causal claim: give the miner a relation that is appropriate to the
family, and transfer should appear. If it does not, the relational hypothesis is wrong.

Relations added:
  count:  ret == number of elements satisfying the family's own predicate
  sorted: ret == (xs is non-decreasing)  -- expressed as a predicate over contents

These are still family-agnostic in form (each is a single lambda over the trace); only
their *availability* differs between conditions, which is exactly the variable we want.
"""
from __future__ import annotations

import json
from pathlib import Path

from .families import FAMILIES, gen_inputs
from .miner import Predicate, candidate_predicates, mine, detect
from .nested import RELATIONAL_NAMES

# Relations keyed by family. Each is a genuine output<->content relation, not a bound.
EXTRA_RELATIONS = {
    "count_positive": [
        Predicate("ret_eq_positive_count",
                  lambda t: t.ret is not None and t.ret == sum(1 for x in t.xs if x > 0)),
        Predicate("ret_le_len_positive",
                  lambda t: t.ret is not None and t.ret <= sum(1 for x in t.xs)),
    ],
    "is_sorted": [
        Predicate("ret_eq_sortedness",
                  lambda t: t.ret is not None
                  and t.ret == all(t.xs[i] <= t.xs[i + 1] for i in range(len(t.xs) - 1))),
    ],
    "sum": [
        Predicate("ret_eq_sum_strict",
                  lambda t: t.ret is not None and bool(t.xs) and t.ret == sum(t.xs)),
    ],
    "max_subarray": [
        Predicate("ret_ge_every_prefix",
                  lambda t: t.ret is not None and all(
                      t.ret >= sum(t.xs[i:j])
                      for i in range(len(t.xs))
                      for j in range(i + 1, len(t.xs) + 1))),
    ],
}


def run(relational_available: bool, n_inputs: int = 400) -> dict:
    rows = []
    for fam, fam_data in FAMILIES.items():
        preds = list(candidate_predicates())
        if relational_available:
            preds += EXTRA_RELATIONS.get(fam, [])
        correct, bugs = fam_data["correct"], fam_data["bugs"]
        train = gen_inputs(fam, n_inputs, seed=1)
        val = gen_inputs(fam, n_inputs, seed=7)
        evalx = gen_inputs(fam, n_inputs, seed=99)

        for target in correct:
            sources = {k: v for k, v in correct.items() if k != target}
            raw = mine(sources, train, preds)
            keep = [p for p in raw["predicates"]
                    if all(detect({"predicates": [p]}, fn, val)["violations"] == 0
                           for fn in correct.values())]
            spec = {"predicates": keep}
            clean = detect(spec, correct[target], evalx)
            for bname, bfn in bugs.items():
                res = detect(spec, bfn, evalx)
                rows.append({
                    "family": fam, "target": target, "bug": bname,
                    "spec": [p.name for p in keep], "spec_size": len(keep),
                    "clean_fp": int(clean["violations"] > 0),
                    "caught": int(res["violations"] > 0),
                })
    n = len(rows)
    return {
        "n": n,
        "transfer_rate": sum(r["caught"] for r in rows) / n,
        "fp_rate": sum(r["clean_fp"] for r in rows) / n,
        "mean_spec_size": sum(r["spec_size"] for r in rows) / n,
        "by_family": {
            fam: {
                "n": len([r for r in rows if r["family"] == fam]),
                "transfer_rate": (sum(r["caught"] for r in rows if r["family"] == fam)
                                  / max(1, len([r for r in rows if r["family"] == fam]))),
                "specs": [r["spec"] for r in rows if r["family"] == fam][:2],
            } for fam in FAMILIES
        },
        "rows": rows,
    }


if __name__ == "__main__":
    out = Path("results/intervention")
    out.mkdir(parents=True, exist_ok=True)
    before = run(relational_available=False)
    after = run(relational_available=True)
    (out / "before.json").write_text(json.dumps(before, indent=1))
    (out / "after.json").write_text(json.dumps(after, indent=1))

    print(f"{'':22s} {'transfer':>9} {'FP':>6} {'spec':>6}")
    print(f"{'generic battery':22s} {before['transfer_rate']:>8.1%} {before['fp_rate']:>5.1%} {before['mean_spec_size']:>6.1f}")
    print(f"{'+ family relations':22s} {after['transfer_rate']:>8.1%} {after['fp_rate']:>5.1%} {after['mean_spec_size']:>6.1f}")
    print()
    for fam in FAMILIES:
        b, a = before["by_family"][fam], after["by_family"][fam]
        print(f"  {fam:16s} {b['transfer_rate']:>6.1%} -> {a['transfer_rate']:>6.1%}")
