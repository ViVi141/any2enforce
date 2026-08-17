"""any2enforce: translate common programming languages to EnforceScript.

Current frontend: Python (stdlib `ast`). Pipeline:
    PythonFrontend -> IR -> Analyzer (sema) -> EnforceBackend -> .c text
"""

from __future__ import annotations

from .backends.enforce import EnforceBackend
from .diagnostics import DiagnosticSink
from .frontends.python_frontend import PythonFrontend
from .ir import Module
from .sema.analyze import Analyzer

__version__ = "0.1.0"

DEFAULT_CONFIG: dict = {
    "naming": {"policy": "keep", "field_prefix": "m_"},
    "types": {"untyped_param_fallback": "float"},
    "visibility": "protected",
    "validate": {
        "workbench_url": "http://127.0.0.1:12345",
        "addon_path": None,
        "deploy": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def transpile(source: str, filename: str = "<string>", config: dict | None = None,
              lang: str = "python"):
    """Full pipeline. Returns (module, enforcescript_text, diagnostics)."""
    config = _deep_merge(DEFAULT_CONFIG, config or {})
    diag = DiagnosticSink()
    if lang != "python":
        diag.error(
            "frontend",
            f"frontend for '{lang}' is not implemented yet (v0.1 ships python only)",
        )
    mod = PythonFrontend(diag).parse(source, filename)
    Analyzer(diag, config).run(mod)
    text = EnforceBackend(config, diag).emit(mod)
    return mod, text, diag
