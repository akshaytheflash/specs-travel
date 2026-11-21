# Do Specifications Travel?

**Relational invariants transfer across programs; bounds do not.**

A specification mined from one correct implementation should describe the *problem*, not
that implementation. We test whether it does.

## The question

Spec-inference tools (Daikon and successors) learn properties from the executions of **one**
program. The reason you would infer a spec is usually that you are writing **another**
program that solves the same thing — a reference implementation vs. your own, a rewrite, a
port, an autograder submission.

Nobody has measured whether the inferred spec transfers.

## The result

| Battery | Transfer | False positives |
|---|---|---|
| Bounds only (`ret >= 0`, `ret <= len(xs)`, `ret is int`) | **0.0%** | 0% |
| Relations only (`ret == sum(xs)`, `ret >= min(xs)`) | 37.5% | 0% |
| Both | 37.5% | 0% |
| Both + one family-appropriate relation | **87.5%** | 0% |

**Every caught case contains a relation to input contents. No case without one is caught.**
Spec size does not separate the classes (3.7 vs 3.4 predicates), so successful specs are not
merely larger — they describe a different kind of thing.

Supplying a single relation appropriate to the family lifts the two failing families from
0% to 100%.

## Why it matters

A spec made of bounds is true of almost everything, and a property true of everything is
not a specification. Tool builders who score themselves on *number of invariants* are
optimising the wrong quantity.

## Repo layout

```
src/miner.py         predicate battery, mining, detection, soundness gate
src/families.py      4 problem families: 3 correct solutions + 2 bugs each
src/experiment.py    the transfer protocol (mine -> gate -> evaluate)
src/nested.py        bounds vs relations partition, 3 conditions
src/intervention.py  add family-appropriate relation; 37.5% -> 87.5%
tests/test_miner.py  5 regression tests (see below)
paper/paper.tex      IEEE two-column paper
results/             JSON artifacts used by the paper
```

## Reproduce

```bash
python3 -m src.experiment      # transfer protocol, generic battery
python3 -m src.nested          # bounds / relations / both
python3 -m src.intervention    # before vs after adding a relation
python3 -m tests.test_miner    # regression tests
cd paper && pdflatex paper.tex && pdflatex paper.tex
```

No GPU, no downloads, ~30 seconds total.

## Three bugs we made, and now guard against

Each produced plausible-looking numbers that were meaningless. They are documented because
the same traps apply to anyone building a similar benchmark:

1. **Vacuous predicates.** Predicates written as `... or True` always hold. They were mined
   in 24/24 cases and caught nothing while inflating spec size.
2. **Input mutation.** One correct solution consumed its argument with `list.pop()`, which
   emptied the evaluation domain for every later call. *A single mutating implementation
   invalidated every number in the experiment.*
3. **Coincidental soundness.** `ret <= len(xs)` held on short mining inputs, then fired on
   correct code. Hence the soundness gate: validate against every correct solution on
   disjoint inputs.

`tests/test_miner.py` asserts all three are fixed, plus that no spec ever flags correct code
and that the relational intervention actually improves transfer.

## Limitations

Four hand-built families in one language; eight hand-written bugs. The *ordering* (bounds
below relations) follows from what predicates can express and should generalise; the
absolute percentages should not be quoted outside this setting.

## Citation

```bibtex
@misc{specsTravel2026,
  title  = {Do Specifications Travel? Relational Invariants Transfer Across Programs, Bounds Do Not},
  author = {Akshay},
  year   = {2026},
  note   = {https://github.com/akshaytheflash/specs-travel}
}
```
