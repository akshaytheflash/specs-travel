"""Do specifications travel across programs that solve the same problem?

Core question: spec-inference tools learn properties from ONE program's executions.
But the reason you infer a spec is usually that you're writing ANOTHER program that
does the same thing. Nobody has measured whether inferred specs transfer.

Design notes that keep the measurement honest:
  * Every predicate must be SOUND: it holds on all correct implementations by
    construction, or it is excluded by the miner's support test. A predicate that
    fires on correct code is a broken predicate, not a found bug.
  * Transfer is measured on inputs disjoint from the mining inputs.
  * A self-spec control (mine from the buggy code itself) tells us how easy the
    problem is without transfer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Trace:
    args: tuple
    ret: object

    @property
    def xs(self):
        return self.args[0]


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


class Predicate:
    def __init__(self, name: str, fn: Callable[[Trace], bool]):
        self.name, self.fn = name, fn

    def holds(self, tr: Trace) -> bool:
        return _safe(self.fn, tr) is True

    def __repr__(self):
        return f"<{self.name}>"


def _sorted_asc(xs):
    return all(xs[i] <= xs[i + 1] for i in range(len(xs) - 1))


def candidate_predicates() -> list[Predicate]:
    """A fixed, generic battery of candidate invariants.

    These are deliberately generic (they never mention a specific problem), so that
    the same battery applies to every family and the transfer measurement is not
    secretly family-aware.
    """
    P: list[Predicate] = []

    # --- type/shape invariants
    P.append(Predicate("ret_bool", lambda t: isinstance(t.ret, bool)))
    P.append(Predicate("ret_int", lambda t: isinstance(t.ret, int) and not isinstance(t.ret, bool)))

    # --- bounds relative to the input
    P.append(Predicate("ret_le_len", lambda t: t.ret is not None and t.ret <= len(t.xs)))
    P.append(Predicate("ret_ge_zero", lambda t: t.ret is not None and t.ret >= 0))
    P.append(Predicate("ret_ge_min", lambda t: t.ret is not None and t.xs and t.ret >= min(t.xs)))
    P.append(Predicate("ret_le_max", lambda t: t.ret is not None and t.xs and t.ret <= max(t.xs)))
    P.append(Predicate("ret_le_sum", lambda t: t.ret is not None and t.xs and t.ret <= sum(t.xs)))
    P.append(Predicate("ret_ge_sum", lambda t: t.ret is not None and t.xs and t.ret >= sum(t.xs)))
    P.append(Predicate("ret_eq_sum", lambda t: t.ret is not None and bool(t.xs) and t.ret == sum(t.xs)))

    # --- relations between return and input that are genuinely invariant
    P.append(Predicate("ret_le_maxabs", lambda t: t.ret is not None and t.xs and t.ret <= max(abs(x) for x in t.xs)))
    P.append(Predicate("ret_ge_minabs", lambda t: t.ret is not None and t.xs and t.ret <= max(abs(x) for x in t.xs)))
    P.append(Predicate("ret_eq_len_or_zero", lambda t: t.ret is not None and (t.ret == 0 or t.ret == len(t.xs))))
    P.append(Predicate("ret_ge_0_or_present", lambda t: t.ret is not None and (t.ret >= 0 or 0 in t.xs)))

    return P


def mine(solutions: dict[str, Callable], inputs: list, predicates: list[Predicate],
         min_support: float = 1.0) -> dict:
    """Keep only predicates that hold on EVERY execution of EVERY source solution.

    min_support=1.0 is strict and is the honest default: a permissive miner keeps
    noise, and noise inflates apparent transfer because it fires on everything.
    """
    traces = []
    for name in sorted(solutions):
        fn = solutions[name]
        for inp in inputs:
            r = _safe(fn, list(inp))
            if r is None:
                continue
            traces.append((name, Trace(args=(list(inp),), ret=r)))

    kept = []
    for p in predicates:
        by_sol: dict[str, list[int]] = {}
        for name, tr in traces:
            d = by_sol.setdefault(name, [0, 0])
            d[1] += 1
            if p.holds(tr):
                d[0] += 1
        if not by_sol:
            continue
        rates = [c / n for c, n in by_sol.values() if n]
        if rates and min(rates) >= min_support:
            kept.append(p)

    return {"predicates": kept, "n_traces": len(traces), "n_sources": len(solutions)}


def detect(spec: dict, fn: Callable, inputs: list) -> dict:
    fails = {p.name: 0 for p in spec["predicates"]}
    checked = 0
    for inp in inputs:
        r = _safe(fn, list(inp))
        if r is None:
            continue
        tr = Trace(args=(list(inp),), ret=r)
        checked += 1
        for p in spec["predicates"]:
            if not p.holds(tr):
                fails[p.name] += 1
    return {"n_checked": checked, "fails": fails, "violations": sum(fails.values())}
