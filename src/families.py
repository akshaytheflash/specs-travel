"""Problem families: each has N correct solutions and N bug-injected variants.

Design constraint that matters for validity: every "correct" solution must agree on
every input in the domain, and every bug must actually change the answer on at least
one input. We assert both, so a failure to transfer cannot be blamed on a wrong
baseline or a bug that does not bite.
"""
from __future__ import annotations

import random
from typing import Callable


# ------------------------------------------------------------ family 1
# "return an index at which the list is non-decreasing" is too rich; we use simple
# numeric aggregates so that a spec can be stated with the predicates we mine.

def p1_sum_correct_a(xs):
    return sum(xs)

def p1_sum_correct_b(xs):
    t = 0
    for x in xs:
        t += x
    return t

def p1_sum_correct_c(xs):
    # NOTE: iterates a copy. An earlier version popped from xs, which mutated the
    # caller's input list and silently emptied the evaluation domain for every later
    # call -- it made every measurement in the experiment meaningless.
    t = 0
    for x in reversed(list(xs)):
        t += x
    return t

def p1_sum_bug_drops_last(xs):
    t = 0
    for x in xs[:-1]:
        t += x
    return t

def p1_sum_bug_double_first(xs):
    return sum(xs) + (xs[0] if xs else 0)


# ------------------------------------------------------------ family 2
# "count elements above a threshold"

def p2_count_correct_a(xs):
    return len([x for x in xs if x > 0])

def p2_count_correct_b(xs):
    n = 0
    for x in xs:
        if x > 0:
            n += 1
    return n

def p2_count_correct_c(xs):
    return sum(1 for x in xs if x > 0)

def p2_count_bug_ge_zero(xs):
    return len([x for x in xs if x >= 0])

def p2_count_bug_abs(xs):
    return len([x for x in xs if abs(x) > 0])


# ------------------------------------------------------------ family 3
# "maximum subarray sum" (kadane) -- a genuinely non-trivial invariant carrier

def p3_kadane_correct_a(xs):
    best = cur = xs[0]
    for x in xs[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best

def p3_kadane_correct_b(xs):
    best = xs[0]
    for i in range(len(xs)):
        s = 0
        for j in range(i, len(xs)):
            s += xs[j]
            best = max(best, s)
    return best

def p3_kadane_correct_c(xs):
    best, cur = xs[0], xs[0]
    for x in xs[1:]:
        cur = cur + x if cur + x > x else x
        if cur > best:
            best = cur
    return best

def p3_kadane_bug_all_negative(xs):
    # fails only when every element is negative
    best = cur = 0
    for x in xs:
        cur = max(0, cur + x)
        best = max(best, cur)
    return best

def p3_kadane_bug_ignores_last(xs):
    if len(xs) < 2:
        return xs[0]
    return p3_kadane_correct_a(xs[:-1])


# ------------------------------------------------------------ family 4
# "is the list sorted?"

def p4_sorted_correct_a(xs):
    return all(xs[i] <= xs[i + 1] for i in range(len(xs) - 1))

def p4_sorted_correct_b(xs):
    return xs == sorted(xs)

def p4_sorted_correct_c(xs):
    it = iter(xs)
    try:
        prev = next(it)
    except StopIteration:
        return True
    for x in it:
        if prev > x:
            return False
        prev = x
    return True

def p4_sorted_bug_strict(xs):
    return all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))

def p4_sorted_bug_skips_last(xs):
    return all(xs[i] <= xs[i + 1] for i in range(len(xs) - 2))


FAMILIES = {
    "sum": {
        "correct": {"a": p1_sum_correct_a, "b": p1_sum_correct_b, "c": p1_sum_correct_c},
        "bugs": {"drops_last": p1_sum_bug_drops_last, "double_first": p1_sum_bug_double_first},
    },
    "count_positive": {
        "correct": {"a": p2_count_correct_a, "b": p2_count_correct_b, "c": p2_count_correct_c},
        "bugs": {"ge_zero": p2_count_bug_ge_zero, "abs": p2_count_bug_abs},
    },
    "max_subarray": {
        "correct": {"a": p3_kadane_correct_a, "b": p3_kadane_correct_b, "c": p3_kadane_correct_c},
        "bugs": {"all_negative": p3_kadane_bug_all_negative, "ignores_last": p3_kadane_bug_ignores_last},
    },
    "is_sorted": {
        "correct": {"a": p4_sorted_correct_a, "b": p4_sorted_correct_b, "c": p4_sorted_correct_c},
        "bugs": {"strict": p4_sorted_bug_strict, "skips_last": p4_sorted_bug_skips_last},
    },
}


def gen_inputs(kind: str, n: int, seed: int = 0) -> list[list[int]]:
    """Inputs for a family. Deliberately includes edge cases, because a bug that only
    bites on an edge is exactly the case a transferred spec should catch."""
    rng = random.Random(seed)
    out: list[list[int]] = []
    if kind in ("sum", "count_positive", "max_subarray"):
        out.append([1])                      # singleton
        out.append([-1])                     # singleton negative
        out.append([-5, -2, -9])             # all negative
        out.append([0, 0, 0])
        out.append([1, 2, 3])
        while len(out) < n:
            m = rng.randint(1, 6)
            out.append([rng.randint(-5, 5) for _ in range(m)])
    elif kind == "is_sorted":
        out.append([1])
        out.append([])
        out.append([1, 1])                   # duplicates: kills a strictness bug
        out.append([2, 1])
        out.append([1, 2, 3])
        while len(out) < n:
            m = rng.randint(1, 6)
            xs = sorted(rng.randint(-5, 5) for _ in range(m))
            if rng.random() < 0.4:
                i = rng.randrange(len(xs))
                xs[i] = xs[i] + rng.randint(10, 20)   # unsort it
            out.append(xs)
    return out
