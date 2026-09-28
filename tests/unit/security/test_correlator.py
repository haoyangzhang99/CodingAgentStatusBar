"""Tests for EventCorrelator - Multi-event correlation."""

import time
import pytest
from opencode_status_bar.security.sequences import SecurityEvent, EventType
from opencode_status_bar.security.correlator import EventCorrelator, Correlation


@pytest.fixture
def correlator() -> EventCorrelator:
    """Create a fresh EventCorrelator for each test."""
    return EventCorrelator(buffer_size=200, default_window_seconds=300.0)


def create_event(
    event_type: EventType,
    target: str,
    session_id: str = "test-session",
    timestamp: float = 0.0,
    risk_score: int = 0,
) -> SecurityEvent:
    """Helper to create security events."""
    ts = timestamp if timestamp > 0 else time.time()
    return SecurityEvent(
        event_type=event_type,
        target=target,
        session_id=session_id,
        timestamp=ts,
        risk_score=risk_score,
    )


class TestCorrelationDetection:
    """Tests for correlation detection - positive and negative cases."""

    POSITIVE_CASES = [
        pytest.param(
            EventType.READ,
            "/home/user/.env",
            EventType.WEBFETCH,
            "https://evil.com/collect",
            "exfiltration_read_webfetch",
            "T1048",
            30,
            id="exfil_read_webfetch",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://evil.com/check",
            EventType.READ,
            "/secrets/api.key",
            "exfiltration_read_webfetch",
            "T1048",
            30,
            id="exfil_webfetch_read",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://example.com/install.sh",
            EventType.BASH,
            "bash ./install.sh",
            "remote_code_execution",
            "T1059",
            35,
            id="rce_shell",
        ),
        pytest.param(
            EventType.WEBFETCH,
            "https://example.com/payload.py",
            EventType.BASH,
            "python payload.py",
            "remote_code_execution",
            "T1059",
            35,
            id="rce_python",
        ),
        pytest.param(
            EventType.WRITE,
            "/tmp/backdoor.sh",
            EventType.BASH,
            "chmod +x /tmp/backdoor.sh",
            "execution_preparation",
            "T1222",
            25,
            id="exec_prep",
        ),
        pytest.param(
            EventType.READ,
            "/project/.git/config",
            EventType.WEBFETCH,
            "https://github.com/some/repo",
            "git_reconnaissance",
            "T1592",
            20,
            id="git_recon",
        ),
    ]

    @pytest.mark.parametrize(
        "e1_type,e1_target,e2_type,e2_target,corr_type,mitre,modifier", POSITIVE_CASES
    )
    def test_correlation_detected(
        self,
        correlator,
        base_time,
        e1_type,
        e1_target,
        e2_type,
        e2_target,
        corr_type,
        mitre,
        modifier,
    ):
        """Verify correlation is detected with correct metadata."""
        e1 = create_event(e1_type, e1_target, timestamp=base_time, risk_score=85)
        e2 = create_event(e2_type, e2_target, timestamp=base_time + 30, risk_score=50)

        assert correlator.add_event(e1) == []
        corrs2 = correlator.add_event(e2)

        matching = [c for c in corrs2 if c.correlation_type == corr_type]
        assert len(matching) == 1
        c = matching[0]
        assert c.mitre_technique == mitre and c.mitre_technique != "XXXX"
        assert c.score_modifier == modifier
        assert 0.0 <= c.confidence <= 1.0
        assert c.description != ""

    def test_correlation_context_time_delta(self, correlator, base_time):
        """Verify correlation context contains accurate time_delta_seconds."""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/collect", timestamp=base_time + 30
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

        assert len(exfil) == 1
        ctx = exfil[0].context
        assert ctx["time_delta_seconds"] == 30
        assert "source_target" in ctx and "related_target" in ctx

    def test_correlation_at_window_boundary(self, correlator, base_time):
        """Verify correlation works exactly at max_window_seconds boundary."""
        # At 299s should still correlate (inside 300s window)
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/exfil", timestamp=base_time + 299
        )
        correlator.add_event(e1)
        corrs = correlator.add_event(e2)
        assert (
            len(
                [c for c in corrs if c.correlation_type == "exfiltration_read_webfetch"]
            )
            == 1
        )
        # Test correlation at exact window boundary (kills mutant 120: > vs >=)
        correlator.clear_all()
        e3 = create_event(EventType.READ, "/secret/.env", timestamp=base_time)
        e4 = create_event(
            EventType.WEBFETCH, "https://evil.com", timestamp=base_time + 300
        )
        correlator.add_event(e3)
        corrs2 = correlator.add_event(e4)
        # At exactly 300s, should still correlate (> not >=)
        exfil2 = [
            c for c in corrs2 if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil2) == 1  # Kills mutant 120

    def test_correlation_session_id_preserved(self, correlator, base_time):
        """Verify correlation preserves session_id and find_related_events works."""
        e1 = create_event(
            EventType.WRITE,
            "/tmp/malware.sh",
            session_id="my-session",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "chmod +x /tmp/malware.sh",
            session_id="my-session",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        prep = [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        assert len(prep) == 1 and prep[0].session_id == "my-session"

        related = correlator.find_related_events(e1)
        assert related == [e2]
        assert len(correlator.get_events_by_path("my-session", "/tmp/malware.sh")) >= 1

    def test_find_related_events_skips_outside_window(self, correlator, base_time):
        """find_related_events uses continue (not break) for outside-window events."""
        ea = create_event(
            EventType.WRITE, "/path/file.sh", session_id="s", timestamp=base_time
        )
        eb = create_event(
            EventType.BASH,
            "echo /path/file.sh",
            session_id="s",
            timestamp=base_time + 500,
        )
        ec = create_event(
            EventType.BASH,
            "cat /path/file.sh",
            session_id="s",
            timestamp=base_time + 10,
        )

        correlator.add_event(ea)
        correlator.add_event(eb)  # Outside window from ea
        correlator.add_event(ec)  # Inside window from ea

        # Should find ec despite eb being outside window (continue, not break)
        assert len(correlator.find_related_events(ea)) == 1


class TestNoCorrelation:
    """Tests verifying correlations are NOT triggered in specific cases."""

    NEGATIVE_CASES = [
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.WEBFETCH,
            "http://localhost:3000/api",
            10,
            id="localhost",
        ),
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.WEBFETCH,
            "https://evil.com/collect",
            301,  # Just outside 300s window - kills max_window_seconds mutants
            id="outside_window",
        ),
        pytest.param(
            EventType.READ,
            "/app/.env",
            EventType.READ,
            "/secrets/key",
            10,
            id="same_type",
        ),
    ]

    @pytest.mark.parametrize(
        "e1_type,e1_target,e2_type,e2_target,offset", NEGATIVE_CASES
    )
    def test_no_exfiltration_correlation(
        self, correlator, base_time, e1_type, e1_target, e2_type, e2_target, offset
    ):
        """Verify exfiltration correlation is NOT triggered."""
        e1 = create_event(e1_type, e1_target, timestamp=base_time)
        e2 = create_event(e2_type, e2_target, timestamp=base_time + offset)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        assert not [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

    def test_chmod_without_prior_write_no_correlation(self, correlator, base_time):
        """chmod without prior write doesn't create execution_preparation."""
        e1 = create_event(
            EventType.BASH, "chmod +x /some/script.sh", timestamp=base_time
        )
        e2 = create_event(EventType.READ, "no_path_here", timestamp=base_time + 5)

        correlations = correlator.add_event(e1)
        correlator.add_event(e2)

        assert not [
            c for c in correlations if c.correlation_type == "execution_preparation"
        ]
        # e2 has no extractable path (no "/"), so no correlation
        assert correlator.find_related_events(e1) == []

    def test_single_event_no_correlation(self, correlator, base_time):
        """Single event cannot create correlations, find_related_events returns empty."""
        event = create_event(EventType.READ, "/app/.env", timestamp=base_time)

        assert correlator.add_event(event) == []
        assert len(correlator.get_session_buffer("test-session")) == 1
        assert correlator.find_related_events(event) == []
        assert len(correlator.get_events_by_path("test-session", "/app/.env")) == 1


class TestSessionManagement:
    """Tests for session buffer management."""

    SESSION_CASES = [
        pytest.param(
            [("s1", EventType.READ, "/f1"), ("s2", EventType.WRITE, "/f2")],
            {"s1": 1, "s2": 1},
            id="separate",
        ),
        pytest.param(
            [
                ("s1", EventType.READ, "/f1"),
                ("s1", EventType.WRITE, "/f2"),
                ("s2", EventType.READ, "/f3"),
            ],
            {"s1": 2, "s2": 1},
            id="multiple_in_one",
        ),
    ]

    @pytest.mark.parametrize("events,expected", SESSION_CASES)
    def test_session_buffer_counts(self, correlator, events, expected):
        """Verify session buffers track events correctly."""
        for session_id, event_type, target in events:
            correlator.add_event(
                create_event(event_type, target, session_id=session_id)
            )

        for session_id, count in expected.items():
            buffer = correlator.get_session_buffer(session_id)
            assert len(buffer) == count

    def test_clear_session_removes_only_target(self, correlator):
        """Clearing a session removes only that session's data including path_index."""
        e1 = create_event(EventType.READ, "/path/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/path/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        assert correlator.get_events_by_path("s1", "/path/file1") != []

        correlator.clear_session("s1")

        assert correlator.get_session_buffer("s1") == []
        assert len(correlator.get_session_buffer("s2")) == 1
        assert correlator.get_events_by_path("s1", "/path/file1") == []

    def test_clear_all_removes_all_sessions(self, correlator):
        """Clearing all removes all session data including path_index."""
        e1 = create_event(EventType.READ, "/path/file1", session_id="s1")
        e2 = create_event(EventType.READ, "/path/file2", session_id="s2")

        correlator.add_event(e1)
        correlator.add_event(e2)
        assert correlator.get_events_by_path("s1", "/path/file1") != []

        correlator.clear_all()

        assert correlator.get_session_buffer("s1") == []
        assert correlator.get_session_buffer("s2") == []
        assert correlator.get_events_by_path("s1", "/path/file1") == []

    def test_empty_session_buffer_returns_empty_list(self, correlator, base_time):
        """Getting buffer for non-existent session returns empty list."""
        assert correlator.get_session_buffer("non-existent") == []
        assert correlator.get_events_by_path("non-existent", "/any/path") == []

    def test_get_events_by_path_no_slash_in_target(self, correlator, base_time):
        """get_events_by_path with target lacking '/' returns empty (no index entry)."""
        e = create_event(
            EventType.READ, "simple_target", session_id="s", timestamp=base_time
        )
        correlator.add_event(e)
        # "simple_target" has no "/" so _extract_path returns None, not indexed
        assert correlator.get_events_by_path("s", "simple_target") == []


class TestCorrelationMetrics:
    """Tests for correlation summary and confidence scoring."""

    def test_summary_counts_by_type(self, correlator, base_time):
        """get_correlation_summary returns accurate type counts."""
        e1 = create_event(EventType.READ, "/app/.env", timestamp=base_time)
        e2 = create_event(
            EventType.WEBFETCH, "https://evil.com/1", timestamp=base_time + 10
        )
        e3 = create_event(
            EventType.WEBFETCH, "https://evil.com/2", timestamp=base_time + 20
        )

        correlator.add_event(e1)
        corrs1 = correlator.add_event(e2)
        corrs2 = correlator.add_event(e3)

        all_corrs = corrs1 + corrs2
        summary = correlator.get_correlation_summary(all_corrs)

        assert summary["exfiltration_read_webfetch"] == 2
        assert isinstance(summary, dict)
        assert len(all_corrs) == 2
        assert all(
            c.correlation_type == "exfiltration_read_webfetch" for c in all_corrs
        )

    def test_high_risk_close_events_high_confidence(self, correlator, base_time):
        """High risk events close in time produce confidence > 0.8 and <= 1.0."""
        # Use risk_scores that sum to >100 to test min(1.0, ...) capping
        e1 = create_event(
            EventType.READ, "/secrets/.env", timestamp=base_time, risk_score=100
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/exfil",
            timestamp=base_time + 1,
            risk_score=100,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

        assert len(exfil) == 1
        conf = exfil[0].confidence
        assert conf >= 0.8
        assert isinstance(conf, float)
        # With risk_score 100+100=200, risk_factor = 200/100 = 2.0 if not capped
        # min(1.0, 2.0) = 1.0, confidence = 0.5*time + 0.3*1.0 + 0.2 = ~1.0
        # min(2.0, 2.0) = 2.0, confidence = 0.5*time + 0.3*2.0 + 0.2 = ~1.3 (capped by outer min)
        assert conf <= 1.0  # Must be capped at 1.0

    def test_low_risk_distant_events_lower_confidence(self, correlator, base_time):
        """Low risk events far apart produce confidence between 0.5-0.7."""
        e1 = create_event(
            EventType.READ, "/app/.env", timestamp=base_time, risk_score=20
        )
        e2 = create_event(
            EventType.WEBFETCH,
            "https://example.com",
            timestamp=base_time + 100,
            risk_score=10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)
        exfil = [
            c
            for c in correlations
            if c.correlation_type == "exfiltration_read_webfetch"
        ]

        assert len(exfil) == 1
        conf = exfil[0].confidence
        assert 0.5 <= conf <= 0.7
        assert isinstance(conf, float)
        assert conf >= 0.0
        assert conf <= 1.0
        # Additional check: distant events with high risk should still have capped confidence
        correlator.clear_all()
        e3 = create_event(
            EventType.READ, "/x/.env", timestamp=base_time, risk_score=100
        )
        e4 = create_event(
            EventType.WEBFETCH,
            "https://evil.com/x",
            timestamp=base_time + 295,
            risk_score=100,
        )
        correlator.add_event(e3)
        corrs = correlator.add_event(e4)
        exfil2 = [
            c for c in corrs if c.correlation_type == "exfiltration_read_webfetch"
        ]
        assert len(exfil2) == 1
        # With risk capped at 1.0: conf ~0.51; with mutant (risk=2.0): conf ~0.81
        assert exfil2[0].confidence < 0.6  # Kills mutant 171
        # Lower confidence for distant, low-risk events
        assert 0.5 <= exfil[0].confidence <= 0.7


# Phase 3 - New Correlation Pattern Tests (Plan 43)


class TestConfigPoisoningCorrelation:
    """Tests for config_poisoning correlation pattern."""

    @pytest.mark.parametrize(
        "config_file,bash_cmd,expected_match",
        [
            (".bashrc", "ls -la", True),
            ("~/.zshrc", "echo hello", True),
            ("/home/user/.profile", "pwd", True),
            ("/tmp/random.txt", "ls", False),  # Not a config file
        ],
        ids=["bashrc-ls", "zshrc-echo", "profile-pwd", "no-config"],
    )
    def test_config_poisoning_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        config_file: str,
        bash_cmd: str,
        expected_match: bool,
    ):
        """write(shell_config) -> bash(any) triggers config poisoning."""
        e1 = create_event(EventType.WRITE, config_file, timestamp=base_time)
        e2 = create_event(EventType.BASH, bash_cmd, timestamp=base_time + 10)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]

        if expected_match:
            assert len(poisoning) == 1
            assert poisoning[0].score_modifier == 25
            assert poisoning[0].mitre_technique == "T1546"
        else:
            assert len(poisoning) == 0

    def test_config_poisoning_outside_window(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Config poisoning outside 60s window doesn't trigger."""
        e1 = create_event(EventType.WRITE, ".bashrc", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "ls",
            timestamp=base_time + 120,  # 2 minutes later
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]
        assert len(poisoning) == 0


class TestDependencyConfusionCorrelation:
    """Tests for dependency_confusion correlation pattern."""

    @pytest.mark.parametrize(
        "fetch_url,package_file,expected_match",
        [
            ("https://registry.npmjs.org/malicious", "package.json", True),
            ("https://pypi.org/simple/evil-pkg", "setup.py", True),
            ("https://rubygems.org/gems/backdoor", "Gemfile", True),
            (
                "https://example.com/data.json",
                "config.json",
                False,
            ),  # Not package registry
        ],
        ids=["npm-package", "pypi-setup", "rubygems-gemfile", "no-registry"],
    )
    def test_dependency_confusion_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        fetch_url: str,
        package_file: str,
        expected_match: bool,
    ):
        """webfetch(registry) -> write(package_file) triggers dependency confusion."""
        e1 = create_event(EventType.WEBFETCH, fetch_url, timestamp=base_time)
        e2 = create_event(EventType.WRITE, package_file, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        confusion = [
            c for c in correlations if c.correlation_type == "dependency_confusion"
        ]

        if expected_match:
            assert len(confusion) == 1
            assert confusion[0].score_modifier == 30
            assert confusion[0].mitre_technique == "T1195"
        else:
            assert len(confusion) == 0


class TestSecretLoggingCorrelation:
    """Tests for secret_logging correlation pattern."""

    @pytest.mark.parametrize(
        "secret_file,log_file,expected_match",
        [
            ("/app/.env", "/var/log/app.log", True),
            ("/secrets/credentials.json", "output.log", True),
            ("~/.ssh/id_rsa.pem", "logs/debug.log", True),
            ("/app/config.yml", "/var/log/app.log", False),  # Not a secrets file
        ],
        ids=["env-varlog", "creds-outputlog", "pem-debuglog", "no-secrets"],
    )
    def test_secret_logging_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        secret_file: str,
        log_file: str,
        expected_match: bool,
    ):
        """read(secrets) -> write(log) triggers secret logging."""
        e1 = create_event(EventType.READ, secret_file, timestamp=base_time)
        e2 = create_event(EventType.WRITE, log_file, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        logging_corr = [
            c for c in correlations if c.correlation_type == "secret_logging"
        ]

        if expected_match:
            assert len(logging_corr) == 1
            assert logging_corr[0].score_modifier == 35
            assert logging_corr[0].mitre_technique == "T1074"
        else:
            assert len(logging_corr) == 0


class TestTunnelEstablishmentCorrelation:
    """Tests for tunnel_establishment correlation pattern."""

    @pytest.mark.parametrize(
        "ssh_cmd,webfetch_url,expected_match",
        [
            ("ssh -L 8080:remote:80 user@host", "https://evil.com/data", True),
            ("ssh -R 9000:localhost:22 attacker@box", "https://external.io/api", True),
            ("ssh user@server", "https://example.com", False),  # No tunnel flags
            (
                "ssh -L 8080:remote:80 user@host",
                "http://localhost:3000",
                False,
            ),  # localhost
        ],
        ids=["local-tunnel", "remote-tunnel", "no-tunnel", "localhost-excluded"],
    )
    def test_tunnel_establishment_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        ssh_cmd: str,
        webfetch_url: str,
        expected_match: bool,
    ):
        """bash(ssh -L/-R) -> webfetch(external) triggers tunnel establishment."""
        e1 = create_event(EventType.BASH, ssh_cmd, timestamp=base_time)
        e2 = create_event(EventType.WEBFETCH, webfetch_url, timestamp=base_time + 60)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        tunnel = [
            c for c in correlations if c.correlation_type == "tunnel_establishment"
        ]

        if expected_match:
            assert len(tunnel) == 1
            assert tunnel[0].score_modifier == 30
            assert tunnel[0].mitre_technique == "T1572"
        else:
            assert len(tunnel) == 0


class TestCleanupAfterAttackCorrelation:
    """Tests for cleanup_after_attack correlation pattern."""

    @pytest.mark.parametrize(
        "destructive_cmd,cleanup_cmd,expected_match",
        [
            ("rm -rf /tmp/evidence", "history -c", True),
            ("shred -u /var/log/auth.log", "rm ~/.bash_history", True),
            ("rm -rf /data/traces", "unset HISTFILE", True),
            ("ls -la", "history -c", False),  # Not destructive
        ],
        ids=["rm-history-c", "shred-rm-history", "rm-unset-histfile", "no-destructive"],
    )
    def test_cleanup_after_attack_detection(
        self,
        correlator: EventCorrelator,
        base_time: float,
        destructive_cmd: str,
        cleanup_cmd: str,
        expected_match: bool,
    ):
        """bash(rm -rf/shred) -> bash(history clear) triggers cleanup detection."""
        e1 = create_event(EventType.BASH, destructive_cmd, timestamp=base_time)
        e2 = create_event(EventType.BASH, cleanup_cmd, timestamp=base_time + 30)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]

        if expected_match:
            assert len(cleanup) == 1
            assert cleanup[0].score_modifier == 40
            assert cleanup[0].mitre_technique == "T1070"
        else:
            assert len(cleanup) == 0

    def test_cleanup_outside_window(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Cleanup correlation outside 3min window doesn't trigger."""
        e1 = create_event(EventType.BASH, "rm -rf /tmp/data", timestamp=base_time)
        e2 = create_event(
            EventType.BASH,
            "history -c",
            timestamp=base_time + 300,  # 5 minutes later
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]
        assert len(cleanup) == 0


class TestNewCorrelationMetadata:
    """Tests for metadata correctness on new correlations."""

    def test_config_poisoning_context_includes_time_delta(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Config poisoning correlation context includes accurate time_delta."""
        e1 = create_event(EventType.WRITE, ".bashrc", timestamp=base_time)
        e2 = create_event(EventType.BASH, "ls", timestamp=base_time + 15)

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        poisoning = [
            c for c in correlations if c.correlation_type == "config_poisoning"
        ]
        assert len(poisoning) == 1
        assert poisoning[0].context["time_delta_seconds"] == 15

    def test_cleanup_correlation_preserves_session_id(
        self, correlator: EventCorrelator, base_time: float
    ):
        """Cleanup correlation preserves session_id from events."""
        e1 = create_event(
            EventType.BASH,
            "rm -rf /tmp/data",
            session_id="attack-session",
            timestamp=base_time,
        )
        e2 = create_event(
            EventType.BASH,
            "history -c",
            session_id="attack-session",
            timestamp=base_time + 10,
        )

        correlator.add_event(e1)
        correlations = correlator.add_event(e2)

        cleanup = [
            c for c in correlations if c.correlation_type == "cleanup_after_attack"
        ]
        assert len(cleanup) == 1
        assert cleanup[0].session_id == "attack-session"
