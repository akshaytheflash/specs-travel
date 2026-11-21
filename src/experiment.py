"""Cross-solution spec transfer experiment.

Two-stage validity, because the first version of this script produced specs that
fired on CORRECT code (a sum can exceed its list's length, so `ret_le_len` was only
true by luck on short mining inputs). Reporting transfer rate on top of unsound
specs would have been meaningless.

Stage 1 (mining):  keep predicates that hold on every execution of every SOURCE.
Stage 2 (soundness gate): a mined predicate is retained only if it also holds on
   EVERY correct solution across a HELD-OUT validation domain. This is the step that
   removes predicates which survived by coincidence.

Only after both gates do we measure transfer to buggy implementations.
"""
from __future__ import annotations

import json
from pathlib import Path

from .families import FAMILIES, gen_inputs
from .miner import candidate_predicates, mine, detect, Predicate


def sound_filter(spec: dict, correct: dict, val_inputs: list) -> tuple[list[Predicate], list[str]]:
    """Drop mined predicates that fire on any correct implementation."""
    keep, dropped = [], []
    for p in spec["predicates"]:
        bad = False
        for name, fn in correct.items():
            res = detect({"predicates": [p]}, fn, val_inputs)
            if res["violations"] > 0:
                bad = True
                break
        (dropped if bad else keep).append(p if not bad else p.name)
    return keep, dropped


def run(out_dir: Path = Path('results'), n_inputs: int = 400, min_support: float = 1.0) -> dict:
    preds = candidate_predicates()
    rows = []
    for fam, fam_data in FAMILIES.items():
        correct = fam_data["correct"]
        bugs = fam_data["bugs"]
        train_inputs = gen_inputs(fam, n_inputs, seed=1)
        val_inputs = gen_inputs(fam, n_inputs, seed=7)
        eval_inputs = gen_inputs(fam, n_inputs, seed=99)

        for target in correct:
            sources = {k: v for k, v in correct.items() if k != target}
            raw = mine(sources, train_inputs, preds, min_support=min_support)
            kept, dropped = sound_filter(raw, correct, val_inputs)
            spec = {"predicates": kept}
            mined_names = [p.name for p in kept]

            clean = detect(spec, correct[target], eval_inputs)

            for bug_name, bug_fn in bugs.items():
                res = detect(spec, bug_fn, eval_inputs)
                self_spec = mine({bug_name: bug_fn}, train_inputs, preds, min_support=min_support)
                self_kept, _ = sound_filter(self_spec, {bug_name: bug_fn}, val_inputs)
                self_res = detect({"predicates": self_kept}, bug_fn, eval_inputs)

                rows.append({
                    "family": fam, "target_solution": target, "bug": bug_name,
                    "n_mined_raw": len(raw["predicates"]),
                    "n_dropped_unsound": len(dropped),
                    "dropped": dropped,
                    "n_mined": len(mined_names), "mined": mined_names,
                    "clean_violations": clean["violations"],
                    "bug_violations": res["violations"],
                    "caught": int(res["violations"] > 0),
                    "self_spec_size": len(self_kept),
                    "self_caught": int(self_res["violations"] > 0),
                })

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "runs.json").write_text(json.dumps(rows, indent=1))
    return summarise(rows)


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    by_family = {}
    for fam in sorted({r["family"] for r in rows}):
        fr = [r for r in rows if r["family"] == fam]
        by_family[fam] = {
            "n": len(fr),
            "transfer_rate": sum(r["caught"] for r in fr) / len(fr),
            "mean_spec_size": sum(r["n_mined"] for r in fr) / len(fr),
            "mean_dropped": sum(r["n_dropped_unsound"] for r in fr) / len(fr),
        }
    return {
        "n_cases": n,
        "transfer_rate": sum(r["caught"] for r in rows) / n,
        "self_rate": sum(r["self_caught"] for r in rows) / n,
        "false_positive_cases": sum(1 for r in rows if r["clean_violations"] > 0),
        "false_positive_rate": sum(1 for r in rows if r["clean_violations"] > 0) / n,
        "mean_spec_size": sum(r["n_mined"] for r in rows) / n,
        "mean_dropped_unsound": sum(r["n_dropped_unsound"] for r in rows) / n,
        "by_family": by_family,
        "rows": rows,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results")
    ap.add_argument("--n", type=int, default=400)
    a = ap.parse_args()
    s = run(Path(a.out), n_inputs=a.n)
    print(f"cases                : {s['n_cases']}")
    print(f"transfer rate        : {s['transfer_rate']:.2%}")
    print(f"self-spec rate       : {s['self_rate']:.2%}")
    print(f"unsound (FP) rate    : {s['false_positive_rate']:.2%}   <- must be 0")
    print(f"mean spec size       : {s['mean_spec_size']:.1f} predicates")
    print(f"dropped at sound gate: {s['mean_dropped_unsound']:.1f}")
    print()
    for fam, d in s["by_family"].items():
        print(f"  {fam:16s} n={d['n']:2d} transfer={d['transfer_rate']:.2%} "
              f"spec={d['mean_spec_size']:.1f} dropped={d['mean_dropped']:.1f}")
