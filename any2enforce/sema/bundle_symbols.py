"""Stage B: cross-module symbol rewiring for the bundle pipeline.

Builds a cross-module symbol table that lets the EnforceScript backend
rewrite references to functions/classes defined in *other* bundled modules.

EnforceScript compiles all scripts into one flat namespace, so a bundle's
functions must be referenced by their prefixed global name
(e.g. ``lib_vecmath_magnitude``) rather than a Python-style
``vecmath.magnitude`` or a bare imported ``helper``. Stage A only prefixed
each module's *definitions*; Stage B adds the *call-site* rewiring so a
module can actually call into its dependencies.

Two kinds of local bindings are tracked, both keyed by the importing module:
  - ``module_alias`` : a local name bound to a whole module via
    ``import a.b`` / ``import a.b as alias`` / ``from a import b`` where
    ``b`` is a module. Resolved to the target's namespace prefix so
    ``alias.fn(...)`` can become ``{target_prefix}{fn_id(fn)}(...)``.
  - ``imported_symbol`` : a local name bound to a single definition via
    ``from a import fn``. Resolved to the target's prefix + definition name
    so a bare ``fn(...)`` becomes ``{target_prefix}{fn_id(fn)}(...)``.

The ``BundleSymbolTables`` stores raw target names + the target namespace
prefix; the backend assembles the final identifier using its own policy-aware
``_fn_id`` so a single source of truth drives the name transform.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from ..diagnostics import DiagnosticSink
from ..ir import ImportStmt, Module

# local_name -> (target_qn, target_ns_prefix)
ModuleAlias = Tuple[str, str]
# local_name -> (target_qn, target_ns_prefix, raw_target_name, kind)
#   kind in {"function", "class"}
SymbolBinding = Tuple[str, str, str, str]

ModuleAliasMap = Dict[str, ModuleAlias]
SymbolMap = Dict[str, SymbolBinding]


class BundleSymbolTables:
    """Cross-module binding tables for one bundle."""

    def __init__(self) -> None:
        # module_qn -> { local_name -> (target_qn, target_ns_prefix) }
        self.module_aliases: Dict[str, ModuleAliasMap] = {}
        # module_qn -> { local_name -> binding }
        self.imported_symbols: Dict[str, SymbolMap] = {}

    def alias_for(self, module_qn: str, name: str) -> Optional[ModuleAlias]:
        return self.module_aliases.get(module_qn, {}).get(name)

    def symbol_for(self, module_qn: str, name: str) -> Optional[SymbolBinding]:
        return self.imported_symbols.get(module_qn, {}).get(name)

    def function_imports(self, module_qn: str) -> set:
        """Local names bound to functions via ``from x import f`` in *module_qn*."""
        out: set = set()
        for name, b in self.imported_symbols.get(module_qn, {}).items():
            if b[3] == "function":
                out.add(name)
        return out


def build_bundle_symbol_tables(
    modules: list[Module],
    diag: DiagnosticSink,
) -> BundleSymbolTables:
    """Build cross-module binding tables for a resolved bundle.

    Requires ``resolve_closure`` to have set each ``module.name`` to its
    qualified name and each ``module.ns_prefix``.
    """
    # qn -> ns_prefix for every module in the bundle
    ns_by_qn: Dict[str, str] = {m.name: (m.ns_prefix or "") for m in modules}
    # qn -> set of global function names defined there
    fns_by_qn: Dict[str, set] = {}
    # class name -> (qn, ) for collision detection
    class_defs: Dict[str, str] = {}

    for mod in modules:
        fns_by_qn[mod.name] = {fn.name for fn in mod.functions}
        for cls in mod.classes:
            if cls.name in class_defs and class_defs[cls.name] != mod.name:
                diag.warning(
                    "bundle-class-collision",
                    f"class '{cls.name}' is defined in both "
                    f"'{class_defs[cls.name]}' and '{mod.name}'; references "
                    "may be ambiguous in the flat EnforceScript namespace",
                )
            else:
                class_defs[cls.name] = mod.name

    # Build a re-export index: for each package `__init__`, which local names it
    # re-exports from submodules (so a consumer's `from pkg import name` can
    # follow through to the ultimate source module).
    reexports: Dict[str, Dict[str, str]] = _build_reexports(modules, ns_by_qn)

    tables = BundleSymbolTables()
    for mod in modules:
        aliases: ModuleAliasMap = {}
        symbols: SymbolMap = {}
        for imp in mod.imports:
            _bind_import(imp, mod.name, ns_by_qn, fns_by_qn, aliases, symbols,
                         reexports)
        tables.module_aliases[mod.name] = aliases
        tables.imported_symbols[mod.name] = symbols
    return tables


def _build_reexports(
    modules: list[Module], ns_by_qn: Dict[str, str]
) -> Dict[str, Dict[str, str]]:
    """Map ``package_qn -> {re_exported_local_name: source_module_qn}``."""
    reexports: Dict[str, Dict[str, str]] = {}
    for mod in modules:
        package_qn = mod.name
        for imp in mod.imports:
            if imp.level == 0 or not imp.module:
                continue
            parts = package_qn.split(".")
            up = max(0, imp.level - 1)
            base = ".".join(parts[:-up]) if up else package_qn
            source_pkg = f"{base}.{imp.module.lstrip('.')}" if base else imp.module.lstrip(".")
            if source_pkg in ns_by_qn:
                for name in imp.names:
                    reexports.setdefault(package_qn, {})[name] = source_pkg
    return reexports


def _follow_reexport(
    target_qn: str, name: str, ns_by_qn: Dict[str, str], reexports: Dict
) -> Optional[str]:
    """Resolve ``name`` imported from *target_qn* through package re-exports.

    Returns the ultimate source module qn, or *target_qn* if no re-export.
    """
    seen: set = set()
    cur = target_qn
    while cur in reexports and cur not in seen:
        seen.add(cur)
        nxt = reexports[cur].get(name)
        if not nxt:
            return cur
        cur = nxt
    return cur


def _bind_import(
    imp: ImportStmt,
    module_qn: str,
    ns_by_qn: Dict[str, str],
    fns_by_qn: Dict[str, set],
    aliases: ModuleAliasMap,
    symbols: SymbolMap,
    reexports: Dict[str, Dict[str, str]],
) -> None:
    """Bind the names an import statement introduces in *module_qn*."""
    if imp.level > 0:
        # relative import: resolve target package by walking up `level` segs
        parts = module_qn.split(".")
        if not imp.module:
            # `from . import x` against this package
            target_qn = module_qn
            for name in imp.names:
                _bind_from(target_qn, name, ns_by_qn, fns_by_qn, aliases,
                           symbols, reexports)
            return
        up = max(0, imp.level - 1)
        base = ".".join(parts[:-up]) if up else module_qn
        mod_part = imp.module.lstrip(".")
        target_qn = f"{base}.{mod_part}" if base else mod_part
        for name in imp.names:
            _bind_from(target_qn, name, ns_by_qn, fns_by_qn, aliases,
                       symbols, reexports)
        return

    mod_name = imp.module or ""

    if not mod_name:
        for name in imp.names:
            # top-level module alias if it is a known module
            if name in ns_by_qn:
                aliases[name] = (name, ns_by_qn[name])
        return

    if imp.names:
        # `from X import y` / `from X import y as z`
        for name in imp.names:
            _bind_from(mod_name, name, ns_by_qn, fns_by_qn, aliases,
                       symbols, reexports)
    else:
        # `import a.b` — bind the top-level name to the full module so that
        # dotted traversal still works.
        top = mod_name.split(".")[0]
        aliases[top] = (mod_name, _ns(mod_name, ns_by_qn))


def _bind_from(
    target_qn: str,
    local_name: str,
    ns_by_qn: Dict[str, str],
    fns_by_qn: Dict[str, set],
    aliases: ModuleAliasMap,
    symbols: SymbolMap,
    reexports: Dict[str, Dict[str, str]],
) -> None:
    """Bind a ``from TARGET import NAME`` local binding."""
    # Case 1: NAME is itself a module (e.g. `from lib import vecmath`).
    sub_qn = f"{target_qn}.{local_name}"
    if sub_qn in ns_by_qn:
        aliases[local_name] = (sub_qn, _ns(sub_qn, ns_by_qn))
        return
    # Case 2: follow package re-exports (e.g. `from pkg import helper` where
    # pkg/__init__.py re-exports helper from pkg.core2).
    src_qn = _follow_reexport(target_qn, local_name, ns_by_qn, reexports)
    if src_qn in fns_by_qn and local_name in fns_by_qn[src_qn]:
        symbols[local_name] = (src_qn, _ns(src_qn, ns_by_qn), local_name, "function")
        return
    # Case 3: NAME is a global function exported by TARGET directly.
    if local_name in fns_by_qn.get(target_qn, set()):
        symbols[local_name] = (target_qn, _ns(target_qn, ns_by_qn), local_name, "function")
        return
    # Case 4: NAME is a class exported by TARGET (bare; backend emits the plain
    # class name, consistent with non-prefixed class emission).
    symbols[local_name] = (target_qn, _ns(target_qn, ns_by_qn), local_name, "class")


def _ns(qn: str, ns_by_qn: Dict[str, str]) -> str:
    for k, v in ns_by_qn.items():
        if k == qn:
            return v
    return qn.replace(".", "_") + "_"
