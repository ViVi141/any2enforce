"""Dependency resolution for multi-file Python projects.

Given a .py entry file, follows import statements to find the transitive
closure of source modules, resolves qualified names against include paths
and the entry directory, detects cycles, and returns modules in dependency
order with per-module namespace prefixes.
"""

from __future__ import annotations

import pathlib
from typing import Dict, List, Optional, Set, Tuple

from ..diagnostics import DiagnosticSink
from ..ir import ImportStmt, Module


def qn_to_ns_prefix(qualified_name: str) -> str:
    """Convert a qualified module name into a namespace prefix.

    ``a.b.c`` -> ``a_b_c_``
    """
    return qualified_name.replace(".", "_") + "_"


class Resolver:
    """Resolve Python import dependencies to a closure of IR modules."""

    def __init__(self, diag: DiagnosticSink) -> None:
        self.diag = diag
        self._resolved: Dict[str, pathlib.Path] = {}  # qualified_name -> file path
        self._modules: Dict[str, Module] = {}          # qualified_name -> parsed module

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    def resolve_closure(
        self,
        entry_path: str,
        include_roots: Optional[List[str]] = None,
    ) -> List[Module]:
        """Find the transitive closure of modules reachable from *entry_path*.

        *include_roots* — optional list of directories to search for modules
        (in addition to the entry file's own directory).

        Returns modules in **topological (dependency-before-dependents)** order.
        Each module has its ``ns_prefix`` set (e.g. ``module`` ``a.b.c`` ->
        ``ns_prefix`` ``a_b_c_``).

        Diagnostics are emitted on *self.diag*::

            bundle-cycle             import cycle detected
            bundle-unresolved-import cannot resolve import statement
            bundle-not-found         entry file missing
        """
        entry = pathlib.Path(entry_path).resolve(strict=False)
        if not entry.exists():
            self.diag.error(
                "bundle-not-found",
                f"bundle entry file not found: {entry_path}",
            )
            return []

        roots: List[pathlib.Path] = [entry.parent.resolve()]
        if include_roots:
            for r in include_roots:
                rp = pathlib.Path(r).resolve(strict=False)
                if rp.is_dir():
                    roots.append(rp)
                else:
                    self.diag.warning(
                        "bundle-include-root",
                        f"include root is not a directory: {r}",
                    )

        # DFS with three-colour marking for cycle detection.
        # WHITE=unvisited, GRAY=on current stack, BLACK=done
        colours: Dict[str, str] = {}
        order: List[str] = []  # topological (leaves-first)

        def visit(qn: str, file_path: pathlib.Path) -> None:
            if qn in colours:
                if colours[qn] == "black":
                    return
                if colours[qn] == "gray":
                    self.diag.error(
                        "bundle-cycle",
                        f"import cycle detected involving module '{qn}'",
                    )
                    return

            colours[qn] = "gray"
            self._resolved[qn] = file_path

            source = file_path.read_text(encoding="utf-8")
            mod = self._parse_module(qn, source, str(file_path))
            if mod is None:
                colours[qn] = "black"
                return

            self._modules[qn] = mod

            for imp in mod.imports:
                results = self._resolve_import_multi(imp, qn, roots)
                if not results:
                    self.diag.error(
                        "bundle-unresolved-import",
                        f"cannot resolve import '{imp_repr(imp)}' from "
                        f"module '{qn}'",
                    )
                    continue
                for dep_qn, dep_path in results:
                    visit(dep_qn, dep_path)

            colours[qn] = "black"
            order.append(qn)

        # Determine the entry module's qualified name
        entry_qn = self._path_to_qn(entry, roots)
        if entry_qn is None:
            self.diag.error(
                "bundle-resolve",
                f"cannot determine qualified name for entry {entry}",
            )
            return []

        visit(entry_qn, entry)

        # Build result in topological order (dependencies first)
        result: List[Module] = []
        seen: Set[str] = set()
        for qn in order:
            if qn in self._modules and qn not in seen:
                seen.add(qn)
                mod = self._modules[qn]
                mod.ns_prefix = qn_to_ns_prefix(qn)
                result.append(mod)

        return result

    # ------------------------------------------------------------------
    # Qualified name from filesystem path
    # ------------------------------------------------------------------

    @staticmethod
    def _path_to_qn(
        file_path: pathlib.Path, roots: List[pathlib.Path]
    ) -> Optional[str]:
        """Convert a file path to its Python qualified module name."""
        for root in roots:
            try:
                rel = file_path.relative_to(root)
            except ValueError:
                continue
            parts = list(rel.parts)
            if not parts:
                continue
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                if not parts[-1].endswith(".py"):
                    continue
                parts[-1] = parts[-1][:-3]
            if parts:
                return ".".join(parts)
        # Fallback: just use stem
        return file_path.stem

    # ------------------------------------------------------------------
    # Parse a single module (frontend + lift)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_module(qn: str, source: str, filename: str) -> Optional[Module]:
        from ..frontends.python_frontend import PythonFrontend
        from ..sema.lift_comps import lift_comprehensions

        diag = DiagnosticSink()
        mod = PythonFrontend(diag).parse(source, filename)
        mod.name = qn
        lift_comprehensions(mod)
        return mod

    # ------------------------------------------------------------------
    # Resolve a single ImportStmt to list of (qualified_name, file_path)
    # ------------------------------------------------------------------

    def _resolve_import_multi(
        self,
        imp: ImportStmt,
        importing_qn: str,
        roots: List[pathlib.Path],
    ) -> List[Tuple[str, pathlib.Path]]:
        """Resolve one import statement to zero or more (qn, path) pairs.

        Most imports produce a single result, but ``from pkg import sub``
        may return both the package (``pkg/__init__.py``) and the submodule
        (``pkg/sub.py``) when both exist.
        """
        # --- Relative imports ---
        if imp.level > 0:
            result = self._resolve_relative(imp, importing_qn, roots)
            return [result] if result else []

        mod_name = imp.module

        if not mod_name:
            # ``from . import name`` with level=0 is actually a relative import
            # but the frontend may have set level=0 with an empty module when
            # module was None.  Handle as absolute name lookup for each name.
            results: List[Tuple[str, pathlib.Path]] = []
            for name in imp.names:
                found = self._find_module(name, roots)
                if found:
                    results.append(found)
            return results

        # --- ``import pkg.sub``  OR  ``from pkg import sub`` ---

        # For ``from pkg import sub`` we need:
        #   1. module "pkg" itself (if it resolves to a package/__init__.py)
        #   2. sub-module "pkg.sub" (pkg/sub.py or pkg/sub/__init__.py)
        #   3. for each name in names, try as a sub-qualified module

        results: List[Tuple[str, pathlib.Path]] = []

        # Try the main module name
        main = self._find_module(mod_name, roots)
        if main:
            results.append(main)

        # For each name, try as a sub-module of mod_name
        for name in imp.names:
            sub_qn = f"{mod_name}.{name}"
            sub = self._find_module(sub_qn, roots)
            if sub:
                results.append(sub)

        return results

    # ------------------------------------------------------------------
    # Relative imports  (``from .`` / ``from ..mod``)
    # ------------------------------------------------------------------

    def _resolve_relative(
        self,
        imp: ImportStmt,
        importing_qn: str,
        roots: List[pathlib.Path],
    ) -> Optional[Tuple[str, pathlib.Path]]:
        level = imp.level
        importing_parts = importing_qn.split(".")

        if level > len(importing_parts):
            return None  # beyond top-level

        mod_name = imp.module.lstrip(".")  # strip leading dots

        if mod_name:
            # ``from ..mod import x`` -> parent.mod
            parent = ".".join(importing_parts[:-level]) if level > 0 else ""
            qn = f"{parent}.{mod_name}" if parent else mod_name
            return self._find_module(qn, roots)

        # ``from . import x`` where x is in imp.names
        if not imp.names:
            return None
        parent = ".".join(importing_parts[:-level]) if level > 0 else ""
        qn = f"{parent}.{imp.names[0]}" if parent else imp.names[0]
        return self._find_module(qn, roots)

    # ------------------------------------------------------------------
    # Filesystem lookup for a qualified name
    # ------------------------------------------------------------------

    def _find_module(
        self,
        qualified_name: str,
        roots: List[pathlib.Path],
    ) -> Optional[Tuple[str, pathlib.Path]]:
        """Look up a qualified module name in the search roots.

        Checks (in order):
          1. ``<root>/<parts>/__init__.py``  (package)
          2. ``<root>/<parts>.py``           (module)

        Returns ``(qualified_name, path)`` or ``None``.
        """
        parts = qualified_name.split(".")

        for root in roots:
            # Try package
            pkg_path = root.joinpath(*parts) / "__init__.py"
            if pkg_path.exists():
                return (qualified_name, pkg_path)

            # Try module
            mod_path = root.joinpath(*parts).with_suffix(".py")
            if mod_path.exists():
                return (qualified_name, mod_path)

        return None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def imp_repr(imp: ImportStmt) -> str:
    """Human-readable representation of an import statement."""
    if imp.level > 0:
        prefix = "." * imp.level
        mod = imp.module.lstrip(".") if imp.module else ""
        full = f"{prefix}{mod}" if mod else prefix
    else:
        full = imp.module

    if imp.names:
        return f"from {full} import {', '.join(imp.names)}"
    return f"import {full}"