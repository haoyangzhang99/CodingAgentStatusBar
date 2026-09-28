"""
Tests for the loguru-based logger module.
"""

from io import StringIO


from opencode_status_bar.utils.logger import (
    setup_logger,
    get_logger,
    debug,
    info,
    warn,
    warning,
    error,
    critical,
    exception,
    log_context,
    get_request_id,
    get_session_id,
    logger,
    log,
)


class TestSetupLogger:
    """Tests for setup_logger function (backward compatible API)."""

    def test_setup_logger_returns_logger(self):
        """setup_logger returns a logger instance."""
        result = setup_logger()
        assert result is logger

    def test_setup_logger_with_name(self):
        """setup_logger accepts name parameter for compatibility."""
        result = setup_logger("myapp")
        assert result is logger


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """get_logger() returns the logger instance."""
        result = get_logger()
        assert result is logger

    def test_get_logger_with_name(self):
        """get_logger('name') returns logger (name ignored in loguru)."""
        result = get_logger("api")
        assert result is logger


class TestLoggingFunctions:
    """Tests for convenience logging functions."""

    def test_debug_is_callable(self):
        """debug function is callable."""
        assert callable(debug)

    def test_info_is_callable(self):
        """info function is callable."""
        assert callable(info)

    def test_warn_is_callable(self):
        """warn function is callable."""
        assert callable(warn)

    def test_warning_is_callable(self):
        """warning function is callable."""
        assert callable(warning)

    def test_error_is_callable(self):
        """error function is callable."""
        assert callable(error)

    def test_critical_is_callable(self):
        """critical function is callable."""
        assert callable(critical)

    def test_exception_is_callable(self):
        """exception function is callable."""
        assert callable(exception)


class TestLogContext:
    """Tests for log context management."""

    def test_log_context_sets_request_id(self):
        """log_context sets request_id for the duration of the context."""
        assert get_request_id() is None

        with log_context(request_id="test-req-123"):
            assert get_request_id() == "test-req-123"

        assert get_request_id() is None

    def test_log_context_sets_session_id(self):
        """log_context sets session_id for the duration of the context."""
        assert get_session_id() is None

        with log_context(session_id="test-session-456"):
            assert get_session_id() == "test-session-456"

        assert get_session_id() is None

    def test_log_context_auto_generates_ids(self):
        """log_context can auto-generate IDs."""
        with log_context(auto_request_id=True, auto_session_id=True) as ctx:
            assert ctx["request_id"] is not None
            assert ctx["session_id"] is not None
            assert len(ctx["request_id"]) == 8
            assert len(ctx["session_id"]) == 12

    def test_log_context_yields_active_ids(self):
        """log_context yields the active context IDs."""
        with log_context(request_id="req-1", session_id="sess-2") as ctx:
            assert ctx["request_id"] == "req-1"
            assert ctx["session_id"] == "sess-2"

    def test_nested_contexts(self):
        """Nested log contexts work correctly."""
        with log_context(request_id="outer"):
            assert get_request_id() == "outer"
            with log_context(request_id="inner"):
                assert get_request_id() == "inner"
            assert get_request_id() == "outer"
        assert get_request_id() is None


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with old API."""

    def test_import_debug_info_warn_error(self):
        """Can import debug, info, warn, error from logger module."""
        from opencode_status_bar.utils.logger import debug, info, warn, error

        assert callable(debug)
        assert callable(info)
        assert callable(warn)
        assert callable(error)

    def test_import_setup_logger(self):
        """Can import setup_logger from logger module."""
        from opencode_status_bar.utils.logger import setup_logger

        assert callable(setup_logger)
        result = setup_logger()
        assert result is logger

    def test_module_import_functions(self):
        """Can use module.function style like old code."""
        from opencode_status_bar.utils import logger as logger_module

        assert hasattr(logger_module, "debug")
        assert hasattr(logger_module, "info")
        assert hasattr(logger_module, "warn")
        assert hasattr(logger_module, "error")
        assert hasattr(logger_module, "setup_logger")

    def test_log_proxy_available(self):
        """log proxy is available for backward compatibility."""
        assert log is logger


class TestLogOutput:
    """Tests for actual log output."""

    def test_info_logs_message(self, capsys):
        """info() produces output."""
        # Add a stderr sink temporarily
        from loguru import logger as _logger

        handler_id = _logger.add(
            lambda msg: print(msg, end=""),
            format="{level} | {message}",
            level="DEBUG",
        )
        try:
            info("Test message")
        finally:
            _logger.remove(handler_id)

    def test_context_appears_in_logs(self):
        """Context IDs appear in log output."""
        from loguru import logger as _logger

        output = StringIO()
        handler_id = _logger.add(
            output,
            format="{message}{extra[context]}",
            level="DEBUG",
        )
        try:
            with log_context(request_id="ctx-test"):
                _logger.info("Test with context")
            result = output.getvalue()
            assert "req=ctx-test" in result
        finally:
            _logger.remove(handler_id)
