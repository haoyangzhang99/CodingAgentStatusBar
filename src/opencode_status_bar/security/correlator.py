"""
Event Correlator - Multi-event correlation for Security Audit

Correlates events across different types to detect complex attack patterns:
- read(sensitive_file) + webfetch(external_url) = Potential exfiltration
- webfetch(script) + bash(similar_command) = Remote code execution
- write(path) + bash(chmod path) = Execution preparation
- read(.git/config) + webfetch(other_remote) = Reconnaissance

Each correlation enriches alerts with contextual information.
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Deque
from pathlib import Path

from .sequences import SecurityEvent, EventType


@dataclass
class Correlation:
    """A detected correlation between multiple events"""

    correlation_type: str
    description: str
    source_event: SecurityEvent
    related_events: List[SecurityEvent]
    confidence: float  # 0.0 to 1.0
    score_modifier: int
    mitre_technique: str = ""
    context: Dict = field(default_factory=dict)

    @property
    def session_id(self) -> str:
        return self.source_event.session_id


# Correlation pattern definitions
CORRELATION_PATTERNS = [
    {
        "name": "exfiltration_read_webfetch",
        "description": "Potential data exfiltration: sensitive file read followed by external request",
        "source_type": EventType.READ,
        "source_pattern": r"\.(env|pem|key|secret|password|ssh|aws)",
        "target_type": EventType.WEBFETCH,
        "target_pattern": r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0)",
        "score_modifier": 30,
        "mitre_technique": "T1048",
        "max_window_seconds": 300,
    },
    {
        "name": "remote_code_execution",
        "description": "Remote code execution: script download followed by execution",
        "source_type": EventType.WEBFETCH,
        "source_pattern": r"\.(sh|py|bash|js)(\?|$)",
        "target_type": EventType.BASH,
        "target_pattern": r"(ba)?sh\s|python|node",
        "score_modifier": 35,
        "mitre_technique": "T1059",
        "max_window_seconds": 300,
    },
    {
        "name": "execution_preparation",
        "description": "Execution preparation: file written then made executable",
        "source_type": EventType.WRITE,
        "source_pattern": r"\.(sh|bash|py|pl)$",
        "target_type": EventType.BASH,
        "target_pattern": r"chmod\s+\+?[0-7]*x",
        "score_modifier": 25,
        "mitre_technique": "T1222",
        "max_window_seconds": 120,
        "path_correlation": True,  # Require same path in both events
    },
    {
        "name": "git_reconnaissance",
        "description": "Repository reconnaissance: git config read followed by external fetch",
        "source_type": EventType.READ,
        "source_pattern": r"\.git/(config|credentials|HEAD)",
        "target_type": EventType.WEBFETCH,
        "target_pattern": r"github\.com|gitlab\.com|bitbucket\.org",
        "score_modifier": 20,
        "mitre_technique": "T1592",
        "max_window_seconds": 300,
    },
    # =========================================================================
    # Phase 3 - New Correlation Patterns (Plan 43)
    # =========================================================================
    {
        "name": "config_poisoning",
        "description": "Shell config modification followed by shell execution",
        "source_type": EventType.WRITE,
        "source_pattern": r"\.bashrc|\.zshrc|\.profile",
        "target_type": EventType.BASH,
        "target_pattern": r".*",  # Any bash command after config write
        "score_modifier": 25,
        "mitre_technique": "T1546",
        "max_window_seconds": 60,
    },
    {
        "name": "dependency_confusion",
        "description": "External package fetch followed by package file modification",
        "source_type": EventType.WEBFETCH,
        "source_pattern": r"npmjs\.org|pypi\.org|rubygems\.org",
        "target_type": EventType.WRITE,
        "target_pattern": r"package\.json|setup\.py|Gemfile",
        "score_modifier": 30,
        "mitre_technique": "T1195",
        "max_window_seconds": 300,
    },
    {
        "name": "secret_logging",
        "description": "Sensitive file read followed by log write",
        "source_type": EventType.READ,
        "source_pattern": r"\.env|credentials|secrets|\.pem|\.key",
        "target_type": EventType.WRITE,
        "target_pattern": r"\.log$|/var/log/|logs/",
        "score_modifier": 35,
        "mitre_technique": "T1074",
        "max_window_seconds": 120,
    },
    {
        "name": "tunnel_establishment",
        "description": "SSH tunnel followed by external network access",
        "source_type": EventType.BASH,
        "source_pattern": r"\bssh\s+.*-[RL]\s+",
        "target_type": EventType.WEBFETCH,
        "target_pattern": r"https?://(?!localhost|127\.0\.0\.1)",
        "score_modifier": 30,
        "mitre_technique": "T1572",
        "max_window_seconds": 600,
    },
    {
        "name": "cleanup_after_attack",
        "description": "Destructive command followed by history clearing",
        "source_type": EventType.BASH,
        "source_pattern": r"\brm\s+-rf|\bshred\s+",
        "target_type": EventType.BASH,
        "target_pattern": r"\bhistory\s+-c|\brm\s+.*history|unset\s+HISTFILE",
        "score_modifier": 40,
        "mitre_technique": "T1070",
        "max_window_seconds": 180,
        "allow_same_type": True,  # Allow BASH→BASH correlation
    },
]


class EventCorrelator:
    """
    Correlates security events to detect complex attack patterns.

    Maintains event history and checks for correlations when new events
    are added. Correlations enrich alerts with context.
    """

    def __init__(
        self,
        buffer_size: int = 200,
        default_window_seconds: float = 300.0,
    ):
        """
        Initialize the event correlator.

        Args:
            buffer_size: Maximum events to keep per session
            default_window_seconds: Default correlation time window
        """
        self._buffer_size = buffer_size
        self._default_window = default_window_seconds
        self._session_buffers: Dict[str, Deque[SecurityEvent]] = {}
        self._patterns = CORRELATION_PATTERNS.copy()
        self._path_index: Dict[str, Dict[str, List[SecurityEvent]]] = {}

    def add_event(self, event: SecurityEvent) -> List[Correlation]:
        """
        Add an event and check for correlations.

        Args:
            event: The security event to add

        Returns:
            List of detected correlations
        """
        session_id = event.session_id

        # Get or create session buffer
        if session_id not in self._session_buffers:
            self._session_buffers[session_id] = deque(maxlen=self._buffer_size)
            self._path_index[session_id] = {}

        buffer = self._session_buffers[session_id]
        buffer.append(event)

        # Index by path for path-based correlations
        self._index_event(event)

        # Check correlations
        return self._check_correlations(event)

    def _index_event(self, event: SecurityEvent) -> None:
        """Index event by path for efficient correlation lookup"""
        session_id = event.session_id
        if session_id not in self._path_index:
            self._path_index[session_id] = {}

        # Extract path from target
        path = self._extract_path(event.target)
        if path:
            if path not in self._path_index[session_id]:
                self._path_index[session_id][path] = []
            self._path_index[session_id][path].append(event)

    def _extract_path(self, target: str) -> Optional[str]:
        """Extract file path from target string"""
        # For bash commands, try to find file paths
        if "/" in target:
            # Find path-like patterns
            match = re.search(r"(/[\w./-]+)", target)
            if match:
                return match.group(1)
        return None

    def _check_correlations(self, new_event: SecurityEvent) -> List[Correlation]:
        """Check for correlations with the new event"""
        correlations: List[Correlation] = []
        session_id = new_event.session_id
        buffer = self._session_buffers.get(session_id, deque())

        if len(buffer) < 2:
            return correlations

        current_time = new_event.timestamp

        for pattern in self._patterns:
            correlation = self._check_pattern_correlation(
                new_event, list(buffer), pattern, current_time
            )
            if correlation:
                correlations.append(correlation)

        return correlations

    def _check_pattern_correlation(
        self,
        new_event: SecurityEvent,
        events: List[SecurityEvent],
        pattern: Dict,
        current_time: float,
    ) -> Optional[Correlation]:
        """Check if new event correlates with previous events per pattern"""
        window = pattern.get("max_window_seconds", self._default_window)

        # Determine if new event is source or target of pattern
        source_match = new_event.event_type == pattern["source_type"] and re.search(
            pattern["source_pattern"], new_event.target, re.IGNORECASE
        )
        target_match = new_event.event_type == pattern["target_type"] and re.search(
            pattern["target_pattern"], new_event.target, re.IGNORECASE
        )

        if not (source_match or target_match):
            return None

        # Search for matching counterpart in history
        for event in reversed(events[:-1]):  # Exclude new_event itself
            # Check time window
            if (current_time - event.timestamp) > window:
                continue

            # Skip same event type unless explicitly allowed
            allow_same_type = pattern.get("allow_same_type", False)
            if event.event_type == new_event.event_type and not allow_same_type:
                continue

            # Check if event matches the counterpart pattern
            if source_match:
                # New event is source, look for target
                if event.event_type != pattern["target_type"]:
                    continue
                if not re.search(
                    pattern["target_pattern"], event.target, re.IGNORECASE
                ):
                    continue
            else:
                # New event is target, look for source
                if event.event_type != pattern["source_type"]:
                    continue
                if not re.search(
                    pattern["source_pattern"], event.target, re.IGNORECASE
                ):
                    continue

            # Path correlation check if required
            if pattern.get("path_correlation"):
                if not self._paths_correlate(new_event.target, event.target):
                    continue

            # Found correlation!
            source_event = event if target_match else new_event
            target_event = new_event if target_match else event

            return Correlation(
                correlation_type=pattern["name"],
                description=pattern["description"],
                source_event=source_event,
                related_events=[target_event],
                confidence=self._calculate_confidence(source_event, target_event),
                score_modifier=pattern["score_modifier"],
                mitre_technique=pattern.get("mitre_technique", ""),
                context={
                    "time_delta_seconds": abs(
                        target_event.timestamp - source_event.timestamp
                    ),
                    "source_target": source_event.target,
                    "related_target": target_event.target,
                },
            )

        return None

    def _paths_correlate(self, target1: str, target2: str) -> bool:
        """Check if two targets refer to the same file path"""
        path1 = self._extract_path(target1)
        path2 = self._extract_path(target2)

        if not path1 or not path2:
            return False

        # Normalize paths
        p1 = Path(path1).resolve() if path1.startswith("/") else path1
        p2 = Path(path2).resolve() if path2.startswith("/") else path2

        # Check if same path or path is contained in the other
        return str(p1) == str(p2) or str(p1) in str(target2) or str(p2) in str(target1)

    def _calculate_confidence(
        self, source: SecurityEvent, target: SecurityEvent
    ) -> float:
        """
        Calculate confidence score for a correlation.

        Factors:
        - Time proximity (closer = higher confidence)
        - Risk scores of involved events
        - Path similarity (if applicable)
        """
        # Time factor: decay over time window
        time_delta = abs(target.timestamp - source.timestamp)
        time_factor = max(0.0, 1.0 - (time_delta / self._default_window))

        # Risk factor: higher if both events have risk
        risk_factor = min(1.0, (source.risk_score + target.risk_score) / 100)

        # Combined confidence
        confidence = 0.5 * time_factor + 0.3 * risk_factor + 0.2

        return round(min(1.0, confidence), 2)

    def find_related_events(
        self,
        event: SecurityEvent,
        window_seconds: Optional[float] = None,
    ) -> List[SecurityEvent]:
        """
        Find events related to the given event.

        Args:
            event: Event to find relations for
            window_seconds: Time window to search

        Returns:
            List of related events
        """
        session_id = event.session_id
        buffer = self._session_buffers.get(session_id, deque())
        window = window_seconds or self._default_window

        related = []
        for e in buffer:
            if e is event:
                continue
            if abs(e.timestamp - event.timestamp) > window:
                continue

            # Check path correlation
            if self._paths_correlate(event.target, e.target):
                related.append(e)

        return related

    def get_events_by_path(self, session_id: str, path: str) -> List[SecurityEvent]:
        """Get all events related to a specific path"""
        if session_id not in self._path_index:
            return []

        normalized_path = self._extract_path(path) or path
        return self._path_index[session_id].get(normalized_path, [])

    def get_session_buffer(self, session_id: str) -> List[SecurityEvent]:
        """Get all events in a session buffer"""
        return list(self._session_buffers.get(session_id, deque()))

    def clear_session(self, session_id: str) -> None:
        """Clear buffers for a specific session"""
        if session_id in self._session_buffers:
            del self._session_buffers[session_id]
        if session_id in self._path_index:
            del self._path_index[session_id]

    def clear_all(self) -> None:
        """Clear all session data"""
        self._session_buffers.clear()
        self._path_index.clear()

    def get_correlation_summary(
        self, correlations: List[Correlation]
    ) -> Dict[str, int]:
        """Get summary of correlation types"""
        summary: Dict[str, int] = {}
        for corr in correlations:
            summary[corr.correlation_type] = summary.get(corr.correlation_type, 0) + 1
        return summary
