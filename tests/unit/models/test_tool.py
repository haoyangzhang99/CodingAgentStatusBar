import pytest
from opencode_status_bar.core.models import Tool


def test_tool_creation():
    tool = Tool(name="bash", arg="ls -la", elapsed_ms=1000)
    assert tool.name == "bash"
    assert tool.arg == "ls -la"
    assert tool.elapsed_ms == 1000


def test_tool_may_need_permission_below_threshold():
    tool = Tool(name="bash", arg="npm install", elapsed_ms=3000)
    assert not tool.may_need_permission


def test_tool_may_need_permission_above_threshold():
    tool = Tool(name="bash", arg="npm install", elapsed_ms=7000)
    assert tool.may_need_permission


def test_tool_excluded_from_permission_detection():
    tool = Tool(name="task", arg="some task", elapsed_ms=10000)
    assert not tool.may_need_permission


def test_tool_to_dict():
    tool = Tool(name="read", arg="/path/to/file", elapsed_ms=500)
    result = tool.to_dict()

    assert result["name"] == "read"
    assert result["arg"] == "/path/to/file"
    assert result["elapsed_ms"] == 500
    assert "may_need_permission" in result
