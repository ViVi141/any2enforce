"""Entry module: re-exported helper via package __init__."""

from pkg2 import helper


def run(x: int) -> int:
    return helper(x)
