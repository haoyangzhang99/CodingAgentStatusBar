"""Diagnostics commands using ruff.

Provides lint and check commands for Python code analysis.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class Diagnostic:
    """A diagnostic message (error, warning, etc.)."""

    path: str
    line: int
    column: int
    code: str
    message: str
    severity: str = "error"
    fix_available: bool = False

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "fix_available": self.fix_available,
        }


def _run_ruff(args: list[str], path: str) -> tuple[str, int]:
    """Run ruff with the given arguments.

    Returns:
        Tuple of (stdout, return_code)
    """
    cmd = ["uv", "run", "ruff", *args, path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr, result.returncode


def lint(path: str, *, as_json: bool = False, fix: bool = False) -> str | list[dict]:
    """Run ruff lint on the specified path.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text
        fix: Apply automatic fixes

    Returns:
        Formatted string or list of diagnostic dicts
    """
    args = ["check", "--output-format=json"]
    if fix:
        args.append("--fix")

    output, code = _run_ruff(args, path)

    if as_json:
        try:
            # Ruff outputs JSON array
            issues = json.loads(output) if output.strip() else []
            diagnostics = []
            for issue in issues:
                diag = Diagnostic(
                    path=issue.get("filename", ""),
                    line=issue.get("location", {}).get("row", 0),
                    column=issue.get("location", {}).get("column", 0),
                    code=issue.get("code", ""),
                    message=issue.get("message", ""),
                    severity="error"
                    if issue.get("code", "").startswith("E")
                    else "warning",
                    fix_available=issue.get("fix") is not None,
                )
                diagnostics.append(diag.to_dict())
            return diagnostics
        except json.JSONDecodeError:
            return [{"error": output}]

    # Text output - run without JSON format
    args = ["check"]
    if fix:
        args.append("--fix")
    output, code = _run_ruff(args, path)

    if code == 0:
        return f"No lint issues found in {path}"

    return f"Lint results for {path}:\n{output}"


def check(path: str, *, as_json: bool = False) -> str | dict:
    """Run ruff format check on the specified path.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or dict with check results
    """
    # Check formatting
    args = ["format", "--check", "--diff"]
    output, code = _run_ruff(args, path)

    result = {
        "path": path,
        "formatted": code == 0,
        "diff": output if code != 0 else "",
    }

    if as_json:
        return result

    if code == 0:
        return f"Format check passed for {path}"

    return f"Format issues in {path}:\n{output}"
