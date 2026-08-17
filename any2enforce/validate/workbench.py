"""Validation loop: deploy generated .c files into an addon and compile them
with the Workbench NET API (ValidateScripts).

The endpoint protocol matches the wb_bridge used by the DSH Arma tooling:
    POST <workbench_url>/api/ValidateScripts

When Workbench is not running, every function degrades gracefully (returns a
report with an "error" entry) so the CLI never hard-fails on validation.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
from typing import Optional


def deploy(module_name: str, source_text: str, addon_path: str,
           subdir: str = "Game") -> Optional[pathlib.Path]:
    """Write source_text into <addon_path>/scripts/<subdir>/<module_name>/<module_name>.c.

    Returns the written path, or None if addon_path is not set.
    """
    if not addon_path:
        return None
    target_dir = (pathlib.Path(addon_path) / "scripts" / subdir / module_name)
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / f"{module_name}.c"
    out.write_text(source_text, encoding="utf-8")
    return out


def validate_scripts(workbench_url: str, timeout: int = 30) -> dict:
    """Ask the running Workbench to compile the addon's scripts.

    Returns a JSON report. On any connection/parse failure returns
    {"error": <message>} so callers can present a friendly notice.
    """
    url = workbench_url.rstrip("/") + "/api/ValidateScripts"
    try:
        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload) if payload else {"ok": True}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError,
            ConnectionError) as exc:
        return {"error": f"Workbench unreachable at {workbench_url}: {exc}"}


def run_validation(config: dict, module_name: str, source_text: str) -> dict:
    """deploy + validate, driven by the validate config section."""
    vcfg = config.get("validate", {})
    addon_path = vcfg.get("addon_path")
    deployed = deploy(module_name, source_text, addon_path) if vcfg.get("deploy") else None
    report = validate_scripts(vcfg.get("workbench_url", "http://127.0.0.1:12345"))
    if deployed:
        report["deployed_to"] = str(deployed)
    return report
