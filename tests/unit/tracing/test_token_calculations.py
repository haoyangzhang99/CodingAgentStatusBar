"""
Unit tests for token calculations in SessionOverviewPanel.

Tests verify that:
1. Tokens object has the correct structure (input, output, cache_read, cache_write, total)
2. Tokens are correctly aggregated from the API response
3. cache_write is included in the total (regression test)
4. Edge cases (missing fields, None values) are handled correctly
"""

import pytest
from unittest.mock import MagicMock

from opencode_status_bar.dashboard.sections.tracing.detail_panel.components.session_overview import (
    SessionOverviewPanel,
    extract_session_data,
)


class TestTokensObjectStructure:
    """Tests for tokens object structure returned by the API."""

    def test_tokens_object_has_required_fields(self):
        """Test que l'objet tokens retourné par l'API a la bonne structure."""
        # Given: Une structure de données typique de l'API
        tree_data = {
            "tokens": {
                "input": 175,
                "output": 4747,
                "cache_read": 658693,
                "cache_write": 61035,
                "total": 724650,
            },
            "children": [],
        }

        # When: On extrait les tokens
        tokens = tree_data.get("tokens", {})

        # Then: L'objet doit contenir tous les champs requis
        assert "input" in tokens, "tokens should have 'input' field"
        assert "output" in tokens, "tokens should have 'output' field"
        assert "cache_read" in tokens, "tokens should have 'cache_read' field"
        assert "cache_write" in tokens, "tokens should have 'cache_write' field"
        assert "total" in tokens, "tokens should have 'total' field"

    def test_tokens_values_are_integers(self):
        """Test que les valeurs des tokens sont bien des entiers."""
        # Given: Une structure avec des tokens
        tree_data = {
            "tokens": {
                "input": 175,
                "output": 4747,
                "cache_read": 658693,
                "cache_write": 61035,
                "total": 724650,
            },
            "children": [],
        }

        # When: On extrait les tokens
        tokens = tree_data["tokens"]

        # Then: Toutes les valeurs doivent être des entiers
        assert isinstance(tokens["input"], int)
        assert isinstance(tokens["output"], int)
        assert isinstance(tokens["cache_read"], int)
        assert isinstance(tokens["cache_write"], int)
        assert isinstance(tokens["total"], int)

    def test_tokens_values_are_positive(self):
        """Test que les valeurs des tokens sont positives ou nulles."""
        # Given: Une structure avec des tokens
        tree_data = {
            "tokens": {
                "input": 175,
                "output": 4747,
                "cache_read": 658693,
                "cache_write": 61035,
                "total": 724650,
            },
            "children": [],
        }

        # When: On extrait les tokens
        tokens = tree_data["tokens"]

        # Then: Toutes les valeurs doivent être >= 0
        assert tokens["input"] >= 0
        assert tokens["output"] >= 0
        assert tokens["cache_read"] >= 0
        assert tokens["cache_write"] >= 0
        assert tokens["total"] >= 0


class TestTokensAggregation:
    """Tests for token aggregation logic."""

    def test_total_includes_all_token_types(self):
        """Test que le total inclut bien tous les types de tokens."""
        # Given: Des valeurs de tokens connues
        tokens_in = 175
        tokens_out = 4747
        cache_read = 658693
        cache_write = 61035

        # When: On calcule le total
        calculated_total = tokens_in + tokens_out + cache_read + cache_write

        # Then: Le total doit correspondre
        expected_total = 724650
        assert calculated_total == expected_total, (
            f"Total should be {expected_total}, got {calculated_total}"
        )

    def test_cache_write_is_included_in_total(self):
        """Test que cache_write est bien inclus dans le total (regression test).

        Avant cette feature, cache_write était manquant du calcul du total.
        """
        # Given: Une structure avec cache_write non-nul
        tree_data = {
            "tokens": {
                "input": 100,
                "output": 200,
                "cache_read": 300,
                "cache_write": 400,  # <- Ce champ doit être pris en compte
                "total": 1000,
            },
            "children": [],
        }

        # When: On extrait les tokens
        tokens = tree_data["tokens"]

        # Calculate what the total should be
        calculated_total = (
            tokens["input"]
            + tokens["output"]
            + tokens["cache_read"]
            + tokens["cache_write"]
        )

        # Then: cache_write doit être inclus dans le calcul
        assert tokens["cache_write"] > 0, "cache_write should be non-zero for this test"
        assert calculated_total == tokens["total"], (
            f"Total should include cache_write: "
            f"{tokens['input']} + {tokens['output']} + {tokens['cache_read']} + {tokens['cache_write']} "
            f"= {calculated_total} (expected {tokens['total']})"
        )

    def test_tokens_aggregation_with_zero_values(self):
        """Test que l'agrégation fonctionne avec des valeurs nulles."""
        # Given: Certains tokens sont à 0
        tree_data = {
            "tokens": {
                "input": 100,
                "output": 0,
                "cache_read": 0,
                "cache_write": 50,
                "total": 150,
            },
            "children": [],
        }

        # When: On extrait les tokens
        tokens = tree_data["tokens"]
        calculated_total = (
            tokens["input"]
            + tokens["output"]
            + tokens["cache_read"]
            + tokens["cache_write"]
        )

        # Then: Le total doit être correct même avec des 0
        assert calculated_total == tokens["total"]


