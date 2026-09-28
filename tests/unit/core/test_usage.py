"""
Tests for opencode_status_bar.core.usage module.
Coverage target: 100%
Refactored for high assertion density (target ratio > 4.0).
"""

import json
import urllib.error
from contextlib import contextmanager
from unittest.mock import MagicMock, mock_open, patch

import pytest

from opencode_status_bar.core.usage import fetch_usage, read_auth_token


# =============================================================================
# Fixtures and Helpers
# =============================================================================


@contextmanager
def mock_usage_api(api_response: dict, token: str = "valid-token"):
    """Context manager to mock the usage API call."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(api_response).encode("utf-8")
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("opencode_status_bar.core.usage.read_auth_token", return_value=token):
        with patch("urllib.request.urlopen", return_value=mock_response):
            yield mock_response


# =============================================================================
# Tests for read_auth_token()
# =============================================================================


class TestReadAuthToken:
    """Tests for the read_auth_token function."""

    def test_returns_token_when_valid_auth_file_exists(self):
        """Valid auth file with token should return the token."""
        auth_data = {"anthropic": {"access": "test-token-123"}}

        with patch("builtins.open", mock_open(read_data=json.dumps(auth_data))):
            result = read_auth_token()

        assert result == "test-token-123", "Token should match"
        assert isinstance(result, str), "Token should be a string"

    @pytest.mark.parametrize(
        "scenario,open_config,error_type",
        [
            pytest.param(
                "file_not_found",
                {"side_effect": FileNotFoundError()},
                FileNotFoundError,
                id="file_not_found",
            ),
            pytest.param(
                "permission_denied",
                {"side_effect": PermissionError()},
                PermissionError,
                id="permission_denied",
            ),
            pytest.param(
                "invalid_json",
                {"read_data": "not valid json {"},
                json.JSONDecodeError,
                id="invalid_json",
            ),
            pytest.param(
                "missing_anthropic_key",
                {"read_data": json.dumps({"other": {"access": "t"}})},
                KeyError,
                id="missing_anthropic",
            ),
            pytest.param(
                "missing_access_key",
                {"read_data": json.dumps({"anthropic": {"refresh": "t"}})},
                KeyError,
                id="missing_access",
            ),
        ],
    )
    def test_returns_none_on_error_conditions(self, scenario, open_config, error_type):
        """Various error conditions should return None gracefully."""
        if "side_effect" in open_config:
            mock_fn = MagicMock(side_effect=open_config["side_effect"])
        else:
            mock_fn = mock_open(read_data=open_config["read_data"])

        with patch("builtins.open", mock_fn):
            result = read_auth_token()

        # Verify None is returned and function doesn't crash
        assert result is None, f"Should return None for {scenario}"
        # Verify the mock was actually called
        assert mock_fn.called, "open() should have been called"
        # Verify result type
        assert not isinstance(result, str), "Should not return a string on error"


# =============================================================================
# Tests for fetch_usage()
# =============================================================================


class TestFetchUsage:
    """Tests for the fetch_usage function."""

    def test_returns_error_when_no_token(self):
        """No auth token should return Usage with error message and zero usage."""
        with patch("opencode_status_bar.core.usage.read_auth_token", return_value=None):
            result = fetch_usage()

        # Verify error state
        assert result.error == "No auth token found", "Error message should match"
        # Verify five_hour defaults
        assert result.five_hour.utilization == 0, "five_hour utilization should be 0"
        assert result.five_hour.resets_at is None, "five_hour resets_at should be None"
        # Verify seven_day defaults
        assert result.seven_day.utilization == 0, "seven_day utilization should be 0"
        assert result.seven_day.resets_at is None, "seven_day resets_at should be None"

    @pytest.mark.parametrize(
        "http_code,expected_error",
        [
            pytest.param(401, "Token expired", id="401_token_expired"),
            pytest.param(403, "HTTP 403", id="403_forbidden"),
            pytest.param(500, "HTTP 500", id="500_server_error"),
            pytest.param(502, "HTTP 502", id="502_bad_gateway"),
            pytest.param(503, "HTTP 503", id="503_unavailable"),
        ],
    )
    def test_returns_appropriate_error_on_http_errors(self, http_code, expected_error):
        """HTTP errors should return appropriate error messages with zero usage."""
        with patch(
            "opencode_status_bar.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            http_error = urllib.error.HTTPError(
                url="https://api.anthropic.com/api/oauth/usage",
                code=http_code,
                msg="Error",
                hdrs=MagicMock(),
                fp=None,
            )
            with patch("urllib.request.urlopen", side_effect=http_error):
                result = fetch_usage()

        # Verify error handling
        assert result.error == expected_error, f"Error should be '{expected_error}'"
        # Verify usage is zeroed on error
        assert result.five_hour.utilization == 0, "five_hour should be 0 on error"
        assert result.seven_day.utilization == 0, "seven_day should be 0 on error"

    @pytest.mark.parametrize(
        "exception,expected_error",
        [
            pytest.param(
                TimeoutError("Connection timed out"),
                "Connection timed out",
                id="timeout",
            ),
            pytest.param(
                urllib.error.URLError("Name resolution failed"),
                "<urlopen error Name resolution failed>",
                id="url_error",
            ),
            pytest.param(
                ConnectionRefusedError("Connection refused"),
                "Connection refused",
                id="connection_refused",
            ),
        ],
    )
    def test_returns_error_on_network_exceptions(self, exception, expected_error):
        """Network exceptions should return error string with zero usage."""
        with patch(
            "opencode_status_bar.core.usage.read_auth_token",
            return_value="valid-token",
        ):
            with patch("urllib.request.urlopen", side_effect=exception):
                result = fetch_usage()

        # Verify error handling
        assert result.error == expected_error, f"Error should be '{expected_error}'"
        # Verify structure is valid even on error
        assert hasattr(result, "five_hour"), "Should have five_hour attribute"
        assert hasattr(result, "seven_day"), "Should have seven_day attribute"
        # Verify defaults on error
        assert result.five_hour.utilization == 0, "Should default to 0"
        assert result.seven_day.utilization == 0, "Should default to 0"

    @pytest.mark.parametrize(
        "api_response,expected",
        [
            pytest.param(
                {
                    "five_hour": {
                        "utilization": 25,
                        "resets_at": "2025-01-01T12:00:00Z",
                    },
                    "seven_day": {
                        "utilization": 50,
                        "resets_at": "2025-01-07T00:00:00Z",
                    },
                },
                {
                    "error": None,
                    "five_hour_util": 25,
                    "five_hour_resets": "2025-01-01T12:00:00Z",
                    "seven_day_util": 50,
                    "seven_day_resets": "2025-01-07T00:00:00Z",
                },
                id="full_response",
            ),
            pytest.param(
                {"seven_day": {"utilization": 30}},
                {
                    "error": None,
                    "five_hour_util": 0,
                    "five_hour_resets": None,
                    "seven_day_util": 30,
                    "seven_day_resets": None,
                },
                id="seven_day_only",
            ),
            pytest.param(
                {"five_hour": {"utilization": 75}},
                {
                    "error": None,
                    "five_hour_util": 75,
                    "five_hour_resets": None,
                    "seven_day_util": 0,
                    "seven_day_resets": None,
                },
                id="five_hour_only",
            ),
        ],
    )
    def test_returns_usage_on_successful_response(self, api_response, expected):
        """Successful API response should return parsed Usage with all fields."""
        with mock_usage_api(api_response):
            result = fetch_usage()

        # Verify no error
        assert result.error == expected["error"], "No error on success"
        # Verify five_hour parsing
        assert result.five_hour.utilization == expected["five_hour_util"]
        assert result.five_hour.resets_at == expected["five_hour_resets"]
        # Verify seven_day parsing
        assert result.seven_day.utilization == expected["seven_day_util"]
        assert result.seven_day.resets_at == expected["seven_day_resets"]
        # Verify types
        assert isinstance(result.five_hour.utilization, int), (
            "utilization should be int"
        )
        assert isinstance(result.seven_day.utilization, int), (
            "utilization should be int"
        )

    @pytest.mark.parametrize(
        "api_response,response_type",
        [
            pytest.param(
                {"five_hour": {"utilization": "not-a-number"}},
                "invalid_utilization",
                id="invalid_utilization",
            ),
            pytest.param(
                {"five_hour": None, "seven_day": None},
                "both_null",
                id="both_null",
            ),
            pytest.param({}, "empty_response", id="empty_response"),
            pytest.param(None, "null_response", id="null_response"),
            pytest.param([], "array_response", id="array_response"),
            pytest.param("string", "string_response", id="string_response"),
        ],
    )
    def test_returns_api_unavailable_on_invalid_response(
        self, api_response, response_type
    ):
        """Invalid or unexpected API responses should return 'API unavailable'."""
        with mock_usage_api(api_response):
            result = fetch_usage()

        # Verify error state
        assert result.error == "API unavailable", (
            f"Should return API unavailable for {response_type}"
        )
        # Verify structure remains valid
        assert hasattr(result, "five_hour"), "Should have five_hour"
        assert hasattr(result, "seven_day"), "Should have seven_day"
        assert hasattr(result.five_hour, "utilization"), (
            "five_hour should have utilization"
        )
        assert hasattr(result.seven_day, "utilization"), (
            "seven_day should have utilization"
        )

    def test_request_headers_are_correctly_set(self):
        """Verify that the request headers are correctly set."""
        api_response = {"five_hour": {}, "seven_day": {}}

        with mock_usage_api(api_response, token="test-bearer-token"):
            with patch("urllib.request.Request") as mock_request_class:
                mock_request = MagicMock()
                mock_request_class.return_value = mock_request

                fetch_usage()

                # Verify URL
                mock_request_class.assert_called_once_with(
                    "https://api.anthropic.com/api/oauth/usage"
                )

                # Verify headers
                calls = mock_request.add_header.call_args_list
                headers_added = {call[0][0]: call[0][1] for call in calls}

                assert "Authorization" in headers_added, (
                    "Should have Authorization header"
                )
                assert headers_added["Authorization"] == "Bearer test-bearer-token"
                assert "anthropic-beta" in headers_added, (
                    "Should have anthropic-beta header"
                )
                assert headers_added["anthropic-beta"] == "oauth-2025-04-20"
                assert "Content-Type" in headers_added, (
                    "Should have Content-Type header"
                )
                assert headers_added["Content-Type"] == "application/json"
                assert len(headers_added) == 3, "Should have exactly 3 headers"
