"""
Color maps for visual distinction of operation types.
"""

# Map operation types to color variants
OPERATION_TYPE_COLORS = {
    # Commands
    "command": "type-command",
    "bash": "type-bash",
    "shell": "type-command",
    # File operations
    "read": "type-read",
    "write": "type-write",
    "edit": "type-edit",
    # Search & fetch
    "webfetch": "type-webfetch",
    "web_fetch": "type-webfetch",
    "glob": "type-glob",
    "grep": "type-grep",
    # Skills
    "skill": "type-skill",
    # Task management
    "todoread": "type-read",
    "todowrite": "type-write",
}


def get_operation_variant(operation: str) -> str:
    """Get the color variant for an operation type."""
    op_lower = operation.lower()
    return OPERATION_TYPE_COLORS.get(op_lower, "")
