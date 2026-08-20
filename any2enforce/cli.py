"""any2enforce command line interface.

Examples:
    any2enforce examples/demo.py --out out/demo.c
    any2enforce src/ --out build/ --naming camel
    any2enforce examples/demo.py --validate --workbench-url http://127.0.0.1:12345
    any2enforce --bundle main.py --include lib/ --out merged.c
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import List

from . import __version__, transpile, transpile_bundle
from .validate.workbench import run_validation


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="any2enforce",
        description="Translate common programming languages to EnforceScript "
                    "(v0.1: Python).",
    )
    ap.add_argument("input", nargs="?",
                    help="Python source file (.py) or directory (single-file mode)")
    ap.add_argument("--out", default=None,
                    help="output file (single input) or directory (file/dir input)")
    ap.add_argument("--target", default="python", choices=["python"],
                    help="source language (v0.1: python)")
    ap.add_argument("--naming", choices=["keep", "camel"], default=None,
                    help="identifier naming policy")
    ap.add_argument("--field-prefix", default=None,
                    help="field prefix for hoisted instance attributes (default m_)")
    ap.add_argument("--prefix", default=None,
                    help="prefix for global functions (EnforceScript has one "
                         "flat namespace; avoids cross-file name collisions, "
                         "e.g. --prefix ANNA_)")
    ap.add_argument("--visibility", default=None,
                    choices=["public", "protected", "private"])
    ap.add_argument("--validate", action="store_true",
                    help="deploy to addon + run Workbench ValidateScripts")
    ap.add_argument("--workbench-url", default=None,
                    help="Workbench NET API base URL (default http://127.0.0.1:12345)")
    ap.add_argument("--addon-path", default=None,
                    help="addon root for --validate deployment")
    ap.add_argument("--report", choices=["text", "json"], default="text")
    ap.add_argument("--fail-on-error", action="store_true",
                    help="exit 1 when any diagnostic is an error (CI)")
    ap.add_argument("--version", action="version", version=f"any2enforce {__version__}")

    # Bundle mode
    ap.add_argument("--bundle", default=None, metavar="ENTRY",
                    help="bundle mode: entry .py file; resolves imports and "
                         "emits ONE .c with all dependencies")
    ap.add_argument("--include", default=[], action="append", metavar="DIR",
                    help="additional search root(s) for bundle resolution "
                         "(may be repeated)")
    return ap


def _config_from_args(args) -> dict:
    cfg: dict = {}
    if args.naming:
        cfg["naming"] = {"policy": args.naming}
    if args.field_prefix is not None:
        cfg.setdefault("naming", {})["field_prefix"] = args.field_prefix
    if args.prefix is not None:
        cfg.setdefault("naming", {})["prefix"] = args.prefix
    if args.visibility:
        cfg["visibility"] = args.visibility
    if args.workbench_url or args.addon_path:
        v = cfg.setdefault("validate", {})
        if args.workbench_url:
            v["workbench_url"] = args.workbench_url
        if args.addon_path:
            v["addon_path"] = args.addon_path
    return cfg


def _collect_inputs(input_path: pathlib.Path):
    if input_path.is_dir():
        return sorted(input_path.glob("*.py"))
    return [input_path]


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)
    any_error = False

    # --- Bundle mode ---
    if args.bundle:
        entry = args.bundle
        modules, text, diag = transpile_bundle(
            entry_py=entry,
            include_roots=args.include or None,
            config=config,
            lang=args.target,
        )

        out_path = _resolve_out(pathlib.Path(entry), args.out, bundle=True)
        out_path.write_text(text, encoding="utf-8")

        for d in diag.items:
            line = d.render_text()
            print(line, file=sys.stderr if d.level == "error" else sys.stdout)
        any_error = bool(diag.errors)

        if args.validate:
            # Validate with the first module's name (simplified for bundle)
            mod_name = modules[0].name if modules else "bundle"
            report = run_validation(config, mod_name, text)
            if "error" in report:
                print(f"validate: {report['error']}", file=sys.stderr)
            else:
                print(f"validate: compiled OK"
                      + (f" (deployed to {report.get('deployed_to')})"
                         if report.get("deployed_to") else ""))

        print(f"bundle {entry} -> {out_path} ({len(diag.errors)} error(s), "
              f"{sum(1 for d in diag.items if d.level == 'warning')} warning(s))")

        if args.fail_on_error and any_error:
            return 1
        return 0

    # --- Single-file / directory mode ---
    if not args.input:
        # In bundle mode --bundle replaces positional input
        print("any2enforce: either provide INPUT or use --bundle", file=sys.stderr)
        return 1

    inputs = _collect_inputs(pathlib.Path(args.input))

    if not inputs:
        print(f"any2enforce: no .py files found under {args.input}", file=sys.stderr)
        return 1

    for src in inputs:
        source = src.read_text(encoding="utf-8")
        mod, text, diag = transpile(source, filename=str(src), config=config,
                                    lang=args.target)

        out_path = _resolve_out(src, args.out)
        out_path.write_text(text, encoding="utf-8")

        for d in diag.items:
            line = d.render_text()
            print(line, file=sys.stderr if d.level == "error" else sys.stdout)
        any_error = any_error or bool(diag.errors)

        if args.validate:
            report = run_validation(config, mod.name, text)
            if "error" in report:
                print(f"validate: {report['error']}", file=sys.stderr)
            else:
                print(f"validate: compiled OK"
                      + (f" (deployed to {report.get('deployed_to')})"
                         if report.get("deployed_to") else ""))

        print(f"{src} -> {out_path} ({len(diag.errors)} error(s), "
              f"{sum(1 for d in diag.items if d.level == 'warning')} warning(s))")

    if args.fail_on_error and any_error:
        return 1
    return 0


def _resolve_out(src: pathlib.Path, out_arg: str | None,
                 bundle: bool = False) -> pathlib.Path:
    if out_arg is None:
        if bundle:
            return src.with_suffix(".c")
        return src.with_suffix(".c")
    out = pathlib.Path(out_arg)
    if out.suffix == ".c" or (out.suffix and not out.is_dir()):
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    out.mkdir(parents=True, exist_ok=True)
    return out / (src.stem + ".c")


if __name__ == "__main__":
    sys.exit(main())