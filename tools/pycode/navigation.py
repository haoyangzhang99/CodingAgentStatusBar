"""Navigation commands using jedi.

Provides goto definition, find references, hover documentation, and symbol listing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class Location:
    """A code location with file, line, and column."""

    path: str
    line: int
    column: int
    name: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "name": self.name,
            "description": self.description,
        }


@dataclass
class Symbol:
    """A code symbol (function, class, variable, etc.)."""

    name: str
    kind: str
    line: int
    column: int
    full_name: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "line": self.line,
            "column": self.column,
            "full_name": self.full_name,
        }


def _get_jedi_script(file_path: str, line: int, column: int):
    """Create a jedi Script for the given file and position."""
    import jedi

    path = Path(file_path).resolve()
    source = path.read_text()
    return jedi.Script(source, path=path), line, column


def goto_definition(
    file_path: str, line: int, column: int, *, as_json: bool = False
) -> str | list[dict]:
    """Go to definition at the specified location.

    Args:
        file_path: Path to the Python file
        line: Line number (1-based)
        column: Column number (0-based)
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or list of location dicts
    """
    try:
        script, line, column = _get_jedi_script(file_path, line, column)
        definitions = script.goto(line, column)

        locations = []
        for d in definitions:
            if d.module_path:
                loc = Location(
                    path=str(d.module_path),
                    line=d.line or 0,
                    column=d.column or 0,
                    name=d.name,
                    description=d.description,
                )
                locations.append(loc)

        if as_json:
            return [loc.to_dict() for loc in locations]

        if not locations:
            return "No definition found"

        lines = ["Definitions:"]
        for loc in locations:
            lines.append(f"  {loc.path}:{loc.line}:{loc.column} - {loc.name}")
            if loc.description:
                lines.append(f"    {loc.description}")
        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"


def find_references(
    file_path: str, line: int, column: int, *, as_json: bool = False
) -> str | list[dict]:
    """Find all references to the symbol at the specified location.

    Args:
        file_path: Path to the Python file
        line: Line number (1-based)
        column: Column number (0-based)
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or list of location dicts
    """
    try:
        script, line, column = _get_jedi_script(file_path, line, column)
        references = script.get_references(line, column)

        locations = []
        for ref in references:
            if ref.module_path:
                loc = Location(
                    path=str(ref.module_path),
                    line=ref.line or 0,
                    column=ref.column or 0,
                    name=ref.name,
                )
                locations.append(loc)

        if as_json:
            return [loc.to_dict() for loc in locations]

        if not locations:
            return "No references found"

        lines = [f"References ({len(locations)}):"]
        for loc in locations:
            lines.append(f"  {loc.path}:{loc.line}:{loc.column} - {loc.name}")
        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"


def get_hover(
    file_path: str, line: int, column: int, *, as_json: bool = False
) -> str | dict:
    """Get hover documentation for the symbol at the specified location.

    Args:
        file_path: Path to the Python file
        line: Line number (1-based)
        column: Column number (0-based)
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or dict with hover info
    """
    try:
        script, line, column = _get_jedi_script(file_path, line, column)
        names = script.infer(line, column)

        if not names:
            if as_json:
                return {"error": "No information found"}
            return "No information found"

        # Get the first match
        name = names[0]
        result = {
            "name": name.name,
            "type": name.type,
            "module": name.module_name,
            "description": name.description,
            "docstring": name.docstring() or "",
            "signatures": [],
        }

        # Get signatures for functions/methods
        try:
            signatures = script.get_signatures(line, column)
            for sig in signatures:
                result["signatures"].append(str(sig))
        except Exception:
            pass

        if as_json:
            return result

        lines = [f"{result['name']} ({result['type']})"]
        if result["module"]:
            lines.append(f"Module: {result['module']}")
        if result["description"]:
            lines.append(f"Description: {result['description']}")
        if result["docstring"]:
            lines.append("")
            lines.append("Docstring:")
            for doc_line in result["docstring"].split("\n")[:10]:
                lines.append(f"  {doc_line}")
        if result["signatures"]:
            lines.append("")
            lines.append("Signatures:")
            for sig in result["signatures"]:
                lines.append(f"  {sig}")

        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return {"error": str(e)}
        return f"Error: {e}"


def list_symbols(file_path: str, *, as_json: bool = False) -> str | list[dict]:
    """List all symbols in a Python file.

    Args:
        file_path: Path to the Python file
        as_json: Return JSON instead of formatted text

    Returns:
        Formatted string or list of symbol dicts
    """
    try:
        import jedi

        path = Path(file_path).resolve()
        source = path.read_text()
        script = jedi.Script(source, path=path)
        names = script.get_names()

        symbols = []
        for name in names:
            sym = Symbol(
                name=name.name,
                kind=name.type,
                line=name.line or 0,
                column=name.column or 0,
                full_name=name.full_name or "",
            )
            symbols.append(sym)

        if as_json:
            return [sym.to_dict() for sym in symbols]

        if not symbols:
            return "No symbols found"

        lines = [f"Symbols in {path.name} ({len(symbols)}):"]

        # Group by kind
        by_kind: dict[str, list[Symbol]] = {}
        for sym in symbols:
            by_kind.setdefault(sym.kind, []).append(sym)

        for kind in sorted(by_kind.keys()):
            lines.append(f"\n  {kind.upper()}:")
            for sym in sorted(by_kind[kind], key=lambda s: s.line):
                lines.append(f"    {sym.name} (line {sym.line})")

        return "\n".join(lines)

    except Exception as e:
        if as_json:
            return [{"error": str(e)}]
        return f"Error: {e}"
