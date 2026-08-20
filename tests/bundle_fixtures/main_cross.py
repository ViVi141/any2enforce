"""Entry: cross-module module-alias and from-import calls (Stage B)."""

from libx import vecmath


def norm(v: list[float]) -> float:
    return vecmath.magnitude(v)


def total(a: list[float], b: list[float]) -> float:
    return vecmath.dot(a, b)
