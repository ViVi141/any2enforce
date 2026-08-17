"""Tests for mappings calibrated against the real Reforger scripts corpus."""

from pathlib import Path

import pytest

from any2enforce import transpile

HERE = Path(__file__).parent
CALIBRATED = HERE.parent / "examples" / "calibrated.py"


def test_calibrated_golden():
    source = CALIBRATED.read_text(encoding="utf-8")
    _, text, diag = transpile(source, filename=str(CALIBRATED))
    assert diag.errors == []
    expected = (HERE / "golden" / "calibrated.c.expected").read_text(encoding="utf-8")
    assert text == expected


def test_ternary_lowered_to_if_else():
    _, text, _ = transpile("def f(a: int, b: int) -> int:\n"
                           "    return a if a > b else b\n", "t.py")
    assert "if (a > b)" in text
    assert "return a;" in text
    assert "return b;" in text
    assert "?" not in text


def test_min_max_abs_dispatch():
    _, text, _ = transpile("def f(a: int, b: float) -> None:\n"
                           "    x = min(a, a)\n"
                           "    y = max(b, b)\n"
                           "    z = abs(a)\n"
                           "    w = abs(b)\n", "t.py")
    assert "Math.MinInt" in text
    assert "Math.Max(" in text
    assert "Math.AbsInt" in text
    assert "Math.AbsFloat" in text


def test_array_and_map_literals():
    src = ("def f() -> None:\n"
           "    xs = [1, 2, 3]\n"
           "    cfg = {\"a\": 1}\n"
           "    cfg[\"b\"] = 2\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "array<int> xs = { 1, 2, 3 };" in text
    assert "map<string, int> cfg = new map<string, int>();" in text
    assert 'cfg["a"] = 1;' in text
    assert 'cfg["b"] = 2;' in text


def test_float_modulo_uses_math_mod():
    _, text, _ = transpile("def f(deg: float) -> float:\n    return deg % 360.0\n", "t.py")
    assert "Math.Mod(deg, 360.0)" in text


def test_param_default_emitted():
    _, text, diag = transpile("def f(x: int = 3) -> int:\n    return x\n", "t.py")
    assert diag.errors == []
    assert "int x = 3" in text


def test_print_variants():
    _, text, _ = transpile("def f(a: int, b: str) -> None:\n"
                           "    print(a)\n"
                           "    print(\"x\", b)\n", "t.py")
    assert "Print(a);" in text
    assert 'PrintFormat("%1 %2", "x", b);' in text


def test_membership_in_lowered_to_contains():
    src = ("def f(values: list[int], probe: int) -> bool:\n"
           "    return probe in values\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "return values.Contains(probe);" in text


def test_not_in_lowered_to_negated_contains():
    src = ("def f(values: list[int], probe: int) -> bool:\n"
           "    return probe not in values\n")
    _, text, _ = transpile(src, "t.py")
    assert "return !values.Contains(probe);" in text


def test_inline_array_literal_as_call_argument():
    src = ("def total(xs: list[int]) -> int:\n"
           "    return xs[0]\n"
           "def f() -> None:\n"
           "    print(total([1, 2, 3]))\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "Print(total({ 1, 2, 3 }));" in text


def test_super_method_call_maps_to_super_dot():
    src = ("class Base:\n"
           "    def greet(self) -> str:\n"
           "        return \"hi\"\n"
           "class Derived(Base):\n"
           "    def greet(self) -> str:\n"
           "        return super().greet()\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "return super.greet();" in text


def test_super_init_dropped_with_warning():
    src = ("class Base:\n"
           "    def __init__(self, name: str):\n"
           "        self.name = name\n"
           "class Derived(Base):\n"
           "    def __init__(self, name: str):\n"
           "        super().__init__(name)\n"
           "        self.extra = 1\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert any(d.code == "super-init-dropped" for d in diag.items)
    assert "implicit base ctor" in text  # marker comment present


def test_ctor_forward_missing_param_is_error():
    src = ("class Base:\n"
           "    def __init__(self, name: str, hp: int):\n"
           "        self.name = name\n"
           "        self.hp = hp\n"
           "class Derived(Base):\n"
           "    def __init__(self):\n"
           "        pass\n")
    _, _, diag = transpile(src, "t.py")
    assert any(d.code == "ctor-forward" for d in diag.errors), \
        [d.code for d in diag.errors]


def test_ctor_forward_ok_when_params_declared():
    src = ("class Base:\n"
           "    def __init__(self, name: str):\n"
           "        self.name = name\n"
           "class Derived(Base):\n"
           "    def __init__(self, name: str):\n"
           "        self.tag = 1\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "void Derived(string name)" in text
