"""Cross-module dependency library for Stage-B tests."""


def magnitude(v: list[float]) -> float:
    s = 0.0
    for x in v:
        s += x * x
    return s


def dot(a: list[float], b: list[float]) -> float:
    acc = 0.0
    for i in range(len(a)):
        acc += a[i] * b[i]
    return acc
