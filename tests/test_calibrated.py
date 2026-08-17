"""Tests for mappings calibrated against the real Reforger scripts corpus.

ML experiment tests (mlp_forward / train_mlp / training_lab / glue) moved to
the dedicated ML repository (reforger-ml-lab) in the repo split.
"""

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


def test_map_membership_uses_contains():
    src = ("def f(m: dict[str, int], key: str) -> bool:\n"
           "    return key in m\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "return m.Contains(key);" in text


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


def test_list_append_maps_to_insert():
    src = ("def f() -> None:\n"
           "    xs: list[int] = []\n"
           "    xs.append(1)\n"
           "    xs.append(2)\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "array<int> xs = {  };" in text
    assert "xs.Insert(1);" in text
    assert "xs.Insert(2);" in text


def test_block_vars_used_after_are_hoisted():
    """Python is function-scoped, EnforceScript block-scoped: a variable
    assigned inside loops but read AFTER them is hoisted to a typed
    declaration at function scope (the loops then reuse it)."""
    src = ("def f(a: list[float], b: list[float], n: int) -> float:\n"
           "    for i in range(n):\n"
           "        z = a[i]\n"
           "        z = z + 1.0\n"
           "    for i in range(n):\n"
           "        z = b[i]\n"
           "        z = z + 2.0\n"
           "    return z\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "float z = 0.0;" in text       # hoisted typed declaration
    assert text.count("auto z = ") == 0   # loops reuse the hoisted variable
    assert "return z;" in text


def test_global_function_prefix():
    """EnforceScript has one flat namespace: --prefix applies to global
    functions (declaration and calls) but not methods or locals."""
    src = ("def helper(x: int) -> int:\n"
           "    return x + 1\n"
           "def caller(a: int) -> int:\n"
           "    return helper(a)\n"
           "class C:\n"
           "    def method(self, x: int) -> int:\n"
           "        return helper(x)\n")
    _, text, _ = transpile(src, "t.py", config={"naming": {"prefix": "M_"}})
    assert "int M_helper(int x)" in text
    assert "int M_caller(int a)" in text
    assert "return M_helper(a);" in text
    assert "M_helper(x);" in text          # call inside method also prefixed
    assert "int method(int x)" in text      # methods NOT prefixed
    assert "M_method" not in text


def test_if_else_assign_used_after_is_hoisted():
    """`best` assigned in BOTH branches and read after the if/else must be
    hoisted to a typed declaration (was: 'Can't find variable best')."""
    src = ("def f(x: int) -> int:\n"
           "    if x > 0:\n"
           "        best = x\n"
           "    else:\n"
           "        best = -x\n"
           "    return best\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == [], [d.code for d in diag.errors]
    assert "int best = 0;" in text
    assert text.count("auto best") == 0
    assert "best = x;" in text
    assert "best = -x;" in text


def test_array_field_gets_ref():
    """array/map/set fields must be `ref` (verified ANNA:
    `protected static ref array<float> s_Means;`) — was: 'not strong ref'."""
    src = ("class C:\n"
           "    def __init__(self):\n"
           "        self.items = [1, 2]\n"
           "        self.table = {\"a\": 1}\n")
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "protected ref array<int> m_items;" in text
    assert "protected ref map<string, int> m_table;" in text
