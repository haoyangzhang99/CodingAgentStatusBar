"""
Sequence Analyzer - Kill Chain Detection for Security Audit

Detects suspicious multi-step attack patterns (kill chains) by analyzing
sequences of events within a sliding time window per session.

Sequences detected:
- read(.env) -> webfetch(external) = Exfiltration (+40)
- write(*.sh) -> chmod(+x) -> bash(*.sh) = Script execution (+30)
- git clone -> npm install -> bash = Supply chain (+25)
- read(/etc/passwd) -> read(/etc/shadow) = System enumeration (+35)
- Multiple rm in < 30s = Mass deletion (+20)
"""

import re
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Deque


class EventType(Enum):
    """Types of security-relevant events"""

    READ = "read"
    WRITE = "write"
    BASH = "bash"
    WEBFETCH = "webfetch"
    UNKNOWN = "unknown"


@dataclass
class SecurityEvent:
    """A security-relevant event for sequence analysis"""

    event_type: EventType
    target: str  # file_path, url, or command
    session_id: str
    timestamp: float  # Unix timestamp in seconds
    tool: str = ""
    risk_score: int = 0
    metadata: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class SequenceMatch:
    """A detected kill chain sequence"""

    name: str
    description: str
    events: List[SecurityEvent]
    score_bonus: int
    mitre_technique: str = ""

    @property
    def session_id(self) -> str:
        return self.events[0].session_id if self.events else ""


# Kill chain pattern definitions
KILL_CHAIN_PATTERNS = [
    {
        "name": "exfiltration",
        "description": "Exfiltration of secrets",
        "score_bonus": 40,
        "mitre_technique": "T1048",
        "steps": [
            {"type": EventType.READ, "pattern": r"\.(env|pem|key|secret|password)"},
            {
                "type": EventType.WEBFETCH,
                "pattern": r"https?://(?!localhost|127\.0\.0\.1)",
            },
        ],
        "max_window_seconds": 300,  # 5 minutes
    },
    {
        "name": "script_execution",
        "description": "Creation and execution of script",
        "score_bonus": 30,
        "mitre_technique": "T1059",
        "steps": [
            {"type": EventType.WRITE, "pattern": r"\.(sh|bash|zsh)$"},
            {"type": EventType.BASH, "pattern": r"chmod\s+(\+x|[0-7]{3,4})"},
            {"type": EventType.BASH, "pattern": r"\.(sh|bash|zsh)"},
        ],
        "max_window_seconds": 120,  # 2 minutes
    },
    {
        "name": "supply_chain",
        "description": "Potential supply chain attack",
        "score_bonus": 25,
        "mitre_technique": "T1195",
        "steps": [
            {"type": EventType.BASH, "pattern": r"git\s+clone"},
            {
                "type": EventType.BASH,
                "pattern": r"npm\s+install|yarn\s+install|pip\s+install",
            },
            {"type": EventType.BASH, "pattern": r"(ba)?sh\s|node\s|python"},
        ],
        "max_window_seconds": 600,  # 10 minutes
    },
    {
        "name": "system_enumeration",
        "description": "System enumeration",
        "score_bonus": 35,
        "mitre_technique": "T1087",
        "steps": [
            {"type": EventType.READ, "pattern": r"/etc/passwd"},
            {"type": EventType.READ, "pattern": r"/etc/shadow|/etc/group|/etc/sudoers"},
        ],
        "max_window_seconds": 300,  # 5 minutes
    },
    # =========================================================================
    # Phase 3 - New Kill Chain Patterns (Plan 43)
    # =========================================================================
    {
        "name": "credential_harvest",
        "description": "Credential file access followed by network exfiltration",
        "score_bonus": 35,
        "mitre_technique": "T1552",
        "steps": [
            {"type": EventType.READ, "pattern": r"\.ssh/|\.aws/|\.netrc|\.pgpass"},
            {"type": EventType.BASH, "pattern": r"\bcurl\s+.*-d\s+|\bwget\s+.*--post"},
        ],
        "max_window_seconds": 600,  # 10 minutes
    },
    {
        "name": "persistence_install",
        "description": "Service creation or startup modification for persistence",
        "score_bonus": 40,
        "mitre_technique": "T1547",
        "steps": [
            {
                "type": EventType.WRITE,
                "pattern": r"\.bashrc|\.bash_profile|\.zshrc|crontab|LaunchAgent",
            },
            {"type": EventType.BASH, "pattern": r"\bchmod\s+\+x|\bsource\s+"},
        ],
        "max_window_seconds": 300,  # 5 minutes
    },
    {
        "name": "data_staging",
        "description": "Data collection and staging for exfiltration",
        "score_bonus": 40,
        "mitre_technique": "T1560",
        "steps": [
            {"type": EventType.BASH, "pattern": r"\bfind\s+.*-type\s+f"},
            {"type": EventType.BASH, "pattern": r"\btar\s+.*-[a-z]*c|\bzip\s+-r"},
            {
                "type": EventType.WEBFETCH,
                "pattern": r"s3://|gs://|https?://(?!localhost)",
            },
        ],
        "max_window_seconds": 900,  # 15 minutes
    },
    {
        "name": "privilege_escalation",
        "description": "SUID binary creation or sudo rule modification",
        "score_bonus": 45,
        "mitre_technique": "T1548",
        "steps": [
            # Match: chmod u+s, chmod g+s, chmod 4xxx (SUID), chmod 2xxx (SGID)
            {
                "type": EventType.BASH,
                "pattern": r"\bchmod\s+[ug]\+s|\bchmod\s+[42][0-7]{3}",
            },
            {"type": EventType.BASH, "pattern": r"\bsudo\s+"},
        ],
        "max_window_seconds": 300,  # 5 minutes
    },
    {
        "name": "cloud_credential_abuse",
        "description": "Cloud credential theft and abuse",
        "score_bonus": 45,
        "mitre_technique": "T1567",
        "steps": [
            {"type": EventType.READ, "pattern": r"\.aws/credentials|\.boto|gcloud"},
            {"type": EventType.BASH, "pattern": r"\baws\s+|\bgcloud\s+|\baz\s+"},
        ],
        "max_window_seconds": 600,  # 10 minutes
    },
    {
        "name": "container_escape",
        "description": "Attempt to escape container to host",
        "score_bonus": 50,
        "mitre_technique": "T1611",
        "steps": [
            {"type": EventType.READ, "pattern": r"/proc/1/|/proc/self/"},
            {
                "type": EventType.BASH,
                "pattern": r"\bdocker\s+|\bnsenter\s+|\bchroot\s+",
            },
        ],
        "max_window_seconds": 300,  # 5 minutes
    },
]


