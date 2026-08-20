"""Entry module: imports from a package."""

from pkg import core


def run(a: float, b: float) -> float:
    return core.compute(a, b)