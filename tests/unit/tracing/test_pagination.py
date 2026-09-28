import pytest
from unittest.mock import MagicMock
from PyQt6.QtCore import QModelIndex

from opencode_status_bar.dashboard.sections.tracing.tree_model import TracingTreeModel


class TestTracingTreeModelPagination:
    @pytest.fixture
    def model(self):
        return TracingTreeModel(page_size=80)

    def test_initial_state(self, model):
        assert model._has_more == False
        assert model._is_fetching == False
        assert model._total_loaded == 0
        assert model._page_size == 80

    def test_cannot_fetch_more_initially(self, model):
        assert model.canFetchMore(QModelIndex()) == False

    def test_can_fetch_more_after_pagination_state_set(self, model):
        model.set_pagination_state(has_more=True)
        assert model.canFetchMore(QModelIndex()) == True

    def test_can_fetch_more_for_child_always_false(self, model):
        model.set_sessions([{"session_id": "s1", "children": []}])
        child_index = model.index(0, 0)
        assert model.canFetchMore(child_index) == False

    def test_cannot_fetch_more_when_no_more_data(self, model):
        model.set_pagination_state(has_more=False)
        assert model.canFetchMore(QModelIndex()) == False

    def test_cannot_fetch_more_when_fetching(self, model):
        model._is_fetching = True
        assert model.canFetchMore(QModelIndex()) == False

    def test_fetch_more_emits_signal(self, model, qtbot):
        model.set_pagination_state(has_more=True)
        signals_received = []
        model.fetch_more_requested.connect(lambda o, l: signals_received.append((o, l)))

        model.fetchMore(QModelIndex())

        assert len(signals_received) == 1
        assert signals_received[0] == (0, 80)

    def test_fetch_more_sets_fetching_state(self, model):
        model.set_pagination_state(has_more=True)
        model.fetchMore(QModelIndex())
        assert model._is_fetching == True

    def test_fetch_more_does_nothing_for_child(self, model):
        model.set_sessions([{"session_id": "s1", "children": []}])
        child_index = model.index(0, 0)

        signals_received = []
        model.fetch_more_requested.connect(lambda o, l: signals_received.append((o, l)))

        model.fetchMore(child_index)

        assert len(signals_received) == 0

    def test_fetch_more_does_nothing_when_no_more(self, model):
        model.set_pagination_state(has_more=False)

        signals_received = []
        model.fetch_more_requested.connect(lambda o, l: signals_received.append((o, l)))

        model.fetchMore(QModelIndex())

        assert len(signals_received) == 0

    def test_fetch_more_does_nothing_when_already_fetching(self, model):
        model._is_fetching = True

        signals_received = []
        model.fetch_more_requested.connect(lambda o, l: signals_received.append((o, l)))

        model.fetchMore(QModelIndex())

        assert len(signals_received) == 0

    def test_set_pagination_state(self, model):
        model._is_fetching = True

        model.set_pagination_state(has_more=False)

        assert model._has_more == False
        assert model._is_fetching == False

    def test_set_sessions_updates_total_loaded(self, model):
        sessions = [
            {"session_id": "s1", "children": []},
            {"session_id": "s2", "children": []},
        ]
        model.set_sessions(sessions)

        assert model._total_loaded == 2

    def test_append_sessions_updates_total_loaded(self, model):
        model.set_sessions([{"session_id": "s1", "children": []}])
        assert model._total_loaded == 1

        model.append_sessions([{"session_id": "s2", "children": []}])
        assert model._total_loaded == 2

    def test_clear_resets_pagination(self, model):
        model.set_sessions([{"session_id": "s1", "children": []}])
        model.set_pagination_state(has_more=True)
        model._is_fetching = True

        model.clear()

        assert model._total_loaded == 0
        assert model._has_more == False
        assert model._is_fetching == False

    def test_fetch_more_offset_after_load(self, model, qtbot):
        model.set_sessions([{"session_id": f"s{i}", "children": []} for i in range(10)])
        model.set_pagination_state(has_more=True)

        signals_received = []
        model.fetch_more_requested.connect(lambda o, l: signals_received.append((o, l)))

        model.fetchMore(QModelIndex())

        assert signals_received[0] == (10, 80)
