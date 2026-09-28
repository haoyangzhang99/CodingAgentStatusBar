"""Combined report generation.

Generates a comprehensive code quality report combining all analyses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .diagnostics import lint
from .metrics import complexity, maintainability
from .deadcode import detect_dead_code


@dataclass
class Report:
    """Combined code quality report."""

    path: str
    timestamp: str
    lint_issues: list[dict] = field(default_factory=list)
    complexity_issues: list[dict] = field(default_factory=list)
    maintainability: list[dict] = field(default_factory=list)
    dead_code: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "timestamp": self.timestamp,
            "summary": {
                "lint_issues": len(self.lint_issues),
                "high_complexity": len(
                    [c for c in self.complexity_issues if c.get("rank", "A") >= "C"]
                ),
                "low_maintainability": len(
                    [m for m in self.maintainability if m.get("rank", "A") >= "B"]
                ),
                "dead_code": len(self.dead_code),
            },
            "lint": self.lint_issues,
            "complexity": self.complexity_issues,
            "maintainability": self.maintainability,
            "dead_code": self.dead_code,
        }


def generate_report(
    path: str, *, as_json: bool = False, verbose: bool = False
) -> str | dict:
    """Generate a comprehensive code quality report.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text
        verbose: Include all details

    Returns:
        Formatted string or dict with full report
    """
    timestamp = datetime.now().isoformat()

    # Collect all analyses
    lint_result = lint(path, as_json=True)
    lint_issues = lint_result if isinstance(lint_result, list) else []

    complexity_result = complexity(path, as_json=True, min_rank="A" if verbose else "C")
    complexity_issues = complexity_result if isinstance(complexity_result, list) else []

    maintainability_result = maintainability(path, as_json=True)
    maintainability_data = (
        maintainability_result if isinstance(maintainability_result, list) else []
    )

    deadcode_result = detect_dead_code(path, as_json=True)
    dead_code = deadcode_result if isinstance(deadcode_result, list) else []

    report = Report(
        path=path,
        timestamp=timestamp,
        lint_issues=lint_issues,
        complexity_issues=complexity_issues,
        maintainability=maintainability_data,
        dead_code=dead_code,
    )

    if as_json:
        return report.to_dict()

    # Generate text report
    lines = ["=" * 60]
    lines.append("CODE QUALITY REPORT")
    lines.append(f"Path: {path}")
    lines.append(f"Generated: {timestamp}")
    lines.append("=" * 60)

    # Summary
    summary = report.to_dict()["summary"]
    lines.append("")
    lines.append("SUMMARY")
    lines.append("-" * 30)
    lines.append(f"  Lint issues:          {summary['lint_issues']}")
    lines.append(f"  High complexity (C+): {summary['high_complexity']}")
    lines.append(f"  Low maintainability:  {summary['low_maintainability']}")
    lines.append(f"  Dead code items:      {summary['dead_code']}")

    # Lint issues
    if lint_issues:
        lines.append("")
        lines.append("LINT ISSUES")
        lines.append("-" * 30)
        for issue in lint_issues[:10]:  # Limit to first 10
            if "error" not in issue:
                lines.append(
                    f"  {issue.get('path', '')}:{issue.get('line', 0)} "
                    f"[{issue.get('code', '')}] {issue.get('message', '')}"
                )
        if len(lint_issues) > 10:
            lines.append(f"  ... and {len(lint_issues) - 10} more")

    # Complexity issues
    high_complexity = [c for c in complexity_issues if c.get("rank", "A") >= "C"]
    if high_complexity or verbose:
        lines.append("")
        lines.append("COMPLEXITY ISSUES")
        lines.append("-" * 30)
        items_to_show = complexity_issues if verbose else high_complexity
        for item in items_to_show[:10]:
            if "error" not in item:
                lines.append(
                    f"  {item.get('rank', '?')} {item.get('name', '')} "
                    f"({item.get('type', '')}) - complexity: {item.get('complexity', 0)}"
                )
        if len(items_to_show) > 10:
            lines.append(f"  ... and {len(items_to_show) - 10} more")

    # Maintainability
    low_mi = [m for m in maintainability_data if m.get("rank", "A") >= "B"]
    if low_mi or verbose:
        lines.append("")
        lines.append("MAINTAINABILITY")
        lines.append("-" * 30)
        items_to_show = maintainability_data if verbose else low_mi
        for item in items_to_show[:10]:
            if "error" not in item:
                lines.append(
                    f"  {item.get('rank', '?')} MI={item.get('mi', 0):.1f} - {item.get('path', '')}"
                )
        if len(items_to_show) > 10:
            lines.append(f"  ... and {len(items_to_show) - 10} more")

    # Dead code
    if dead_code:
        lines.append("")
        lines.append("DEAD CODE")
        lines.append("-" * 30)
        for item in dead_code[:10]:
            if "error" not in item:
                lines.append(
                    f"  {item.get('name', '')} ({item.get('type', '')}) "
                    f"at {item.get('path', '')}:{item.get('line', 0)}"
                )
        if len(dead_code) > 10:
            lines.append(f"  ... and {len(dead_code) - 10} more")

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
