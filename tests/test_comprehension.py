"""List / dict / set comprehension lowering (v0.2)."""

from any2enforce import transpile


def test_list_comp_with_filter():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    ys: list[int] = [x * 2 for x in xs if x > 0]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "array<int> ys = {};" in text
    assert "foreach (int x : xs)" in text
    assert "if (x > 0)" in text
    assert "ys.Insert(x * 2);" in text
    assert "?" not in text


def test_list_comp_range():
    src = "def f() -> None:\n    ys: list[int] = [i for i in range(3)]\n"
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "for (int i = 0; i < 3; i++)" in text
    assert "ys.Insert(i);" in text


def test_list_comp_nested():
    src = (
        "def f(a: list[int], b: list[int]) -> None:\n"
        "    ys: list[int] = [x + y for x in a for y in b]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert text.count("foreach") == 2
    assert "ys.Insert(x + y);" in text


def test_dict_comp():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    d: dict[int, int] = {x: x * 2 for x in xs}\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "map<int, int> d = new map<int, int>();" in text
    assert "d[x] = x * 2;" in text


def test_set_comp():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    s: set[int] = {x for x in xs if x > 0}\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "set<int> s = new set<int>();" in text
    assert "s.Insert(x);" in text


def test_list_comp_return():
    src = (
        "def f(xs: list[int]) -> list[int]:\n"
        "    return [x for x in xs]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "_pyComp0" in text
    assert "return _pyComp0;" in text
    assert ".Insert(x);" in text


def test_list_comp_unannotated_assign():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    ys = [x * 2 for x in xs]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "array<int> ys = {};" in text


def test_comp_in_call_is_lifted():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    print([x for x in xs])\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "_pyLift0" in text
    assert "_pyLift0.Insert(x);" in text
    assert "Print(_pyLift0);" in text


def test_comp_nested_as_iterable_is_lifted():
    src = (
        "def f(xs: list[int]) -> None:\n"
        "    ys: list[int] = [y for y in [x for x in xs]]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert diag.errors == []
    assert "_pyLift0" in text
    assert "foreach (int y : _pyLift0)" in text
    assert "ys.Insert(y);" in text


def test_comp_tuple_unpack_errors():
    src = (
        "def f(pairs: list[int]) -> None:\n"
        "    ys: list[int] = [a for a, b in pairs]\n"
    )
    _, text, diag = transpile(src, "t.py")
    assert any(d.code == "comp-unpack" for d in diag.errors)
