"""Bundle demo entry.

Imports the bundled dependency library `lib.vecmath` and exercises it,
including real cross-module runtime calls (Stage B: module-alias rewiring).

Two import styles are exercised to cover Stage B:
  - ``from lib import vecmath``  -> ``vecmath.<fn>(...)`` rewires to the
    dependency's prefixed global function (e.g. ``lib_vecmath_magnitude``).
  - ``from lib.vecmath import weighted_sum`` -> bare ``weighted_sum(...)``
    rewires to ``lib_vecmath_weighted_sum``.
"""

from lib import vecmath
from lib.vecmath import weighted_sum


def make_weights() -> dict[str, float]:
    cfg = {"border": 0.5, "center": 1.0}
    cfg["corner"] = 0.25
    return cfg


def describe_magnitude(v: list[float]) -> str:
    # cross-module call via module alias -> lib_vecmath_magnitude(v)
    mag = vecmath.magnitude(v)
    return f"mag={mag}"


def total_dot(a: list[float], b: list[float]) -> float:
    # cross-module call via module alias -> lib_vecmath_dot(a, b)
    return vecmath.dot(a, b)


def pick_weight(key: str, fallback: float) -> float:
    # bare imported function -> lib_vecmath_weighted_sum
    w = make_weights()
    return weighted_sum(w, key, fallback)
