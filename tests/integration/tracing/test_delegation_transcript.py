"""Integration tests for DelegationTranscriptPanel display.

The panel now shows a simplified view with just prompt input and response output,
using get_session_prompts() API instead of the detailed timeline.
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from PyQt6.QtWidgets import QLabel, QTextEdit

from tests.mocks import MockAnalyticsAPIClient

pytestmark = [
    pytest.mark.integration,
    pytest.mark.xdist_group(name="qt_tracing"),  # Force same worker for Qt UI tests
]

FIXED_TEST_DATE = datetime(2024, 1, 15, 10, 30, 0)


def create_session_prompts_data():
    """Create session prompts data matching new API format."""
    return {
        "prompt_input": "Analyze the codebase structure and identify key modules",
        "prompt_output": "The project has a modular structure with main.py as entry point.",
    }


class TestDelegationTranscriptPanelDisplay:
    @pytest.fixture
    def panel(self, qapp):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    @pytest.fixture
    def mock_client(self):
        responses = {
            "session_prompts": {
                "sess-delegation-test": create_session_prompts_data(),
            },
            "health": True,
        }
        return MockAnalyticsAPIClient(responses)

    def test_panel_displays_prompt_input_first(self, panel, mock_client, qtbot):
        """GIVEN delegation data with prompt_input
        WHEN panel loads the delegation
        THEN prompt section appears with correct header
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        content_layout = panel._content_layout
        assert content_layout.count() >= 2

        all_labels = panel.findChildren(QLabel)
        header_texts = [label.text() for label in all_labels]

        assert any("Prompt" in text for text in header_texts)

    def test_panel_displays_prompt_content_in_text_edit(
        self, panel, mock_client, qtbot
    ):
        """GIVEN delegation data with prompt_input
        WHEN panel loads the delegation
        THEN prompt content appears in QTextEdit widget
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        assert len(text_edits) >= 1

        all_contents = [te.toPlainText() for te in text_edits]
        prompt_found = any(
            "Analyze the codebase" in content for content in all_contents
        )
        assert prompt_found

    def test_panel_displays_response_section(self, panel, mock_client, qtbot):
        """GIVEN delegation data with prompt_output
        WHEN panel loads the delegation
        THEN response section is displayed with correct header
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        header_texts = [label.text() for label in all_labels]

        assert any("Response" in text for text in header_texts)

    def test_panel_displays_response_content(self, panel, mock_client, qtbot):
        """GIVEN delegation data with prompt_output
        WHEN panel loads the delegation
        THEN response content appears in QTextEdit widget
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        all_contents = [te.toPlainText() for te in text_edits]

        response_found = any("modular structure" in content for content in all_contents)
        assert response_found

    def test_panel_displays_both_sections_in_order(self, panel, mock_client, qtbot):
        """GIVEN delegation data with both prompt and response
        WHEN panel loads the delegation
        THEN prompt section appears before response section
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        header_texts = [label.text() for label in all_labels]

        prompt_idx = next((i for i, t in enumerate(header_texts) if "Prompt" in t), -1)
        response_idx = next(
            (i for i, t in enumerate(header_texts) if "Response" in t), -1
        )

        assert prompt_idx >= 0, "Prompt header should exist"
        assert response_idx >= 0, "Response header should exist"
        assert prompt_idx < response_idx, "Prompt should appear before Response"

    def test_panel_has_two_text_edits_for_content(self, panel, mock_client, qtbot):
        """GIVEN delegation data with both prompt and response
        WHEN panel loads the delegation
        THEN two QTextEdit widgets are created for content display
        """
        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "sess-delegation-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 15000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        assert len(text_edits) == 2


