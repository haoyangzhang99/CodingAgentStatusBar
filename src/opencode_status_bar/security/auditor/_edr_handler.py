"""
EDR (Endpoint Detection and Response) handler for the security auditor.

Manages sequence analysis and event correlation for detecting kill chains
and suspicious patterns.
"""

import threading
import time
from typing import Dict, Any, List, Optional

from ..sequences import SequenceAnalyzer, SequenceMatch, create_event_from_audit_data
from ..correlator import EventCorrelator, Correlation


class EDRHandler:
    """Handles EDR-like heuristics: sequence analysis and event correlation.

    Encapsulates:
    - SequenceAnalyzer: Detects kill chain patterns
    - EventCorrelator: Correlates related events
    - Recent detections buffer
    """

    def __init__(
        self,
        buffer_size: int = 100,
        correlator_buffer_size: int = 200,
        window_seconds: float = 300.0,
        max_recent: int = 50,
    ):
        self._lock = threading.Lock()

        # EDR components
        self._sequence_analyzer = SequenceAnalyzer(
            buffer_size=buffer_size,
            default_window_seconds=window_seconds,
        )
        self._event_correlator = EventCorrelator(
            buffer_size=correlator_buffer_size,
            default_window_seconds=window_seconds,
        )

        # Detected sequences and correlations (recent)
        self._recent_sequences: List[SequenceMatch] = []
        self._recent_correlations: List[Correlation] = []
        self._max_recent = max_recent

        # Stats counters
        self._sequences_detected = 0
        self._correlations_detected = 0

    def process_event(
        self,
        tool: str,
        target: str,
        session_id: str,
        timestamp: Optional[float],
        risk_score: int,
    ) -> Dict[str, Any]:
        """
        Process event through EDR analyzers (sequence + correlation).

        Returns dict with:
        - sequences: List of detected kill chains
        - correlations: List of detected correlations
        - sequence_score_bonus: Additional score from sequences
        - correlation_score_bonus: Additional score from correlations
        - mitre_from_edr: MITRE techniques from EDR analysis
        """
        # Convert timestamp from milliseconds if needed
        ts = (
            timestamp / 1000.0
            if timestamp and timestamp > 1e10
            else timestamp or time.time()
        )

        # Create security event
        event = create_event_from_audit_data(
            tool=tool,
            target=target,
            session_id=session_id,
            timestamp=ts,
            risk_score=risk_score,
        )

        # Analyze with sequence analyzer
        sequences = self._sequence_analyzer.add_event(event)

        # Check for mass deletion
        mass_del = self._sequence_analyzer.check_mass_deletion(session_id)
        if mass_del:
            sequences.append(mass_del)

        # Analyze with event correlator
        correlations = self._event_correlator.add_event(event)

        # Collect results
        sequence_score_bonus = sum(s.score_bonus for s in sequences)
        correlation_score_bonus = sum(c.score_modifier for c in correlations)

        mitre_from_edr: List[str] = []
        for seq in sequences:
            if seq.mitre_technique and seq.mitre_technique not in mitre_from_edr:
                mitre_from_edr.append(seq.mitre_technique)
        for corr in correlations:
            if corr.mitre_technique and corr.mitre_technique not in mitre_from_edr:
                mitre_from_edr.append(corr.mitre_technique)

        # Store recent detections
        with self._lock:
            for seq in sequences:
                self._recent_sequences.append(seq)
                self._sequences_detected += 1
            for corr in correlations:
                self._recent_correlations.append(corr)
                self._correlations_detected += 1

            # Trim to max recent
            if len(self._recent_sequences) > self._max_recent:
                self._recent_sequences = self._recent_sequences[-self._max_recent :]
            if len(self._recent_correlations) > self._max_recent:
                self._recent_correlations = self._recent_correlations[
                    -self._max_recent :
                ]

        return {
            "sequences": sequences,
            "correlations": correlations,
            "sequence_score_bonus": sequence_score_bonus,
            "correlation_score_bonus": correlation_score_bonus,
            "mitre_from_edr": mitre_from_edr,
        }

    def get_recent_sequences(self) -> List[SequenceMatch]:
        """Get recently detected kill chain sequences."""
        with self._lock:
            return self._recent_sequences.copy()

    def get_recent_correlations(self) -> List[Correlation]:
        """Get recently detected event correlations."""
        with self._lock:
            return self._recent_correlations.copy()

    def get_session_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tracked events for a session."""
        sequence_events = self._sequence_analyzer.get_session_buffer(session_id)
        return [
            {
                "type": e.event_type.value,
                "target": e.target,
                "timestamp": e.timestamp,
                "risk_score": e.risk_score,
            }
            for e in sequence_events
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get EDR-specific statistics."""
        with self._lock:
            return {
                "sequences_detected": self._sequences_detected,
                "correlations_detected": self._correlations_detected,
                "active_sessions": len(self._sequence_analyzer.get_active_sessions()),
                "recent_sequences": len(self._recent_sequences),
                "recent_correlations": len(self._recent_correlations),
            }

    def clear_all(self) -> None:
        """Clear all EDR analyzer buffers (useful for testing)."""
        self._sequence_analyzer.clear_all()
        self._event_correlator.clear_all()
        with self._lock:
            self._recent_sequences.clear()
            self._recent_correlations.clear()
