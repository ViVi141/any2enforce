"""Unit tests for the annotation -> IR type parser."""

from any2enforce.ir import ArrayType, ClassType, MapType, SetType, STRING, INT, FLOAT
from any2enforce.sema.types import parse_type_annotation


def test_scalars():
    assert parse_type_annotation("int").render() == "int"
    assert parse_type_annotation("float").render() == "float"
    assert parse_type_annotation("bool").render() == "bool"
    assert parse_type_annotation("str").render() == "string"


def test_generics():
    t = parse_type_annotation("list[int]")
    assert isinstance(t, ArrayType) and t.elem is INT
    t = parse_type_annotation("dict[str, float]")
    assert isinstance(t, MapType) and t.k is STRING and t.v is FLOAT
    t = parse_type_annotation("set[int]")
    assert isinstance(t, SetType)


def test_optional_and_unions():
    assert parse_type_annotation("Optional[int]").render() == "int"
    assert parse_type_annotation("int | None").render() == "int"


def test_typing_module_prefixes():
    assert parse_type_annotation("typing.List[str]").render() == "array<string>"
    assert parse_type_annotation("builtins.int").render() == "int"


def test_user_classes():
    t = parse_type_annotation("Player")
    assert isinstance(t, ClassType) and t.name == "Player"


def test_none_return_is_void():
    from any2enforce.ir import VOID
    assert parse_type_annotation("None", is_return=True) is VOID