class TestDelegationTranscriptPanelEdgeCases:
    @pytest.fixture
    def panel(self, qapp):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    def test_panel_handles_empty_data(self, panel, qapp, qtbot):
        """GIVEN delegation data with no prompt or response
        WHEN panel loads the delegation
        THEN panel shows appropriate empty state message
        """
        responses = {
            "session_prompts": {
                "empty-session": {"prompt_input": "", "prompt_output": ""},
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "empty-session",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 0,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text().lower() for label in all_labels]

        empty_message_found = any("no" in t and "content" in t for t in all_texts)
        assert empty_message_found

    def test_panel_handles_only_prompt_input(self, panel, qapp, qtbot):
        """GIVEN delegation data with only prompt_input
        WHEN panel loads the delegation
        THEN only prompt section is displayed
        """
        responses = {
            "session_prompts": {
                "prompt-only": {
                    "prompt_input": "Just a prompt",
                    "prompt_output": "",
                },
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "prompt-only",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        assert len(text_edits) == 1

        all_labels = panel.findChildren(QLabel)
        header_texts = [label.text() for label in all_labels]
        assert any("Prompt" in text for text in header_texts)
        assert not any("Response" in text for text in header_texts)

    def test_panel_handles_missing_child_session_id(self, panel, qapp, qtbot):
        """GIVEN delegation data without child_session_id
        WHEN panel loads the delegation
        THEN panel shows appropriate message
        """
        delegation_data = {
            "child_session_id": None,
            "subagent_type": "explore",
            "status": "completed",
            "duration_ms": 0,
        }
        panel.load_delegation(delegation_data)
        qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text().lower() for label in all_labels]

        message_found = any("no" in t and "session" in t for t in all_texts)
        assert message_found

    def test_panel_handles_api_unavailable(self, panel, qapp, qtbot):
        """GIVEN API client is unavailable
        WHEN panel loads the delegation
        THEN panel shows appropriate error message
        """
        mock_client = MockAnalyticsAPIClient({"health": False})
        mock_client.set_available(False)

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "test-session",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        all_labels = panel.findChildren(QLabel)
        all_texts = [label.text().lower() for label in all_labels]

        error_message_found = any(
            "api" in t and "not available" in t for t in all_texts
        )
        assert error_message_found


class TestDelegationTranscriptPanelContentDisplay:
    """Tests for content display in the simplified panel."""

    @pytest.fixture
    def panel(self, qapp):
        from opencode_status_bar.dashboard.sections.tracing.detail_panel.components import (
            DelegationTranscriptPanel,
        )

        panel = DelegationTranscriptPanel()
        yield panel
        panel.deleteLater()

    def test_prompt_input_exact_content(self, panel, qapp, qtbot):
        """GIVEN specific prompt content
        WHEN panel loads the delegation
        THEN exact content appears in first QTextEdit
        """
        expected_prompt = "Search for all Python files in src/"
        expected_response = "Found 15 Python files in the src directory."

        responses = {
            "session_prompts": {
                "exact-content": {
                    "prompt_input": expected_prompt,
                    "prompt_output": expected_response,
                },
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "exact-content",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        assert len(text_edits) == 2

        prompt_content = text_edits[0].toPlainText()
        response_content = text_edits[1].toPlainText()

        assert prompt_content == expected_prompt
        assert response_content == expected_response

    def test_text_edits_are_readonly(self, panel, qapp, qtbot):
        """GIVEN loaded delegation
        WHEN panel is displayed
        THEN QTextEdit widgets are read-only
        """
        responses = {
            "session_prompts": {
                "readonly-test": {
                    "prompt_input": "Test prompt",
                    "prompt_output": "Test response",
                },
            },
            "health": True,
        }
        mock_client = MockAnalyticsAPIClient(responses)

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            delegation_data = {
                "child_session_id": "readonly-test",
                "subagent_type": "explore",
                "status": "completed",
                "duration_ms": 5000,
            }
            panel.load_delegation(delegation_data)
            qtbot.wait(50)

        text_edits = panel.findChildren(QTextEdit)
        for te in text_edits:
            assert te.isReadOnly()
