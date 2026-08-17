"""Structural tests for the Python frontend + sema pass."""

from any2enforce import transpile
from any2enforce.diagnostics import DiagnosticSink
from any2enforce.frontends.python_frontend import PythonFrontend
from any2enforce.ir import (
    ArrayType, AssignStmt, ClassType, FLOAT, INT, MapType, NameExpr, STRING,
)
from any2enforce.sema.analyze import Analyzer


def parse(source, name="x.py"):
    diag = DiagnosticSink()
    mod = PythonFrontend(diag).parse(source, name)
    Analyzer(diag, {}).run(mod)
    return mod, diag


def test_module_structure():
    src = "def f(a: int) -> int:\n    return a\n"
    mod, diag = parse(src)
    assert diag.errors == []
    assert [fn.name for fn in mod.functions] == ["f"]
    assert mod.functions[0].params[0].type is INT


def test_annotation_mapping():
    src = ("def f(xs: list[int], m: dict[str, float]) -> None:\n"
           "    pass\n")
    mod, diag = parse(src)
    p = mod.functions[0].params
    assert isinstance(p[0].type, ArrayType)
    assert p[0].type.elem is INT
    assert isinstance(p[1].type, MapType)
    assert p[1].type.k is STRING
    assert p[1].type.v is FLOAT


def test_field_hoisting():
    src = ("class A:\n"
           "    def __init__(self, x: int):\n"
           "        self.value = x\n"
           "        self.tag = \"t\"\n"
           "    def bump(self) -> None:\n"
           "        self.value += 1\n")
    mod, diag = parse(src)
    assert diag.errors == []
    cls = mod.classes[0]
    names = {f.name: f.type for f in cls.fields}
    assert names["value"] is INT
    assert names["tag"] is STRING
    ctor = [m for m in cls.methods if m.is_constructor][0]
    assert [p.name for p in ctor.params] == ["x"]


def test_untyped_param_is_error_with_fallback():
    src = "def f(x) -> int:\n    return x\n"
    mod, diag = parse(src)
    codes = {d.code for d in diag.errors}
    assert "untyped-param" in codes
    assert mod.functions[0].params[0].type.render() == "float"  # config fallback


def test_class_ref_annotation():
    src = "def make() -> Player:\n    return None\n"
    mod, diag = parse(src)
    rt = mod.functions[0].return_type
    assert isinstance(rt, ClassType) and rt.name == "Player"


def test_dict_literal_assignment_is_map():
    src = "def f() -> None:\n    cfg = {\"a\": 1}\n"
    mod, diag = parse(src)
    assert diag.errors == []
    body = mod.functions[0].body
    assert isinstance(body[0], AssignStmt)
    assert isinstance(body[0].value.type, MapType)
