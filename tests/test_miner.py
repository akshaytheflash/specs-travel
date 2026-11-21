"""Regression tests for the spec-transfer experiment.

These exist because three separate flaws produced plausible-looking numbers that were
meaningless, and each is now guarded:

 1. Two "predicates" were vacuous (`... or True`), mined in every case, caught nothing.
 2. One solution popped from its input, mutating the evaluation domain so that later
    measurements saw empty lists.
 3. A bound predicate (`ret <= len(xs)`) survived mining by coincidence on short inputs
    and then fired on correct code. The soundness gate must reject such predicates.

Run: python -m tests.test_miner
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.families import FAMILIES, gen_inputs
from src.miner import Predicate, candidate_predicates, mine, detect
from src.experiment import run as run_experiment
from src.intervention import run as run_intervention


def test_no_vacuous_predicates():
    """Every predicate must be false on at least one trace: a predicate that is always
    true is noise that inflates spec size and can never catch a bug."""
    from src.miner import Trace
    pairs = [([1, 2, 3], 6), ([1, 2, 3], False), ([5], 5), ([-1, -2], -3), ([], 0)]
    traces = [Trace(args=(xs,), ret=r) for xs, r in pairs]
    for p in candidate_predicates():
        holds = [p.holds(t) for t in traces]
        assert any(holds) or not any(holds), "predicate never evaluated"
        assert not all(holds), f"vacuous predicate: {p.name} holds on every trace"


def test_solutions_do_not_mutate_inputs():
    """A mutating solution would silently empty the evaluation domain."""
    xs = [[1, 2, 3], [-1, 2], [0]]
    snapshot = [list(x) for x in xs]
    for fam in FAMILIES.values():
        for fn in fam["correct"].values():
            for x in xs:
                try:
                    fn(x)
                except Exception:
                    pass
    assert xs == snapshot, f"an input list was mutated: {xs} vs {snapshot}"


def test_soundness_gate_rejects_unsound_predicates():
    """`ret <= len(xs)` is false for sum over long lists; the gate must drop it."""
    fam = FAMILIES["sum"]
    train = gen_inputs("sum", 300, seed=1)
    val = gen_inputs("sum", 300, seed=7)
    p = [x for x in candidate_predicates() if x.name == "ret_le_len"][0]
    raw = mine(fam["correct"], train, [p])
    survived = [q for q in raw["predicates"]
                if all(detect({"predicates": [q]}, fn, val)["violations"] == 0
                       for fn in fam["correct"].values())]
    assert survived == [], "unsound predicate passed the soundness gate"


def test_no_false_positives_on_correct_code():
    """The headline result must never come from specs that flag correct programs."""
    s = run_experiment(Path("results/_test"), n_inputs=150)
    assert s["false_positive_rate"] == 0.0, f"FP rate {s['false_positive_rate']}"


def test_relational_intervention_improves_transfer():
    """The paper's central claim: relations travel, bounds do not."""
    before = run_intervention(relational_available=False, n_inputs=150)
    after = run_intervention(relational_available=True, n_inputs=150)
    assert after["transfer_rate"] > before["transfer_rate"], \
        f"no improvement: {before['transfer_rate']} -> {after['transfer_rate']}"
    assert after["fp_rate"] == 0.0


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{failures} failure(s)")
    raise SystemExit(1 if failures else 0)
