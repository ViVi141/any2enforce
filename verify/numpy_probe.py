"""
numpy_probe.py — an EnforceScript float32 emulator + verification prototype.

Purpose:
  Provide a self-contained numeric prototype that mirrors EnforceScript's
  float32-only arithmetic, compares it against real NumPy (float64) reference
  computations, and demonstrates the float32-vs-float64 drift that motivates
  any2enforce's "approximate numerics only" guarantee.

Dependencies:
  numpy 2.4.4  (stdlib + numpy only)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# 1.  EnforceScript float32 emulator
# ---------------------------------------------------------------------------

_F32 = np.float32  # shorthand


@dataclass
class Array1D:
    """
    A 1-D numeric array that stores every element as float32, mirroring
    EnforceScript's native float type.
    """
    data: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Cast every element to float32 at construction time
        self.data = [float(_F32(x)) for x in self.data]

    @property
    def length(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> float:
        return self.data[idx]

    def __setitem__(self, idx: int, val: float) -> None:
        self.data[idx] = float(_F32(val))

    def __repr__(self) -> str:
        return f"Array1D({self.data!r})"


# ---------------------------------------------------------------------------
# EnforceScript-mirroring math functions  (all intermediate casts to float32)
# ---------------------------------------------------------------------------

def _f32(x: float) -> float:
    """Cast *x* through float32 and back to Python float."""
    return float(_F32(x))


def es_sum(a: Array1D) -> float:
    """EnforceScript element sum."""
    s = _F32(0.0)
    for x in a.data:
        s += _F32(x)
    return float(s)


def es_mean(a: Array1D) -> float:
    """EnforceScript arithmetic mean."""
    n = a.length
    if n == 0:
        return 0.0
    return _f32(es_sum(a) / _F32(n))


def es_std(a: Array1D, ddof: int = 0) -> float:
    """
    EnforceScript population (ddof=0) or sample (ddof=1) standard deviation.
    Uses the two-pass formula for numerical stability within float32.
    """
    n = a.length
    if n <= ddof:
        return 0.0
    mu = es_mean(a)
    s = _F32(0.0)
    for x in a.data:
        d = _F32(x) - _F32(mu)
        s += _F32(d * d)
    return _f32(_F32(math.sqrt(float(s) / (n - ddof))))  # sqrt on Python float, then cast


def es_dot(a: Array1D, b: Array1D) -> float:
    """EnforceScript dot product."""
    if a.length != b.length:
        raise ValueError(f"es_dot length mismatch: {a.length} vs {b.length}")
    s = _F32(0.0)
    for x, y in zip(a.data, b.data):
        s += _F32(_F32(x) * _F32(y))
    return float(s)


def es_matmul(a: List[Array1D], b: List[Array1D]) -> List[Array1D]:
    """
    EnforceScript matrix multiply  (a as m×k, b as k×n).
    Each row of *a* and *b* is an Array1D.
    Returns a list of Array1D rows (each in float32).
    """
    if not a or not b:
        return []
    m, k_a = len(a), a[0].length
    k_b, n = len(b), b[0].length
    if k_a != k_b:
        raise ValueError(f"es_matmul inner dim mismatch: {k_a} vs {k_b}")
    result: List[Array1D] = []
    for i in range(m):
        row = [0.0] * n
        for j in range(n):
            s = _F32(0.0)
            for t in range(k_a):
                s += _F32(_F32(a[i][t]) * _F32(b[t][j]))
            row[j] = float(s)
        result.append(Array1D(row))
    return result


def es_square(a: Array1D) -> Array1D:
    """Element-wise square."""
    return Array1D([_f32(_F32(x) * _F32(x)) for x in a.data])


def es_exp(a: Array1D) -> Array1D:
    """Element-wise exp."""
    return Array1D([_f32(math.exp(_f32(x))) for x in a.data])


def es_abs(a: Array1D) -> Array1D:
    """Element-wise absolute value."""
    return Array1D([_f32(abs(_f32(x))) for x in a.data])


# ---------------------------------------------------------------------------
# 2.  Verification routine
# ---------------------------------------------------------------------------

MAX_ABS_ERR = 1e-5  # absolute tolerance  (float32 ~7 digits of precision)
MAX_REL_ERR = 1e-4  # relative tolerance  (1e-4 is conservative for f32)


def _np_array(a: Array1D) -> np.ndarray:
    return np.array(a.data, dtype=np.float64)


def verify_case(
    name: str,
    es_val: float,
    np_val: float,
    abs_tol: float = MAX_ABS_ERR,
    rel_tol: float = MAX_REL_ERR,
) -> Tuple[bool, float, float]:
    """Return (pass, abs_error, rel_error)."""
    abs_err = abs(es_val - np_val)
    rel_err = abs_err / max(abs(np_val), 1e-15)
    passed = abs_err <= abs_tol or rel_err <= rel_tol
    return passed, abs_err, rel_err


def verify_case_array(
    name: str,
    es_arr: Array1D,
    np_arr: np.ndarray,
    abs_tol: float = MAX_ABS_ERR,
    rel_tol: float = MAX_REL_ERR,
) -> Tuple[bool, float, float]:
    """Element-wise max error over arrays."""
    if es_arr.length != len(np_arr):
        return False, float("inf"), float("inf")
    abs_errs = [abs(es_arr[i] - float(np_arr[i])) for i in range(es_arr.length)]
    max_abs = max(abs_errs)
    max_rel = max(
        a / max(abs(float(np_arr[i])), 1e-15)
        for i, a in enumerate(abs_errs)
    )
    passed = max_abs <= abs_tol or max_rel <= rel_tol
    return passed, max_abs, max_rel


# ---------------------------------------------------------------------------
# 3.  Float32 vs Float64 drift demo
# ---------------------------------------------------------------------------

def float32_vs_float64_drift() -> None:
    """
    Compute statistics over a large array with wide magnitude spread in
    float32 and float64, then print the differences and a short explanation.
    """
    rng = np.random.default_rng(42)

    # Build an array with values spanning many orders of magnitude
    n = 2000
    raw = np.exp(rng.uniform(-5.0, 15.0, size=n))  # exp → range ~0.007 .. 3.3e6

    f32_arr = np.float32(raw)
    f64_arr = np.float64(raw)

    # Mean
    f32_mean = np.float32(np.mean(f32_arr))
    f64_mean = np.mean(f64_arr)
    mean_diff = float(f32_mean) - float(f64_mean)

    # Std
    f32_std = np.float32(np.std(f32_arr))
    f64_std = np.std(f64_arr)
    std_diff = float(f32_std) - float(f64_std)

    print("\n" + "=" * 72)
    print("  Float32 vs Float64 drift demo")
    print("=" * 72)
    print(f"  Array size : {n}")
    print(f"  Value range: {float(raw.min()):.6g}  …  {float(raw.max()):.6g}")
    print()
    print(f"  {'Quantity':<20s}  {'float32':<16s}  {'float64':<16s}  {'Diff':<16s}")
    print(f"  {'─'*19:<20s}  {'─'*15:<16s}  {'─'*15:<16s}  {'─'*15:<16s}")
    print(f"  {'mean':<20s}  {float(f32_mean):<16.8g}  {f64_mean:<16.8g}  {mean_diff:<+16.8g}")
    print(f"  {'std':<20s}  {float(f32_std):<16.8g}  {f64_std:<16.8g}  {std_diff:<+16.8g}")
    print()

    explanation = (
        "  EnforceScript stores all floats as IEEE-754 binary32 (float32),\n"
        "  which provides ~7 decimal digits of precision.  The reference\n"
        "  implementation uses Python / NumPy float64 (~15 digits).  The\n"
        "  differences above are expected and inherent to the representation.\n"
        "  This is why any2enforce guarantees only *approximate* numerics:\n"
        "  two implementations that both comply with the spec may differ in\n"
        "  the 5th–7th significant digit due to float32 precision, operation\n"
        "  order, and the use of fused multiply-add or other hardware\n"
        "  optimisations."
    )
    print(explanation)
    print("=" * 72)


# ---------------------------------------------------------------------------
# 4.  main() — clean verification report
# ---------------------------------------------------------------------------

def _approx_eq(es_val: float, np_val: float) -> bool:
    """Return True if values are 'close enough' for display purposes."""
    return abs(es_val - np_val) < 1e-4 * max(abs(np_val), 1e-15) + 1e-5


def main() -> int:
    print("=" * 72)
    print("  numpy_probe.py  —  EnforceScript float32 emulator verification")
    print("=" * 72)

    total = 0
    passed = 0

    # -- Helper to run one scalar case --
    def run_scalar(
        label: str,
        emu_val: float,
        ref_val: float,
        es_expr: str = "",
    ) -> None:
        nonlocal total, passed
        total += 1
        p, ae, re = verify_case(label, emu_val, ref_val)
        status = "PASS" if p else "FAIL"
        if p:
            passed += 1
        print(f"\n  [{status}] {label}")
        print(f"         emulated : {emu_val!r}")
        print(f"         ref      : {ref_val!r}")
        print(f"         abs err  : {ae:.6e}")
        print(f"         rel err  : {re:.6e}")
        if es_expr:
            print(f"         (es code: {es_expr})")

    # -- Helper to run one array case --
    def run_array(
        label: str,
        emu_arr: Array1D,
        ref_arr: np.ndarray,
        es_expr: str = "",
    ) -> None:
        nonlocal total, passed
        total += 1
        p, ae, re = verify_case_array(label, emu_arr, ref_arr)
        status = "PASS" if p else "FAIL"
        if p:
            passed += 1
        print(f"\n  [{status}] {label}")
        print(f"         max abs err : {ae:.6e}")
        print(f"         max rel err : {re:.6e}")
        if es_expr:
            print(f"         (es code: {es_expr})")

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    # --- 1. sum ---
    a4 = Array1D([1.0, 2.0, 3.0, 4.0])
    a16 = Array1D([float(i) for i in range(1, 17)])
    a100 = Array1D([float(i) for i in range(1, 101)])

    run_scalar("sum [4]", es_sum(a4), 10.0, "sum(a4)")
    run_scalar("sum [16]", es_sum(a16), 136.0, "sum(a16)")
    run_scalar("sum [100]", es_sum(a100), 5050.0, "sum(a100)")

    # --- 2. mean ---
    run_scalar("mean [4]", es_mean(a4), np.mean([1., 2., 3., 4.]))
    run_scalar("mean [16]", es_mean(a16), np.mean(np.arange(1., 17.)))

    # --- 3. std ---
    run_scalar("std [4] (pop)", es_std(a4, ddof=0), np.std([1., 2., 3., 4.], ddof=0))
    run_scalar("std [4] (sample)", es_std(a4, ddof=1), np.std([1., 2., 3., 4.], ddof=1))

    # --- 4. dot ---
    b4 = Array1D([4.0, 5.0, 6.0, 7.0])
    run_scalar("dot [4]", es_dot(a4, b4), np.dot([1., 2., 3., 4.], [4., 5., 6., 7.]))

    # --- 5. matmul  (2×3 dot 3×2 → 2×2) ---
    A = [Array1D([1.0, 2.0, 3.0]), Array1D([4.0, 5.0, 6.0])]      # 2×3
    B = [Array1D([7.0, 8.0]), Array1D([9.0, 10.0]), Array1D([11.0, 12.0])]  # 3×2
    es_mm = es_matmul(A, B)
    ref_mm = np.array([[1., 2., 3.], [4., 5., 6.]]) @ np.array([[7., 8.], [9., 10.], [11., 12.]])
    # Flatten both for comparison
    flat_es = Array1D([es_mm[i][j] for i in range(len(es_mm)) for j in range(es_mm[0].length)])
    flat_ref = ref_mm.flatten()
    run_array("matmul 2×3·3×2", flat_es, flat_ref, "matmul(A, B)")

    # --- 6. element-wise square ---
    run_array("square [4]", es_square(a4), np.square([1., 2., 3., 4.]))

    # --- 7. element-wise exp ---
    exp_in = Array1D([0.0, 1.0, 2.0, 3.0])
    run_array("exp [4]", es_exp(exp_in), np.exp([0., 1., 2., 3.]))

    # --- 8. element-wise abs ---
    neg = Array1D([-1.0, 2.0, -3.0, 4.0])
    run_array("abs [4]", es_abs(neg), np.abs([-1., 2., -3., 4.]))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 72)
    print(f"  Results:  {passed} / {total} passed")
    if passed == total:
        print("  All checks PASS — float32 emulator is working as expected.")
    else:
        print(f"  ⚠  {total - passed} case(s) exceeded tolerance.")
    print("=" * 72)

    # ------------------------------------------------------------------
    # Drift demo
    # ------------------------------------------------------------------
    float32_vs_float64_drift()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())