class SequenceAnalyzer:
    """
    Analyzes sequences of events to detect kill chains.

    Maintains a circular buffer of recent events per session and checks
    for suspicious multi-step patterns.
    """

    def __init__(
        self,
        buffer_size: int = 100,
        default_window_seconds: float = 300.0,
    ):
        """
        Initialize the sequence analyzer.

        Args:
            buffer_size: Maximum number of events to keep per session
            default_window_seconds: Default time window for pattern matching
        """
        self._buffer_size = buffer_size
        self._default_window = default_window_seconds
        self._session_buffers: Dict[str, Deque[SecurityEvent]] = {}
        self._patterns = KILL_CHAIN_PATTERNS.copy()

    def add_event(self, event: SecurityEvent) -> List[SequenceMatch]:
        """
        Add an event to the buffer and check for sequence matches.

        Args:
            event: The security event to add

        Returns:
            List of detected sequence matches (kill chains)
        """
        session_id = event.session_id

        # Get or create session buffer
        if session_id not in self._session_buffers:
            self._session_buffers[session_id] = deque(maxlen=self._buffer_size)

        buffer = self._session_buffers[session_id]
        buffer.append(event)

        # Check for pattern matches
        return self._check_patterns(session_id)

    def _check_patterns(self, session_id: str) -> List[SequenceMatch]:
        """Check all patterns against the session buffer"""
        matches: List[SequenceMatch] = []
        buffer = self._session_buffers.get(session_id, deque())

        if len(buffer) < 2:
            return matches

        events_list = list(buffer)
        current_time = events_list[-1].timestamp

        for pattern in self._patterns:
            window_val = pattern.get("max_window_seconds")
            if isinstance(window_val, (int, float)):
                window = float(window_val)
            else:
                window = self._default_window
            match = self._match_pattern(events_list, pattern, current_time, window)
            if match:
                matches.append(match)

        return matches

    def _match_pattern(
        self,
        events: List[SecurityEvent],
        pattern: Dict,
        current_time: float,
        window_seconds: float,
    ) -> Optional[SequenceMatch]:
        """
        Try to match a kill chain pattern against events.

        The pattern steps must occur in order within the time window.
        """
        steps = pattern["steps"]
        matched_events: List[SecurityEvent] = []
        step_index = 0

        # Filter events within time window
        window_events = [
            e for e in events if (current_time - e.timestamp) <= window_seconds
        ]

        for event in window_events:
            if step_index >= len(steps):
                break

            step = steps[step_index]
            if self._event_matches_step(event, step):
                matched_events.append(event)
                step_index += 1

        # All steps must be matched
        if step_index == len(steps):
            return SequenceMatch(
                name=pattern["name"],
                description=pattern["description"],
                events=matched_events,
                score_bonus=pattern["score_bonus"],
                mitre_technique=pattern.get("mitre_technique", ""),
            )

        return None

    def _event_matches_step(self, event: SecurityEvent, step: Dict) -> bool:
        """Check if an event matches a pattern step"""
        # Check event type
        if event.event_type != step["type"]:
            return False

        # Check target pattern
        pattern = step.get("pattern", "")
        if pattern and not re.search(pattern, event.target, re.IGNORECASE):
            return False

        return True

    def check_mass_deletion(
        self, session_id: str, window_seconds: float = 30.0, threshold: int = 5
    ) -> Optional[SequenceMatch]:
        """
        Check for mass deletion pattern (multiple rm commands in short time).

        Args:
            session_id: Session to check
            window_seconds: Time window to check
            threshold: Minimum number of rm commands to trigger

        Returns:
            SequenceMatch if mass deletion detected, None otherwise
        """
        buffer = self._session_buffers.get(session_id, deque())
        if not buffer:
            return None

        current_time = list(buffer)[-1].timestamp
        rm_events = [
            e
            for e in buffer
            if e.event_type == EventType.BASH
            and re.search(r"\brm\s+", e.target)
            and (current_time - e.timestamp) <= window_seconds
        ]

        if len(rm_events) >= threshold:
            return SequenceMatch(
                name="mass_deletion",
                description="Mass deletion detected",
                events=rm_events,
                score_bonus=20,
                mitre_technique="T1070",
            )

        return None

    def get_session_buffer(self, session_id: str) -> List[SecurityEvent]:
        """Get all events in a session buffer"""
        return list(self._session_buffers.get(session_id, deque()))

    def clear_session(self, session_id: str) -> None:
        """Clear the buffer for a specific session"""
        if session_id in self._session_buffers:
            del self._session_buffers[session_id]

    def clear_all(self) -> None:
        """Clear all session buffers"""
        self._session_buffers.clear()

    def get_active_sessions(self) -> List[str]:
        """Get list of sessions with events in buffer"""
        return list(self._session_buffers.keys())


def create_event_from_audit_data(
    tool: str,
    target: str,
    session_id: str,
    timestamp: Optional[float] = None,
    risk_score: int = 0,
) -> SecurityEvent:
    """
    Factory function to create SecurityEvent from audit data.

    Args:
        tool: Tool name (bash, read, write, webfetch)
        target: Command, file path, or URL
        session_id: Session identifier
        timestamp: Event timestamp (defaults to now)
        risk_score: Associated risk score

    Returns:
        SecurityEvent instance
    """
    event_type_map = {
        "bash": EventType.BASH,
        "read": EventType.READ,
        "write": EventType.WRITE,
        "edit": EventType.WRITE,
        "webfetch": EventType.WEBFETCH,
    }

    return SecurityEvent(
        event_type=event_type_map.get(tool, EventType.UNKNOWN),
        target=target,
        session_id=session_id,
        timestamp=timestamp or time.time(),
        tool=tool,
        risk_score=risk_score,
    )
