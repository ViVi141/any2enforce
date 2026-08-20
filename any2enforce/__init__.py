"""any2enforce: translate common programming languages to EnforceScript.

Current frontend: Python (stdlib `ast`). Pipeline:
    PythonFrontend -> IR -> Analyzer (sema) -> EnforceBackend -> .c text

Single-file: transpile() runs the full pipeline.
Bundle: transpile_bundle() resolves multi-file dependencies, then emits one .c.
"""

from __future__ import annotations

from .backends.enforce import EnforceBackend
from .diagnostics import DiagnosticSink
from .frontends.python_frontend import PythonFrontend
from .ir import Module
from .sema.analyze import Analyzer
from .sema.lift_comps import lift_comprehensions

__version__ = "0.1.0"

DEFAULT_CONFIG: dict = {
    # prefix: applied to global functions only (EnforceScript has one flat
    # namespace — all scripts compile together, so module-level function names
    # must be unique project-wide; ANNA uses an ANNA_ prefix)
    "naming": {"policy": "keep", "field_prefix": "m_", "prefix": ""},
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


# ------------------------------------------------------------------
# Single-module parsing (frontend + lift, no sema)
# ------------------------------------------------------------------

def parse_module(source: str, filename: str = "<string>",
                 diag: DiagnosticSink | None = None) -> Module:
    """Parse a single Python source file -> IR.Module (frontend + lift only).

    This is the shared entry used by both ``transpile()`` and
    ``transpile_bundle()``; it stops before semantic analysis so the bundle
    path can apply per-module analysis later.
    """
    if diag is None:
        diag = DiagnosticSink()
    mod = PythonFrontend(diag).parse(source, filename)
    lift_comprehensions(mod)
    return mod


# ------------------------------------------------------------------
# Single-file pipeline
# ------------------------------------------------------------------

def transpile(source: str, filename: str = "<string>", config: dict | None = None,
              lang: str = "python"):
    """Full pipeline for a **single** source file.

    Returns ``(module, enforcescript_text, diagnostics)``.
    """
    config = _deep_merge(DEFAULT_CONFIG, config or {})
    diag = DiagnosticSink()
    if lang != "python":
        diag.error(
            "frontend",
            f"frontend for '{lang}' is not implemented yet (v0.1 ships python only)",
        )
    mod = parse_module(source, filename, diag)
    Analyzer(diag, config).run(mod)
    text = EnforceBackend(config, diag).emit(mod)
    return mod, text, diag


# ------------------------------------------------------------------
# Bundle pipeline
# ------------------------------------------------------------------

def transpile_bundle(entry_py: str,
                     include_roots: list[str] | None = None,
                     config: dict | None = None,
                     lang: str = "python") -> tuple[list[Module], str, DiagnosticSink]:
    """Resolve a multi-file Python project, emit a **single merged** .c file.

    Each module's global function names are prefixed with its namespace prefix
    (e.g. module ``a.b.c`` -> prefix ``a_b_c_``) to avoid collisions in the
    flat EnforceScript namespace.

    Returns ``(modules, merged_c_text, diagnostics)``.
    """
    from .bundle.resolver import Resolver

    config = _deep_merge(DEFAULT_CONFIG, config or {})
    diag = DiagnosticSink()

    if lang != "python":
        diag.error(
            "frontend",
            f"frontend for '{lang}' is not implemented yet (v0.1 ships python only)",
        )
        return [], "", diag

    # 1. Resolve dependency closure
    resolver = Resolver(diag)
    modules = resolver.resolve_closure(entry_py, include_roots)

    if not modules and not diag.errors:
        diag.error("bundle-empty", f"no modules resolved from {entry_py}")
        return [], "", diag

    # 2. Analyse + emit each module, collect pieces
    #    Build cross-module symbol tables (Stage B) so call sites can rewrite
    #    module-alias / from-import references to the true global names.
    from .sema.bundle_symbols import build_bundle_symbol_tables

    tables = build_bundle_symbol_tables(modules, diag)

    pieces: list[str] = []
    source_list: list[str] = []

    for mod in modules:
        source_list.append(mod.name)
        # Names `from x import f` pulls into this module's scope (Stage B).
        known = _imported_fn_names(tables, mod.name)
        Analyzer(diag, config, known_imports=known).run(mod)

        # Let the backend know about the module's namespace prefix and the
        # cross-module symbol tables (for call-site rewiring).
        be = EnforceBackend(config, diag)
        be.set_bundle_tables(tables, mod.name)
        piece = be.emit(mod)
        pieces.append(piece)

    # 3. Assemble merged output
    header = _bundle_header(source_list)
    merged = header + "\n".join(pieces)
    return modules, merged, diag


def _imported_fn_names(tables, module_qn: str) -> set:
    return tables.function_imports(module_qn)


def _bundle_header(source_modules: list[str]) -> str:
    lines = [
        "// Generated by any2enforce -- DO NOT EDIT",
        "// Bundle: merged from:",
    ]
    for sm in source_modules:
        lines.append(f"//   {sm}.py")
    lines.append("")
    return "\n".join(lines) + "\n"