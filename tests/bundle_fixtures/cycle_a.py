"""Cycle test: A imports B."""

import cycle_b


def a_func() -> int:
    return cycle_b.b_func() + 1