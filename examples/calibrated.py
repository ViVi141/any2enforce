"""Mappings calibrated against the real Reforger scripts corpus
(C:\\Users\\74738\\Desktop\\_reforger_code_full_v2\\scripts)."""


def pick(a: int, b: int) -> int:
    return a if a > b else b


def extremes(values: list[int]) -> None:
    lo = values[0]
    hi = values[0]
    for v in values:
        lo = min(lo, v)
        hi = max(hi, v)
    diff = hi - lo
    sign = abs(diff)
    print("range", sign)


def make_config() -> dict[str, int]:
    cfg = {"a": 1, "b": 2}
    cfg["c"] = 3
    return cfg


def names() -> list[str]:
    result = ["alice", "bob"]
    return result


def is_member(values: list[int], probe: int) -> bool:
    return probe in values


def not_member(values: list[int], probe: int) -> bool:
    return probe not in values


def wrap(deg: float) -> float:
    return deg % 360.0


def doubles(values: list[int]) -> list[int]:
    return [v * 2 for v in values if v > 0]


def index_map(values: list[int]) -> dict[int, int]:
    result: dict[int, int] = {v: v * v for v in values}
    return result
