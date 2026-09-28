"""Metrics commands using radon.

Provides complexity and maintainability analysis for Python code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ComplexityResult:
    """Cyclomatic complexity result for a code block."""

    name: str
    type: str  # function, method, class
    line: int
    complexity: int
    rank: str  # A, B, C, D, E, F
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "line": self.line,
            "complexity": self.complexity,
            "rank": self.rank,
            "path": self.path,
        }


@dataclass
class MaintainabilityResult:
    """Maintainability index result for a file."""

    path: str
    mi: float  # Maintainability Index (0-100)
    rank: str  # A, B, C

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "mi": round(self.mi, 2),
            "rank": self.rank,
        }


def _get_python_files(path: str) -> list[Path]:
    """Get all Python files in a path."""
    p = Path(path)
    if p.is_file():
        return [p] if p.suffix == ".py" else []
    return list(p.rglob("*.py"))


def complexity(
    path: str, *, as_json: bool = False, min_rank: str = "A"
) -> str | list[dict]:
    """Analyze cyclomatic complexity of Python code.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text
        min_rank: Minimum rank to report (A=all, C=problematic, F=critical)

    Returns:
        Formatted string or list of complexity dicts
    """
    try:
        from radon.complexity import cc_visit, cc_rank

        files = _get_python_files(path)
        if not files:
            if as_json:
                return []
            return f"No Python files found in {path}"

        results = []
        for file_path in files:
            try:
                source = file_path.read_text()
                blocks = cc_visit(source)

                for block in blocks:
                    rank = cc_rank(block.complexity)
                    # Filter by minimum rank
                    if min_rank != "A" and rank < min_rank:
                        continue

                    result = ComplexityResult(
                        name=block.name,
                        type=block.letter,  # F=function, M=method, C=class
                        line=block.lineno,
                        complexity=block.complexity,
                        rank=rank,
                        path=str(file_path),
                    )
                    results.append(result)

            except SyntaxError:
                continue

        if as_json:
            return [r.to_dict() for r in results]

        if not results:
            return f"No complexity issues found in {path}"

        # Group by file
        by_file: dict[str, list[ComplexityResult]] = {}
        for r in results:
            by_file.setdefault(r.path, []).append(r)

        lines = [f"Complexity Analysis ({len(results)} blocks):"]
        for file_path, file_results in sorted(by_file.items()):
            lines.append(f"\n{file_path}:")
            for r in sorted(file_results, key=lambda x: -x.complexity):
                type_name = {"F": "function", "M": "method", "C": "class"}.get(
                    r.type, r.type
                )
                lines.append(
                    f"  {r.rank} {r.name} ({type_name}) - "
                    f"complexity: {r.complexity}, line: {r.line}"
                )

        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"


def maintainability(path: str, *, as_json: bool = False) -> str | list[dict]:
    """Analyze maintainability index of Python code.

    Args:
        path: Path to file or directory
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or list of maintainability dicts
    """
    try:
        from radon.metrics import mi_visit, mi_rank

        files = _get_python_files(path)
        if not files:
            if as_json:
                return []
            return f"No Python files found in {path}"

        results = []
        for file_path in files:
            try:
                source = file_path.read_text()
                mi = mi_visit(source, multi=True)
                rank = mi_rank(mi)

                result = MaintainabilityResult(
                    path=str(file_path),
                    mi=mi,
                    rank=rank,
                )
                results.append(result)

            except SyntaxError:
                continue

        if as_json:
            return [r.to_dict() for r in results]

        if not results:
            return f"No Python files analyzed in {path}"

        # Sort by MI (lowest first = needs attention)
        results.sort(key=lambda r: r.mi)

        lines = [f"Maintainability Index ({len(results)} files):"]
        lines.append("")
        lines.append("Rank: A (high MI 20-100), B (medium 10-20), C (low 0-10)")
        lines.append("")

        for r in results:
            status = (
                "OK" if r.rank == "A" else "ATTENTION" if r.rank == "B" else "CRITICAL"
            )
            lines.append(f"  {r.rank} [{status:9}] {r.mi:5.1f} - {r.path}")

        # Summary
        avg_mi = sum(r.mi for r in results) / len(results)
        lines.append("")
        lines.append(f"Average MI: {avg_mi:.1f}")

        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"
