"""
Storage Schema Analyzer - Analyze OpenCode storage structure and compare with DB.

This module provides tools to:
1. Scan OpenCode storage files and extract schema information
2. Compare source schema with database schema
3. Detect drift (new fields, missing fields, type changes)
4. Generate reports for data completeness audits

Usage:
    from opencode_status_bar.analytics.schema_analyzer import StorageSchemaAnalyzer

    analyzer = StorageSchemaAnalyzer()
    report = analyzer.full_analysis()
    print(report.to_markdown())
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.logger import info, error


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FieldInfo:
    """Information about a field in the schema."""

    name: str
    types_seen: set[str] = field(default_factory=set)
    sample_values: list[Any] = field(default_factory=list)
    count: int = 0
    null_count: int = 0

    @property
    def fill_rate(self) -> float:
        """Percentage of non-null values."""
        if self.count == 0:
            return 0.0
        return (self.count - self.null_count) / self.count * 100

    def add_value(self, value: Any) -> None:
        """Record a value for this field."""
        self.count += 1
        if value is None:
            self.null_count += 1
        else:
            self.types_seen.add(type(value).__name__)
            if len(self.sample_values) < 3 and value not in self.sample_values:
                # Keep up to 3 sample values
                sample = str(value)[:100] if isinstance(value, str) else value
                self.sample_values.append(sample)


@dataclass
class EntitySchema:
    """Schema for an entity type (session, message, part)."""

    entity_type: str
    fields: dict[str, FieldInfo] = field(default_factory=dict)
    file_count: int = 0
    subtypes: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add_field(self, name: str, value: Any) -> None:
        """Add or update a field."""
        if name not in self.fields:
            self.fields[name] = FieldInfo(name=name)
        self.fields[name].add_value(value)

    def process_object(self, obj: dict, subtype: str | None = None) -> None:
        """Process a JSON object and extract schema info."""
        self.file_count += 1
        if subtype:
            self.subtypes[subtype] += 1

        self._extract_fields(obj, prefix="")

    def _extract_fields(self, obj: dict, prefix: str) -> None:
        """Recursively extract fields from nested objects."""
        for key, value in obj.items():
            field_name = f"{prefix}{key}" if prefix else key

            if isinstance(value, dict):
                # For nested objects, record the object and recurse
                self.add_field(field_name, "{...}")
                self._extract_fields(value, f"{field_name}.")
            elif isinstance(value, list):
                self.add_field(field_name, f"[{len(value)} items]")
                # Sample first item if it's a dict
                if value and isinstance(value[0], dict):
                    self._extract_fields(value[0], f"{field_name}[].")
            else:
                self.add_field(field_name, value)


@dataclass
class SchemaComparison:
    """Comparison between source schema and DB schema."""

    entity_type: str
    source_fields: set[str]
    db_fields: set[str]

    @property
    def missing_in_db(self) -> set[str]:
        """Fields in source but not loaded to DB."""
        return self.source_fields - self.db_fields

    @property
    def extra_in_db(self) -> set[str]:
        """Fields in DB but not in source (computed/derived)."""
        return self.db_fields - self.source_fields

    @property
    def common(self) -> set[str]:
        """Fields present in both."""
        return self.source_fields & self.db_fields


@dataclass
class AnalysisReport:
    """Complete analysis report."""

    timestamp: datetime
    storage_path: Path
    schemas: dict[str, EntitySchema]
    comparisons: dict[str, SchemaComparison]

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# OpenCode Storage Schema Analysis",
            "",
            f"**Generated**: {self.timestamp.isoformat()}",
            f"**Storage Path**: `{self.storage_path}`",
            "",
        ]

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append("| Entity | Files | Fields | Subtypes |")
        lines.append("|--------|-------|--------|----------|")
        for name, schema in self.schemas.items():
            subtypes = ", ".join(
                f"{k}({v})" for k, v in sorted(schema.subtypes.items())[:5]
            )
            lines.append(
                f"| {name} | {schema.file_count} | {len(schema.fields)} | {subtypes or '-'} |"
            )
        lines.append("")

        # Schema details
        for name, schema in self.schemas.items():
            lines.append(f"## {name.title()} Schema")
            lines.append("")
            lines.append("| Field | Types | Fill Rate | Samples |")
            lines.append("|-------|-------|-----------|---------|")

            for field_name, field_info in sorted(schema.fields.items()):
                types = ", ".join(sorted(field_info.types_seen)) or "null"
                fill = f"{field_info.fill_rate:.1f}%"
                samples = ", ".join(str(s)[:30] for s in field_info.sample_values[:2])
                lines.append(f"| `{field_name}` | {types} | {fill} | {samples} |")
            lines.append("")

        # Comparisons
        if self.comparisons:
            lines.append("## DB Comparison")
            lines.append("")
            for name, comp in self.comparisons.items():
                lines.append(f"### {name.title()}")
                lines.append("")
                if comp.missing_in_db:
                    lines.append(f"**Missing in DB** ({len(comp.missing_in_db)}):")
                    for f in sorted(comp.missing_in_db)[:20]:
                        lines.append(f"- `{f}`")
                    lines.append("")
                if comp.extra_in_db:
                    lines.append("**Extra in DB** (computed/derived):")
                    for f in sorted(comp.extra_in_db)[:10]:
                        lines.append(f"- `{f}`")
                    lines.append("")

        return "\n".join(lines)


# =============================================================================
# Main Analyzer Class
# =============================================================================


class StorageSchemaAnalyzer:
    """Analyzer for OpenCode storage schema."""

    DEFAULT_STORAGE = Path.home() / ".local/share/opencode/storage"

    def __init__(self, storage_path: Path | str | None = None):
        """Initialize analyzer.

        Args:
            storage_path: Path to OpenCode storage directory
        """
        self.storage_path = Path(storage_path) if storage_path else self.DEFAULT_STORAGE
        self.schemas: dict[str, EntitySchema] = {}

    def scan_storage(self, sample_limit: int = 500) -> dict[str, EntitySchema]:
        """Scan storage and extract schemas.

        Args:
            sample_limit: Maximum files to scan per entity type

        Returns:
            Dict of entity type -> schema
        """
        info(f"[SchemaAnalyzer] Scanning storage: {self.storage_path}")

        self.schemas = {
            "session": EntitySchema("session"),
            "message": EntitySchema("message"),
            "part": EntitySchema("part"),
        }

        # Scan each entity type
        for entity_type in ["session", "message", "part"]:
            entity_dir = self.storage_path / entity_type
            if not entity_dir.exists():
                continue

            self._scan_entity_directory(entity_type, entity_dir, sample_limit)

        return self.schemas

    def _scan_entity_directory(
        self, entity_type: str, directory: Path, limit: int
    ) -> None:
        """Scan a directory for entity files."""
        schema = self.schemas[entity_type]
        count = 0

        # Find all JSON files
        for json_file in directory.rglob("*.json"):
            if count >= limit:
                break

            try:
                with open(json_file, "r") as f:
                    data = json.load(f)

                # Determine subtype
                subtype = data.get("type") or data.get("role") or "default"
                schema.process_object(data, subtype=str(subtype))
                count += 1

            except (json.JSONDecodeError, IOError):
                pass

        info(f"[SchemaAnalyzer] Scanned {count} {entity_type} files")

    def get_db_schema(self) -> dict[str, set[str]]:
        """Get current database schema.

        Returns:
            Dict of table name -> set of column names
        """
        try:
            from .db import AnalyticsDB

            db = AnalyticsDB()
            conn = db.connect(read_only=True)

            db_schema = {}
            for table in ["sessions", "messages", "parts"]:
                try:
                    result = conn.execute(f"DESCRIBE {table}").fetchall()
                    db_schema[table] = {row[0] for row in result}
                except Exception:
                    db_schema[table] = set()

            db.close()
            return db_schema

        except Exception as e:
            error(f"[SchemaAnalyzer] Error getting DB schema: {e}")
            return {}

    def compare_schemas(self) -> dict[str, SchemaComparison]:
        """Compare source schema with DB schema.

        Returns:
            Dict of entity type -> comparison result
        """
        db_schema = self.get_db_schema()
        comparisons = {}

        # Map entity types to table names
        type_to_table = {
            "session": "sessions",
            "message": "messages",
            "part": "parts",
        }

        for entity_type, schema in self.schemas.items():
            table_name = type_to_table.get(entity_type, entity_type)

            # Get top-level source fields (not nested)
            source_fields = {
                name
                for name in schema.fields.keys()
                if "." not in name and "[]" not in name
            }

            db_fields = db_schema.get(table_name, set())

            comparisons[entity_type] = SchemaComparison(
                entity_type=entity_type,
                source_fields=source_fields,
                db_fields=db_fields,
            )

        return comparisons

    def full_analysis(self, sample_limit: int = 500) -> AnalysisReport:
        """Run full analysis and generate report.

        Args:
            sample_limit: Maximum files to scan per entity type

        Returns:
            Complete analysis report
        """
        self.scan_storage(sample_limit)
        comparisons = self.compare_schemas()

        return AnalysisReport(
            timestamp=datetime.now(),
            storage_path=self.storage_path,
            schemas=self.schemas,
            comparisons=comparisons,
        )

    def check_field_availability(self, entity_type: str, field_path: str) -> dict:
        """Check availability of a specific field.

        Args:
            entity_type: session, message, or part
            field_path: Field name or nested path (e.g., "state.title")

        Returns:
            Dict with field info or None if not found
        """
        schema = self.schemas.get(entity_type)
        if not schema:
            return {"error": f"Unknown entity type: {entity_type}"}

        field_info = schema.fields.get(field_path)
        if not field_info:
            return {"error": f"Field not found: {field_path}"}

        return {
            "field": field_path,
            "types": list(field_info.types_seen),
            "fill_rate": field_info.fill_rate,
            "count": field_info.count,
            "samples": field_info.sample_values,
        }


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """Run schema analysis from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze OpenCode storage schema")
    parser.add_argument(
        "--storage",
        "-s",
        type=str,
        default=None,
        help="Path to OpenCode storage directory",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=500,
        help="Maximum files to scan per entity type",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file for report (default: stdout)",
    )

    args = parser.parse_args()

    analyzer = StorageSchemaAnalyzer(args.storage)
    report = analyzer.full_analysis(args.limit)

    markdown = report.to_markdown()

    if args.output:
        Path(args.output).write_text(markdown)
        print(f"Report written to: {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
