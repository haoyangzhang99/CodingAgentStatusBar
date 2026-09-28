"""DataLoaderMixin - Handles data loading for TraceDetailPanel tabs."""

from typing import Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from opencode_status_bar.analytics import TracingDataService


class DataLoaderMixin:
    """Mixin providing data loading capabilities for TraceDetailPanel.

    This mixin handles:
    - API client access
    - Tab change events
    - Lazy loading of tab data
    """

    # These attributes are expected from TraceDetailPanel
    _current_session_id: Optional[str]
    _service: Optional["TracingDataService"]
    _transcript_tab: "object"
    _tokens_tab: "object"
    _tools_tab: "object"
    _files_tab: "object"
    _agents_tab: "object"
    _timeline_tab: "object"
    _delegations_tab: "object"

    def _get_api_client(self):
        """Get the API client for data access."""
        from opencode_status_bar.api import get_api_client

        return get_api_client()

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab change - load data for new tab if needed.

        Args:
            index: The index of the newly selected tab
        """
        if not self._current_session_id:
            return

        self._load_tab_data(index)

    def _load_tab_data(self, tab_index: int) -> None:
        """Load data for a specific tab via API.

        Tab indices:
            0 = Transcript
            1 = Tokens
            2 = Tools
            3 = Files
            4 = Agents
            5 = Timeline
            6 = Delegations

        Args:
            tab_index: Index of the tab to load data for
        """
        if not self._current_session_id:
            return

        client = self._get_api_client()

        if not client.is_available:
            return

        try:
            if tab_index == 0:  # Transcript
                self._load_transcript_tab()
            elif tab_index == 1:  # Tokens
                self._load_tokens_tab()
            elif tab_index == 2:  # Tools
                self._load_tools_tab()
            elif tab_index == 3:  # Files
                self._load_files_tab()
            elif tab_index == 4:  # Agents
                self._load_agents_tab()
            elif tab_index == 5:  # Timeline
                self._load_timeline_tab()
            elif tab_index == 6:  # Delegations
                self._load_delegations_tab()
        except Exception:
            pass

    def _load_transcript_tab(self) -> None:
        """Load transcript tab data."""
        if self._transcript_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        client = self._get_api_client()
        prompts_data = client.get_session_prompts(session_id)

        if prompts_data:
            self._transcript_tab.load_data(  # type: ignore
                {
                    "user_content": prompts_data.get("prompt_input", ""),
                    "assistant_content": prompts_data.get("prompt_output", ""),
                }
            )
        else:
            self._transcript_tab.load_data(  # type: ignore
                {
                    "user_content": "(No prompt data available)",
                    "assistant_content": "(Session may be empty or API unavailable)",
                }
            )

    def _load_tokens_tab(self) -> None:
        """Load tokens tab data."""
        if self._tokens_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        client = self._get_api_client()
        data = client.get_session_tokens(session_id)
        if data:
            self._tokens_tab.load_data(data)  # type: ignore

    def _load_tools_tab(self) -> None:
        """Load tools tab data."""
        if self._tools_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        client = self._get_api_client()
        data = client.get_session_tools(session_id)
        if data:
            self._tools_tab.load_data(data)  # type: ignore

    def _load_files_tab(self) -> None:
        """Load files tab data."""
        if self._files_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        client = self._get_api_client()
        data = client.get_session_files(session_id)
        if data:
            self._files_tab.load_data(data)  # type: ignore

    def _load_agents_tab(self) -> None:
        """Load agents tab data."""
        if self._agents_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        client = self._get_api_client()
        agents = client.get_session_agents(session_id)
        if agents:
            self._agents_tab.load_data(agents)  # type: ignore

    def _load_timeline_tab(self) -> None:
        """Load timeline tab data."""
        if self._timeline_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        # Try full timeline from service first
        events = self._load_timeline_full_data(session_id)
        if events:
            self._timeline_tab.load_data(events)  # type: ignore
            return

        # Fallback to API client
        client = self._get_api_client()
        events = client.get_session_timeline(session_id)
        if events:
            self._timeline_tab.load_data(events)  # type: ignore

    def _load_timeline_full_data(self, session_id: str) -> list[dict]:
        """Load full timeline from TracingDataService.

        Uses get_session_timeline_full() which returns complete event data
        including reasoning, tool calls, patches, etc.

        Args:
            session_id: The session ID to load timeline for

        Returns:
            List of timeline events, empty list on error
        """
        if not self._service or not session_id:
            return []

        try:
            result = self._service.get_session_timeline_full(
                session_id, include_children=True
            )
            if result and result.get("success"):
                data = result.get("data", {})
                return data.get("timeline", [])
        except Exception:
            pass

        return []

    def _load_delegations_tab(self) -> None:
        """Load delegations tab data."""
        if self._delegations_tab.is_loaded():  # type: ignore
            return

        session_id = self._current_session_id
        if not session_id:
            return

        tree = self._load_delegations_data(session_id)
        if tree:
            self._delegations_tab.load_data(tree)  # type: ignore

    def _load_delegations_data(self, session_id: str) -> dict:
        """Load delegation tree from TracingDataService.

        Uses get_delegation_tree() which returns the full tree of agent
        delegations starting from this session.

        Args:
            session_id: The session ID to load delegation tree for

        Returns:
            Delegation tree dict, empty dict on error
        """
        if not self._service or not session_id:
            return {}

        try:
            result = self._service.get_delegation_tree(session_id)
            if result:
                return result.get("tree", {})
        except Exception:
            pass

        return {}
