"""Extract file paths from bash commands for scope analysis."""

import shlex
from typing import List

# Commands that operate on files and their path argument positions
FILE_COMMANDS = {
    # Command: list of argument indices that are paths (after flags removed)
    # -1 means "all remaining args"
    "cat": [-1],
    "less": [-1],
    "more": [-1],
    "head": [-1],
    "tail": [-1],
    "rm": [-1],
    "cp": [-1],
    "mv": [-1],
    "chmod": [-1],
    "chown": [-1],
    "touch": [-1],
    "mkdir": [-1],
    "rmdir": [-1],
    "ls": [-1],
    "stat": [-1],
    "file": [-1],
    "grep": [-1],  # last args are files
    "sed": [-1],  # in-place edits
    "awk": [-1],
    "source": [0],
    ".": [0],
    "nano": [-1],
    "vim": [-1],
    "vi": [-1],
    "code": [-1],
    "open": [-1],
}


class PathExtractor:
    """Extract file paths from bash commands."""

    @staticmethod
    def extract_from_command(command: str) -> List[str]:
        """Extract potential file paths from a bash command.

        Args:
            command: Raw bash command string

        Returns:
            List of potential file paths found in command
        """
        if not command or not command.strip():
            return []

        paths = []

        # Handle pipes - analyze each segment
        segments = command.split("|")
        for segment in segments:
            paths.extend(PathExtractor._extract_from_segment(segment.strip()))

        return paths

    @staticmethod
    def _extract_from_segment(segment: str) -> List[str]:
        """Extract paths from a single command segment."""
        if not segment:
            return []

        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Malformed command, try basic split
            tokens = segment.split()

        if not tokens:
            return []

        # Find the base command (skip env vars, sudo, etc.)
        cmd_idx = 0
        while cmd_idx < len(tokens):
            token = tokens[cmd_idx]
            if "=" in token and not token.startswith("-"):
                cmd_idx += 1  # Skip VAR=value
            elif token in ("sudo", "env", "nice", "nohup", "time"):
                cmd_idx += 1  # Skip prefix commands
            else:
                break

        if cmd_idx >= len(tokens):
            return []

        cmd = tokens[cmd_idx].split("/")[-1]  # Get base command name

        if cmd not in FILE_COMMANDS:
            return PathExtractor._extract_path_like_args(tokens[cmd_idx + 1 :])

        # Extract non-flag arguments
        args = []
        i = cmd_idx + 1
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("-"):
                # Skip flag and its value if it takes one
                if token in ("-o", "-f", "-i", "-e", "-n", "-c"):
                    i += 2  # Skip flag and value
                    continue
            else:
                args.append(token)
            i += 1

        return [a for a in args if PathExtractor._looks_like_path(a)]

    @staticmethod
    def _extract_path_like_args(tokens: List[str]) -> List[str]:
        """Extract arguments that look like file paths."""
        paths = []
        for token in tokens:
            if token.startswith("-"):
                continue
            if PathExtractor._looks_like_path(token):
                paths.append(token)
        return paths

    @staticmethod
    def _looks_like_path(s: str) -> bool:
        """Check if a string looks like a file path."""
        if not s:
            return False
        # Starts with /, ~, or ./
        if (
            s.startswith("/")
            or s.startswith("~")
            or s.startswith("./")
            or s.startswith("../")
        ):
            return True
        # Contains path separator and doesn't look like URL
        if "/" in s and not s.startswith("http"):
            return True
        # Has file extension
        if "." in s and len(s.split(".")[-1]) <= 5:
            return True
        return False

    @staticmethod
    def extract_from_tool(tool_name: str, args: dict) -> List[str]:
        """Extract file paths based on tool type.

        Args:
            tool_name: Name of the tool (bash, read, write, edit, etc.)
            args: Arguments dict from parts.arguments JSON

        Returns:
            List of file paths to analyze for scope
        """
        if tool_name in ("read", "write", "edit"):
            path = args.get("filePath", "")
            return [path] if path else []

        if tool_name == "bash":
            command = args.get("command", "")
            return PathExtractor.extract_from_command(command)

        if tool_name == "glob":
            pattern = args.get("pattern", "")
            path = args.get("path", "")
            return [p for p in [pattern, path] if p]

        return []
