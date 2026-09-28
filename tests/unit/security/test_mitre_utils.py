"""
Tests for MITRE ATT&CK utilities.
Consolidated: 17 tests → 5 tests with stronger assertions.
"""

import pytest

from opencode_status_bar.security.mitre_utils import (
    serialize_mitre_techniques,
    deserialize_mitre_techniques,
)


class TestSerializeMitreTechniques:
    """Tests for serialize_mitre_techniques function."""

    @pytest.mark.parametrize(
        "techniques,expected_json,description",
        [
            ([], "[]", "empty list"),
            (["T1059"], '["T1059"]', "single technique"),
            (
                ["T1059.001", "T1566.001", "T1027"],
                '["T1059.001", "T1566.001", "T1027"]',
                "multiple techniques",
            ),
            (
                ["T1059", "T1059.001", "T1059.002"],
                '["T1059", "T1059.001", "T1059.002"]',
                "technique with subtechniques",
            ),
        ],
    )
    def test_serialize_valid_lists(self, techniques, expected_json, description):
        """Valid technique lists serialize to correct JSON format."""
        result = serialize_mitre_techniques(techniques)

        assert result == expected_json
        assert result.startswith("[")
        assert result.endswith("]")
        # Verify it's valid JSON by checking structure
        assert result.count("[") == 1
        assert result.count("]") == 1

    @pytest.mark.parametrize(
        "invalid_input,input_type",
        [
            (None, "None"),
            ("T1059", "string"),
            ({"technique": "T1059"}, "dict"),
            (123, "int"),
            (12.34, "float"),
            (set(["T1059"]), "set"),
        ],
    )
    def test_serialize_invalid_inputs_return_empty_array(
        self, invalid_input, input_type
    ):
        """Non-list inputs return empty array '[]' for type safety."""
        result = serialize_mitre_techniques(invalid_input)

        assert result == "[]"
        assert isinstance(result, str)
        assert len(result) == 2


class TestDeserializeMitreTechniques:
    """Tests for deserialize_mitre_techniques function."""

    @pytest.mark.parametrize(
        "json_str,expected_list,description",
        [
            ("[]", [], "empty array"),
            ('["T1059"]', ["T1059"], "single technique"),
            (
                '["T1059.001", "T1566.001", "T1027"]',
                ["T1059.001", "T1566.001", "T1027"],
                "multiple techniques",
            ),
        ],
    )
    def test_deserialize_valid_json(self, json_str, expected_list, description):
        """Valid JSON arrays deserialize to correct Python lists."""
        result = deserialize_mitre_techniques(json_str)

        assert result == expected_list
        assert isinstance(result, list)
        assert len(result) == len(expected_list)
        # Verify all items are strings
        assert all(isinstance(item, str) for item in result)

    @pytest.mark.parametrize(
        "invalid_input,description",
        [
            (None, "None value"),
            ("", "empty string"),
            ("not valid json", "invalid JSON"),
            ('{"technique": "T1059"}', "JSON object instead of array"),
            ('"T1059"', "JSON string instead of array"),
            ("T1059", "plain string"),
            ("[invalid", "malformed JSON"),
        ],
    )
    def test_deserialize_invalid_inputs_return_empty_list(
        self, invalid_input, description
    ):
        """Invalid or non-array inputs return empty list for error resilience."""
        result = deserialize_mitre_techniques(invalid_input)

        assert result == []
        assert isinstance(result, list)
        assert len(result) == 0


class TestRoundTrip:
    """Tests for serialize/deserialize round-trip consistency."""

    @pytest.mark.parametrize(
        "original",
        [
            [],
            ["T1059"],
            ["T1059.001", "T1566.001", "T1027"],
            ["T1059", "T1059.001", "T1059.002", "T1059.003"],
        ],
    )
    def test_roundtrip_preserves_data(self, original):
        """Techniques survive serialize→deserialize round-trip unchanged."""
        serialized = serialize_mitre_techniques(original)
        deserialized = deserialize_mitre_techniques(serialized)

        assert deserialized == original
        assert len(deserialized) == len(original)
        assert isinstance(serialized, str)
        assert isinstance(deserialized, list)
        # Verify order is preserved
        for i, technique in enumerate(original):
            assert deserialized[i] == technique