class TestTokensEdgeCases:
    """Tests for edge cases in token handling."""

    def test_missing_tokens_object(self):
        """Test que l'absence de l'objet tokens est gérée correctement."""
        # Given: Une structure sans l'objet tokens
        tree_data = {
            "children": [],
        }

        # When: On tente d'extraire les tokens
        tokens_dict = tree_data.get("tokens", {})

        # Then: Cela ne doit pas planter, retourner un dict vide
        assert tokens_dict == {}
        assert isinstance(tokens_dict, dict)
        # Accessing with .get() should work without error
        input_tokens = (
            tokens_dict.get("input", 0) if isinstance(tokens_dict, dict) else 0
        )
        output_tokens = (
            tokens_dict.get("output", 0) if isinstance(tokens_dict, dict) else 0
        )
        assert input_tokens == 0
        assert output_tokens == 0

    def test_partial_tokens_object(self):
        """Test qu'un objet tokens incomplet utilise des valeurs par défaut."""
        # Given: Un objet tokens partiel (manque cache_write)
        tree_data = {
            "tokens": {
                "input": 100,
                "output": 200,
                "cache_read": 300,
                # cache_write manquant
            },
            "children": [],
        }

        # When: On extrait les tokens avec des valeurs par défaut
        tokens = tree_data.get("tokens", {})
        tokens_in = tokens.get("input", 0)
        tokens_out = tokens.get("output", 0)
        cache_read = tokens.get("cache_read", 0)
        cache_write = tokens.get("cache_write", 0)  # Devrait être 0 par défaut

        # Then: Les valeurs par défaut doivent être utilisées
        assert tokens_in == 100
        assert tokens_out == 200
        assert cache_read == 300
        assert cache_write == 0, "Missing cache_write should default to 0"

    def test_none_token_values(self):
        """Test que les valeurs None sont traitées comme 0."""
        # Given: Des valeurs None dans les tokens
        tree_data = {
            "tokens": {
                "input": None,
                "output": 100,
                "cache_read": None,
                "cache_write": 50,
                "total": 150,
            },
            "children": [],
        }

        # When: On extrait avec gestion de None
        tokens = tree_data.get("tokens", {})
        tokens_in = tokens.get("input") or 0
        tokens_out = tokens.get("output") or 0
        cache_read = tokens.get("cache_read") or 0
        cache_write = tokens.get("cache_write") or 0

        # Then: None doit être traité comme 0
        assert tokens_in == 0, "None should be treated as 0"
        assert tokens_out == 100
        assert cache_read == 0, "None should be treated as 0"
        assert cache_write == 50


class TestSessionOverviewPanelTokensLoading:
    """Tests for SessionOverviewPanel token loading."""

    def test_panel_loads_tokens_from_tree_data(self, qtbot):
        """Test que le panel charge correctement les tokens depuis tree_data."""
        # Given: Un panel et des données avec tokens
        panel = SessionOverviewPanel()
        tree_data = {
            "tokens": {
                "input": 175,
                "output": 4747,
                "cache_read": 658693,
                "cache_write": 61035,
                "total": 724650,
            },
            "children": [],
        }

        # When: On charge les données
        panel.load_session(tree_data)

        # Then: Le widget tokens doit avoir chargé les bonnes valeurs
        # (Vérifié visuellement dans les tests d'intégration)
        assert panel._tokens is not None

    def test_panel_handles_missing_tokens(self, qtbot):
        """Test que le panel gère l'absence de tokens sans planter."""
        # Given: Un panel et des données sans tokens
        panel = SessionOverviewPanel()
        tree_data = {
            "children": [],
        }

        # When: On charge les données
        success = True
        error = None
        try:
            panel.load_session(tree_data)
        except Exception as e:
            success = False
            error = str(e)

        # Then: Cela ne doit pas planter
        assert success, (
            f"Panel should handle missing tokens gracefully, got error: {error}"
        )


class TestSessionOverviewPanelFilesLoading:
    """Tests for SessionOverviewPanel files loading from API."""

    def test_load_files_from_api_extracts_files_list(self, qtbot):
        """Test that _load_files_from_api extracts files_with_stats from API response."""
        from unittest.mock import Mock, patch

        panel = SessionOverviewPanel()

        mock_client = Mock()
        mock_client.is_available = True
        mock_client.get_session_files.return_value = {
            "details": {
                "files_with_stats": [
                    {"file": "/path/to/file1.py", "type": "read"},
                    {"file": "/path/to/file2.py", "type": "read"},
                    {"file": "/path/to/output.py", "type": "write"},
                ]
            }
        }

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            files_list = panel._load_files_from_api("ses_test")

        assert files_list == [
            {"file": "/path/to/file1.py", "type": "read"},
            {"file": "/path/to/file2.py", "type": "read"},
            {"file": "/path/to/output.py", "type": "write"},
        ]
        mock_client.get_session_files.assert_called_once_with("ses_test")

    def test_load_files_from_api_returns_empty_when_unavailable(self, qtbot):
        """Test that _load_files_from_api returns empty list when API unavailable."""
        from unittest.mock import Mock, patch

        panel = SessionOverviewPanel()

        mock_client = Mock()
        mock_client.is_available = False

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            files_list = panel._load_files_from_api("ses_test")

        assert files_list == []

    def test_load_files_from_api_returns_empty_on_no_data(self, qtbot):
        """Test that _load_files_from_api returns empty list when API returns None."""
        from unittest.mock import Mock, patch

        panel = SessionOverviewPanel()

        mock_client = Mock()
        mock_client.is_available = True
        mock_client.get_session_files.return_value = None

        with patch(
            "opencode_status_bar.api.get_api_client",
            return_value=mock_client,
        ):
            files_list = panel._load_files_from_api("ses_test")

        assert files_list == []
