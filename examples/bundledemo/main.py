"""Bundle demo entry.

Imports the bundled dependency library `lib.vecmath` and exercises it.

Goal for the real-Workbench verify case: the ENTIRE bundle output
(dependency library + entry) must be compilable and runnable with 0 errors.

v0.1/Stage-A boundary: cross-module call rewiring is NOT implemented yet, so
entry functions here must NOT call `vecmath.xxx` at runtime (that would emit a
bare `vecmath.magnitude(...)` reference the EnforceScript compiler rejects as
undefined). Functions here therefore use only the entry's own scope / the
dependency is pulled into the closure purely by `import`; the Workbench test
drives the dependency library's own self-contained top-level functions
(`lib_vecmath_*`) directly.
"""

from lib import vecmath


def make_weights() -> dict[str, float]:
    cfg = {"border": 0.5, "center": 1.0}
    cfg["corner"] = 0.25
    return cfg
