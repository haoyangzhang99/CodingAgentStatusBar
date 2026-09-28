"""CLI entry point for pycode analysis tools.

Usage:
    uv run python -m tools.pycode <command> [options] <target>

Commands:
    goto <file>:<line>:<col>     - Go to definition
    refs <file>:<line>:<col>     - Find references
    hover <file>:<line>:<col>    - Get hover documentation
    symbols <file>               - List symbols in file
    lint <path>                  - Run linting (ruff)
    check <path>                 - Check formatting (ruff)
    complexity <path>            - Analyze cyclomatic complexity
    maintainability <path>       - Analyze maintainability index
    dead-code <path>             - Detect dead code
    report <path>                - Generate combined report

Options:
    --json                       - Output as JSON
    --verbose                    - Show more details
"""

from __future__ import annotations

import argparse
import json
import sys

from .navigation import goto_definition, find_references, get_hover, list_symbols
from .diagnostics import lint, check
from .metrics import complexity, maintainability
from .deadcode import detect_dead_code
from .report import generate_report


def parse_location(loc: str) -> tuple[str, int, int]:
    """Parse file:line:col format.

    Args:
        loc: Location string in format "file:line:col"

    Returns:
        Tuple of (file_path, line, column)
    """
    parts = loc.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid location format: {loc}. Expected file:line:col")

    file_path, line_str, col_str = parts
    try:
        line = int(line_str)
        col = int(col_str)
    except ValueError as e:
        raise ValueError(f"Invalid line or column number: {e}") from e

    return file_path, line, col


def output_result(result, as_json: bool = False):
    """Output result to stdout."""
    if as_json:
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps({"result": result}, indent=2))
    else:
        print(result)


def cmd_goto(args):
    """Handle goto command."""
    file_path, line, col = parse_location(args.location)
    result = goto_definition(file_path, line, col, as_json=args.json)
    output_result(result, args.json)


def cmd_refs(args):
    """Handle refs command."""
    file_path, line, col = parse_location(args.location)
    result = find_references(file_path, line, col, as_json=args.json)
    output_result(result, args.json)


def cmd_hover(args):
    """Handle hover command."""
    file_path, line, col = parse_location(args.location)
    result = get_hover(file_path, line, col, as_json=args.json)
    output_result(result, args.json)


def cmd_symbols(args):
    """Handle symbols command."""
    result = list_symbols(args.file, as_json=args.json)
    output_result(result, args.json)


def cmd_lint(args):
    """Handle lint command."""
    result = lint(args.path, as_json=args.json, fix=getattr(args, "fix", False))
    output_result(result, args.json)


def cmd_check(args):
    """Handle check command."""
    result = check(args.path, as_json=args.json)
    output_result(result, args.json)


def cmd_complexity(args):
    """Handle complexity command."""
    min_rank = "A" if args.verbose else "C"
    result = complexity(args.path, as_json=args.json, min_rank=min_rank)
    output_result(result, args.json)


def cmd_maintainability(args):
    """Handle maintainability command."""
    result = maintainability(args.path, as_json=args.json)
    output_result(result, args.json)


def cmd_deadcode(args):
    """Handle dead-code command."""
    min_confidence = 60 if args.verbose else 80
    result = detect_dead_code(
        args.path, as_json=args.json, min_confidence=min_confidence
    )
    output_result(result, args.json)


def cmd_report(args):
    """Handle report command."""
    result = generate_report(args.path, as_json=args.json, verbose=args.verbose)
    output_result(result, args.json)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="pycode",
        description="Python code analysis CLI tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show more details"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Navigation commands
    goto_parser = subparsers.add_parser("goto", help="Go to definition")
    goto_parser.add_argument("location", help="Location as file:line:col")
    goto_parser.set_defaults(func=cmd_goto)

    refs_parser = subparsers.add_parser("refs", help="Find references")
    refs_parser.add_argument("location", help="Location as file:line:col")
    refs_parser.set_defaults(func=cmd_refs)

    hover_parser = subparsers.add_parser("hover", help="Get hover documentation")
    hover_parser.add_argument("location", help="Location as file:line:col")
    hover_parser.set_defaults(func=cmd_hover)

    symbols_parser = subparsers.add_parser("symbols", help="List symbols in file")
    symbols_parser.add_argument("file", help="Python file path")
    symbols_parser.set_defaults(func=cmd_symbols)

    # Diagnostics commands
    lint_parser = subparsers.add_parser("lint", help="Run linting (ruff)")
    lint_parser.add_argument("path", help="File or directory path")
    lint_parser.add_argument("--fix", action="store_true", help="Apply auto-fixes")
    lint_parser.set_defaults(func=cmd_lint)

    check_parser = subparsers.add_parser("check", help="Check formatting (ruff)")
    check_parser.add_argument("path", help="File or directory path")
    check_parser.set_defaults(func=cmd_check)

    # Metrics commands
    complexity_parser = subparsers.add_parser(
        "complexity", help="Analyze cyclomatic complexity"
    )
    complexity_parser.add_argument("path", help="File or directory path")
    complexity_parser.set_defaults(func=cmd_complexity)

    mi_parser = subparsers.add_parser(
        "maintainability", help="Analyze maintainability index"
    )
    mi_parser.add_argument("path", help="File or directory path")
    mi_parser.set_defaults(func=cmd_maintainability)

    # Dead code command
    deadcode_parser = subparsers.add_parser("dead-code", help="Detect dead code")
    deadcode_parser.add_argument("path", help="File or directory path")
    deadcode_parser.set_defaults(func=cmd_deadcode)

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate combined report")
    report_parser.add_argument("path", help="File or directory path")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    try:
        args.func(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"File not found: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
