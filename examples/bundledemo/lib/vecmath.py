"""Vector / numeric helpers for the bundled demo.

A small pure-Python library (numpy-free) that any2enforce's bundle mode
compiles together with the entry module into a single EnforceScript file.

Written strictly within the v0.1 supported subset so the bundle output is
clean (0 diagnostics) and directly compilable by the real Workbench:
  - functions iterate typed *parameters*, not `self` fields (foreach over a
    field's element type is not yet inferred in v0.1);
  - dict literals use direct un-annotated assignment (the v0.1-backed form);
  - no cross-module symbol rewiring yet (Stage B), so each top-level function
    here is a self-contained unit callable from a Workbench test.
"""


def dot(a: list[float], b: list[float]) -> float:
    # dot product: count loop + index read of typed parameters
    acc = 0.0
    for i in range(len(a)):
        acc += a[i] * b[i]
    return acc


def magnitude(v: list[float]) -> float:
    # sum of squares via foreach over a typed parameter
    s = 0.0
    for x in v:
        s += x * x
    return s


def mean(v: list[float]) -> float:
    if len(v) == 0:
        return 0.0
    total = dot(v, _ones(len(v)))
    return total / len(v)


def _ones(n: int) -> list[float]:
    out = []
    for i in range(n):
        out.append(1.0)
    return out


def weighted_sum(weights: dict[str, float], key: str, fallback: float) -> float:
    # map read with fallback: `key in weights` -> weights.Contains(key)
    if key in weights:
        return weights[key]
    return fallback
