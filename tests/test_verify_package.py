"""Static consistency checks for the copy-ready EnforceScript verification
package (verify/). We cannot compile EnforceScript here, but we can enforce
the invariants that keep the package compiling:

  1. Every `X.Check()` call in VerifyEntry.c resolves to a `class X` declared
     in the package with a `static void Check()` method.
  2. Every file's primary class name matches its file name (EnforceScript
     convention; catches rename/typo drift like C01_BaseCtorImplicit).
  3. Probes are self-contained (their classes match their file names).
"""

import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
VERIFY = HERE.parent / "verify"
RUNNABLE = VERIFY / "Any2EnforceVerify" / "scripts" / "Game" / "Any2EnforceVerify"
PROBES = VERIFY / "Any2EnforceProbes" / "scripts" / "Game" / "Any2EnforceProbes"

CLASS_RE = re.compile(r"^(?:modded )?class\s+(\w+)\b", re.MULTILINE)
STATIC_CHECK_RE = re.compile(r"static\s+void\s+Check\s*\(")


def _classes(text: str) -> set:
    return set(CLASS_RE.findall(text))


def test_runnable_files_declare_matching_class():
    for f in RUNNABLE.glob("*.c"):
        text = f.read_text(encoding="utf-8")
        classes = _classes(text)
        # VerifyEntry.c and RunOnGameStart.c (modded) are exempt from the
        # file-name == class-name rule, but still must have a class.
        assert classes, f"{f.name}: no class declaration found"
        if f.name not in ("VerifyEntry.c", "RunOnGameStart.c"):
            expected = f.stem
            assert expected in classes, \
                f"{f.name}: expected class '{expected}' (got {sorted(classes)})"


def test_every_check_call_resolves():
    entry = (RUNNABLE / "VerifyEntry.c").read_text(encoding="utf-8")
    calls = re.findall(r"^\s*(\w+)\.Check\(\)", entry, re.MULTILINE)
    assert calls, "no Check() calls found in VerifyEntry.c"

    package = ""
    for f in RUNNABLE.glob("*.c"):
        package += f.read_text(encoding="utf-8") + "\n"
    declared = _classes(package)

    for name in calls:
        assert name in declared, f"VerifyEntry calls {name}.Check() but no class '{name}' exists"
        # the calling class must define static void Check()
        m = re.search(rf"class {re.escape(name)}\b.*?static\s+void\s+Check\s*\(", package, re.DOTALL)
        assert m, f"class '{name}' has no static void Check()"


def test_probes_declare_matching_class():
    for f in PROBES.glob("*.c"):
        text = f.read_text(encoding="utf-8")
        classes = _classes(text)
        assert classes, f"{f.name}: no class declaration found"
        assert f.stem in classes, \
            f"{f.name}: expected class '{f.stem}' (got {sorted(classes)})"


@pytest.mark.parametrize("stem,literals", [
    ("P05_FloatLiteralExponent", ["1e+30", "1.0e30"]),
    ("P08_StringEscapes", ["\\u0041", "\\x41"]),
])
def test_probe_candidates_have_expected_forms(stem, literals):
    """The multi-candidate probes must still contain their documented candidates."""
    text = (PROBES / f"{stem}.c").read_text(encoding="utf-8")
    for lit in literals:
        assert lit in text, f"{stem}.c: missing candidate literal {lit!r}"
