"""MITRE ATT&CK utilities for serialization."""

import json
from typing import Any


def serialize_mitre_techniques(techniques: Any) -> str:
    """Serialize MITRE techniques to JSON string.

    Args:
        techniques: List of techniques or any value

    Returns:
        JSON string, or "[]" if not a list
    """
    if isinstance(techniques, list):
        return json.dumps(techniques)
    return "[]"


def deserialize_mitre_techniques(json_str: str | None) -> list[str]:
    """Deserialize MITRE techniques from JSON string.

    Args:
        json_str: JSON string or None

    Returns:
        List of technique IDs
    """
    if not json_str:
        return []
    try:
        result = json.loads(json_str)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []
