"""Cycle test: B imports A (creates cycle)."""

import cycle_a


def b_func() -> int:
    return cycle_a.a_func() + 1