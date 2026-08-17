"""Golden tests: transpiled output must match the checked-in expected files
byte-for-byte. Regenerate with: python -m any2enforce.cli examples/demo.py
"""

from pathlib import Path

import pytest

from any2enforce import transpile

HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
DEMO = HERE.parent / "examples" / "demo.py"


def test_demo_golden():
    source = DEMO.read_text(encoding="utf-8")
    _, text, diag = transpile(source, filename=str(DEMO))
    assert diag.errors == [], "\n".join(d.render_text() for d in diag.errors)
    expected = (GOLDEN / "demo.c.expected").read_text(encoding="utf-8")
    assert text == expected


@pytest.mark.parametrize("policy,prefix", [
    ("keep", "m_"),
    ("camel", "field_"),
])
def test_naming_policies_are_deterministic(policy, prefix):
    source = "def foo_bar(a: int) -> int:\n    return a + 1\n"
    _, text1, _ = transpile(source, filename="x.py",
                            config={"naming": {"policy": policy,
                                               "field_prefix": prefix}})
    _, text2, _ = transpile(source, filename="x.py",
                            config={"naming": {"policy": policy,
                                               "field_prefix": prefix}})
    assert text1 == text2
