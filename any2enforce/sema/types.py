"""Type annotation parsing: raw annotation text -> IR Type."""

from __future__ import annotations

from ..ir import (
    AUTO, BOOL, FLOAT, INT, STRING, VOID, ArrayType, ClassType, ErrorType,
    MapType, ScalarType, SetType, Type,
)

_SCALARS = {
    "int": INT, "float": FLOAT, "bool": BOOL,
    "str": STRING, "string": STRING,
}


def parse_type_annotation(text: str, *, is_return: bool = False) -> Type:
    """Parse a (mostly) PEP 484 annotation string into an IR Type.

    Unsupported / unresolvable annotations degrade to ErrorType (the caller
    must pair this with an error diagnostic).
    """
    t = _normalize(text)
    if not t:
        return VOID if is_return else AUTO

    # Optional[T] / T | None -> the non-None branch
    t = _strip_optional(t)

    if t in ("None", "NoneType"):
        return VOID if is_return else AUTO

    if t in _SCALARS:
        return _SCALARS[t]

    base = t.split("[", 1)[0]
    if base.lower() == "list" and "[" in t:
        return ArrayType(parse_type_annotation(_inner(t)))
    if base.lower() == "dict" and "[" in t:
        kv = _split_top(_inner(t))
        if len(kv) == 2:
            return MapType(parse_type_annotation(kv[0]),
                           parse_type_annotation(kv[1]))
        return ErrorType()
    if base.lower() == "set" and "[" in t:
        return SetType(parse_type_annotation(_inner(t)))
    if base.lower() in ("tuple", "tuple2"):
        return ErrorType(fallback="array<float>")  # tuple unsupported in v0.1
    if t.startswith(("typing.List", "typing.Dict", "typing.Set", "typing.Optional")):
        return parse_type_annotation(t[t.index("[") + 1:-1], is_return=is_return)

    # identifier -> user class reference
    if t.replace("_", "").isalnum() and not t[0].isdigit():
        return ClassType(t)

    return ErrorType()


# --------------------------------------------------------------------------
# small text helpers (no dependency on typing internals)
# --------------------------------------------------------------------------

def _normalize(text: str) -> str:
    t = text.strip()
    for prefix in ("typing.", "builtins.", "__main__."):
        if t.startswith(prefix):
            t = t[len(prefix):]
    return t


def _strip_optional(t: str) -> str:
    if t.startswith("Optional[") and t.endswith("]"):
        t = t[len("Optional["):-1]
    if " | " in t:
        parts = [p.strip() for p in t.split(" | ")]
        non_none = [p for p in parts if p not in ("None", "NoneType")]
        t = non_none[0] if non_none else parts[0]
    return t


def _inner(t: str) -> str:
    return t[t.index("[") + 1:t.rindex("]")]


def _split_top(t: str):
    out, depth, cur = [], 0, ""
    for ch in t:
        if ch in "[<(":
            depth += 1
        elif ch in "]>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out
