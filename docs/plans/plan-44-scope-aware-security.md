# Plan 44 - Scope-Aware Security Detection

**Status**: Draft  
**Priority**: Medium  
**Effort**: Medium (3-5 days)  
**Author**: BMad Master  
**Date**: 2026-01-07

## Executive Summary

OpenCode Status Bar's current security detection analyzes commands and file accesses in isolation, without awareness of the project context. This plan introduces **Scope-Aware Security Detection** - a system that understands the boundaries of the current project and flags accesses outside that scope.

### Problem Statement

An AI coding assistant working on `~/Projects/my-app/` should primarily access files within that directory. When it reads `~/.ssh/id_rsa` or modifies `~/.bashrc`, this is likely:
1. A mistake by the AI
2. A prompt injection attack
3. Scope creep that needs user attention

Currently, we detect sensitive file patterns (`.ssh`, `.env`) but we don't detect when an AI accesses `~/other-project/secrets.json` or `~/Downloads/malware.sh` - files that aren't inherently sensitive but are **outside the project scope**.

### Goals

1. **Detect out-of-scope file accesses** with configurable sensitivity
2. **Distinguish between** safe out-of-scope (temp files) and suspicious out-of-scope (user configs)
3. **Integrate seamlessly** with existing SecurityEnrichmentWorker
4. **Minimize false positives** for legitimate cross-project access patterns

---

## 1. Current State Analysis

### 1.1 What We Have

```
┌─────────────────────────────────────────────────────────────┐
│  Current Detection Model                                    │
│                                                             │
│  Input: file_path or command                                │
│         ↓                                                   │
│  Pattern Matching: Is this path/command inherently risky?   │
│         ↓                                                   │
│  Output: risk_score based on PATTERNS only                  │
│                                                             │
│  Limitation: No awareness of "where should the AI be?"      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 What's Missing

| Scenario | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| AI reads `./src/main.py` | Score: 0 (normal file) | Score: 0 (in scope) |
| AI reads `~/.ssh/id_rsa` | Score: 95 (sensitive) | Score: 95 (sensitive + out of scope) |
| AI reads `~/other-project/config.json` | Score: 25 (json file) | Score: 50+ (out of scope!) |
| AI writes `~/.bashrc` | Score: 50 (shell config) | Score: 75+ (out of scope + config modify) |
| AI reads `/tmp/cache.txt` | Score: 0 (temp) | Score: 0 (allowed out of scope) |

### 1.3 Data Available

From the `sessions` table, we have:
- `working_directory`: The CWD where OpenCode was started (= project root)

From the `parts` table, we have:
- `tool_name`: read, write, bash, edit, etc.
- `arguments`: JSON with file paths
- `tool_input_preview`: Often contains file paths

---

## 2. Proposed Architecture

### 2.1 ScopeAnalyzer Component

```python
from pathlib import Path
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ScopeVerdict(Enum):
    """Result of scope analysis."""
    IN_SCOPE = "in_scope"                       # Within project directory
    OUT_OF_SCOPE_ALLOWED = "out_of_scope_allowed"   # Outside but safe (/tmp)
    OUT_OF_SCOPE_NEUTRAL = "out_of_scope_neutral"   # Outside, unknown risk
    OUT_OF_SCOPE_SUSPICIOUS = "out_of_scope_suspicious"  # Outside, elevated risk
    OUT_OF_SCOPE_SENSITIVE = "out_of_scope_sensitive"    # Outside, high risk

@dataclass
class ScopeResult:
    """Result of scope analysis for a path."""
    verdict: ScopeVerdict
    path: str
    resolved_path: str
    project_root: str
    score_modifier: int  # Added to existing risk score
    reason: str

class ScopeAnalyzer:
    """
    Analyzes file paths relative to the project scope.
    
    The project scope is defined by the working directory where
    the OpenCode session was started.
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.home = Path.home()
        
        # Paths always allowed even outside project
        self.allowed_paths = [
            "/tmp/",
            "/var/tmp/",
            "/var/folders/",  # macOS temp
            str(self.home / ".cache/"),
            str(self.home / ".local/share/"),
            str(self.home / ".npm/"),
            str(self.home / ".yarn/"),
        ]
        
        # Paths with elevated suspicion when accessed outside project
        self.suspicious_paths = {
            str(self.home / "Downloads/"): (50, "Downloads folder"),
            str(self.home / "Documents/"): (40, "Documents folder"),
            str(self.home / "Desktop/"): (40, "Desktop folder"),
            str(self.home / "Library/"): (45, "macOS Library"),
            "/usr/": (40, "System usr directory"),
            "/var/": (35, "System var directory"),
            "/opt/": (30, "Opt directory"),
        }
        
        # Paths that are always sensitive (high score)
        self.sensitive_paths = {
            str(self.home / ".ssh/"): (80, "SSH directory"),
            str(self.home / ".aws/"): (75, "AWS credentials"),
            str(self.home / ".kube/"): (70, "Kubernetes config"),
            str(self.home / ".gnupg/"): (75, "GPG keys"),
            str(self.home / ".bashrc"): (60, "Bash config"),
            str(self.home / ".zshrc"): (60, "Zsh config"),
            str(self.home / ".profile"): (60, "Shell profile"),
            str(self.home / ".gitconfig"): (50, "Git config"),
            str(self.home / ".netrc"): (70, "Netrc credentials"),
            str(self.home / ".env"): (75, "Environment file"),
            "/etc/": (65, "System config"),
            "/etc/passwd": (70, "System passwd"),
            "/etc/shadow": (95, "System shadow"),
        }
    
    def analyze(self, path: str, operation: str = "access") -> ScopeResult:
        """
        Analyze a path and determine if it's within project scope.
        
        Args:
            path: The file path to analyze (can be relative or absolute)
            operation: The operation type (read, write, execute)
            
        Returns:
            ScopeResult with verdict and score modifier
        """
        # Resolve the path
        resolved = self._resolve_path(path)
        
        # Check if in project scope
        if self._is_in_project(resolved):
            return ScopeResult(
                verdict=ScopeVerdict.IN_SCOPE,
                path=path,
                resolved_path=str(resolved),
                project_root=str(self.project_root),
                score_modifier=0,
                reason="Within project scope"
            )
        
        # Check if in allowed paths
        if self._is_allowed(resolved):
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_ALLOWED,
                path=path,
                resolved_path=str(resolved),
                project_root=str(self.project_root),
                score_modifier=0,
                reason="Allowed temporary/cache path"
            )
        
        # Check if sensitive
        if result := self._check_sensitive(resolved):
            score, reason = result
            # Write operations on sensitive files get higher score
            if operation == "write":
                score = min(100, score + 15)
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_SENSITIVE,
                path=path,
                resolved_path=str(resolved),
                project_root=str(self.project_root),
                score_modifier=score,
                reason=f"Sensitive: {reason}"
            )
        
        # Check if suspicious
        if result := self._check_suspicious(resolved):
            score, reason = result
            if operation == "write":
                score = min(100, score + 10)
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS,
                path=path,
                resolved_path=str(resolved),
                project_root=str(self.project_root),
                score_modifier=score,
                reason=f"Suspicious: {reason}"
            )
        
        # Generic out of scope
        base_score = 25 if operation == "read" else 35
        return ScopeResult(
            verdict=ScopeVerdict.OUT_OF_SCOPE_NEUTRAL,
            path=path,
            resolved_path=str(resolved),
            project_root=str(self.project_root),
            score_modifier=base_score,
            reason=f"Outside project scope: {resolved}"
        )
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve a path to absolute, handling ~ and relative paths."""
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = (self.project_root / p).resolve()
        return p.resolve()
    
    def _is_in_project(self, path: Path) -> bool:
        """Check if path is within the project directory."""
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False
    
    def _is_allowed(self, path: Path) -> bool:
        """Check if path is in always-allowed locations."""
        path_str = str(path)
        return any(path_str.startswith(allowed) for allowed in self.allowed_paths)
    
    def _check_sensitive(self, path: Path) -> Optional[tuple[int, str]]:
        """Check if path matches sensitive patterns."""
        path_str = str(path)
        for pattern, (score, reason) in self.sensitive_paths.items():
            if path_str.startswith(pattern) or path_str == pattern.rstrip('/'):
                return (score, reason)
        return None
    
    def _check_suspicious(self, path: Path) -> Optional[tuple[int, str]]:
        """Check if path matches suspicious patterns."""
        path_str = str(path)
        for pattern, (score, reason) in self.suspicious_paths.items():
            if path_str.startswith(pattern):
                return (score, reason)
        return None
```

### 2.2 Integration with SecurityEnrichmentWorker

```python
# In security/enrichment/worker.py

class SecurityEnrichmentWorker:
    def __init__(self, db: AnalyticsDB):
        self.db = db
        self.risk_analyzer = get_risk_analyzer()
        self.scope_analyzer: Optional[ScopeAnalyzer] = None
    
    def _get_scope_analyzer(self, session_id: str) -> Optional[ScopeAnalyzer]:
        """Get or create scope analyzer for a session."""
        # Get project root from session
        session = self.db.get_session(session_id)
        if session and session.working_directory:
            return ScopeAnalyzer(Path(session.working_directory))
        return None
    
    def _enrich_part(self, part: Part) -> EnrichmentResult:
        # Existing pattern-based analysis
        risk_result = self.risk_analyzer.analyze_command(part.tool_input_preview)
        
        # NEW: Scope analysis
        scope_result = None
        if self.scope_analyzer and (file_path := self._extract_file_path(part)):
            operation = "write" if part.tool_name in ("write", "edit") else "read"
            scope_result = self.scope_analyzer.analyze(file_path, operation)
            
            # Add scope score modifier
            if scope_result.verdict != ScopeVerdict.IN_SCOPE:
                risk_result.score += scope_result.score_modifier
                risk_result.reasons.append(scope_result.reason)
        
        return EnrichmentResult(
            risk_score=min(100, risk_result.score),
            risk_level=self._score_to_level(risk_result.score),
            risk_reason="; ".join(risk_result.reasons),
            scope_verdict=scope_result.verdict if scope_result else None,
        )
    
    def _extract_file_path(self, part: Part) -> Optional[str]:
        """Extract file path from part arguments."""
        if part.tool_name in ("read", "write", "edit"):
            args = json.loads(part.arguments) if part.arguments else {}
            return args.get("file_path") or args.get("filePath")
        elif part.tool_name == "bash":
            # Try to extract paths from command
            # This is heuristic and may need refinement
            return self._extract_path_from_command(part.tool_input_preview)
        return None
```

### 2.3 Database Schema Changes

```sql
-- Add scope columns to parts table
ALTER TABLE parts ADD COLUMN scope_verdict TEXT;
ALTER TABLE parts ADD COLUMN scope_resolved_path TEXT;

-- New index for scope queries
CREATE INDEX idx_parts_scope_verdict ON parts(scope_verdict);
```

### 2.4 New API Endpoints

```python
# GET /api/sessions/{session_id}/scope-violations
# Returns all out-of-scope accesses for a session

@app.route("/api/sessions/<session_id>/scope-violations")
def get_scope_violations(session_id: str):
    """Get all out-of-scope file accesses for a session."""
    violations = db.query("""
        SELECT 
            timestamp,
            tool_name,
            tool_input_preview,
            scope_verdict,
            scope_resolved_path,
            risk_score,
            risk_reason
        FROM parts 
        WHERE session_id = ? 
          AND scope_verdict NOT IN ('in_scope', 'out_of_scope_allowed')
        ORDER BY timestamp DESC
    """, [session_id])
    return jsonify(violations)
```

---

## 3. Implementation Phases

### Phase 1: Core ScopeAnalyzer (Day 1)

**Files to create:**
- `src/opencode_status_bar/security/scope/__init__.py`
- `src/opencode_status_bar/security/scope/analyzer.py`

**Tasks:**
1. Implement `ScopeAnalyzer` class with path resolution
2. Implement verdict classification (in_scope, out_of_scope_*)
3. Implement score modifiers for each verdict type
4. Unit tests for all path scenarios

**Tests:**
```python
class TestScopeAnalyzer:
    def test_in_scope_relative_path(self):
        analyzer = ScopeAnalyzer(Path("/home/user/project"))
        result = analyzer.analyze("./src/main.py")
        assert result.verdict == ScopeVerdict.IN_SCOPE
        assert result.score_modifier == 0
    
    def test_out_of_scope_ssh(self):
        analyzer = ScopeAnalyzer(Path("/home/user/project"))
        result = analyzer.analyze("~/.ssh/id_rsa")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
        assert result.score_modifier >= 80
    
    def test_out_of_scope_other_project(self):
        analyzer = ScopeAnalyzer(Path("/home/user/project"))
        result = analyzer.analyze("/home/user/other-project/secret.env")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_NEUTRAL
        assert result.score_modifier > 0
    
    def test_allowed_tmp(self):
        analyzer = ScopeAnalyzer(Path("/home/user/project"))
        result = analyzer.analyze("/tmp/cache.txt")
        assert result.verdict == ScopeVerdict.OUT_OF_SCOPE_ALLOWED
        assert result.score_modifier == 0
```

### Phase 2: Integration with EnrichmentWorker (Day 2)

**Files to modify:**
- `src/opencode_status_bar/security/enrichment/worker.py`
- `src/opencode_status_bar/db/schema.py` (add columns)

**Tasks:**
1. Add scope analysis to enrichment pipeline
2. Extract file paths from different tool types
3. Store scope verdict in database
4. Handle edge cases (no session, no working_directory)

### Phase 3: Path Extraction from Commands (Day 3)

**Files to create/modify:**
- `src/opencode_status_bar/security/scope/path_extractor.py`

**Tasks:**
1. Extract file paths from bash commands
2. Handle common patterns: `cat file`, `rm -rf dir`, `cp src dst`
3. Handle pipes and redirections
4. Unit tests for path extraction

```python
class PathExtractor:
    """Extract file paths from shell commands."""
    
    # Patterns for commands that take file arguments
    FILE_ARG_COMMANDS = {
        "cat": [0],      # cat file
        "less": [0],     # less file
        "head": [-1],    # head -n 10 file
        "tail": [-1],    # tail -f file
        "rm": "all",     # rm file1 file2 ...
        "cp": [0, 1],    # cp src dst
        "mv": [0, 1],    # mv src dst
        "chmod": [-1],   # chmod 755 file
        "chown": [-1],   # chown user file
    }
    
    def extract_paths(self, command: str) -> List[str]:
        """Extract file paths from a shell command."""
        # Implementation...
```

### Phase 4: Dashboard Integration (Day 4)

**Files to modify:**
- `src/opencode_status_bar/dashboard/` (if exists)
- API endpoints

**Tasks:**
1. Add scope violation summary to session view
2. Highlight out-of-scope accesses in timeline
3. Add filtering by scope verdict
4. Add scope violation alerts

### Phase 5: Testing & Polish (Day 5)

**Tasks:**
1. Integration tests with real OpenCode sessions
2. Performance testing (scope analysis overhead)
3. Documentation
4. Edge case handling

---

## 4. Configuration

### 4.1 User Configuration (Future)

```yaml
# ~/.config/opencode-status-bar/scope.yaml
scope:
  # Additional allowed paths (e.g., monorepo siblings)
  allowed_paths:
    - ~/Projects/shared-libs/
    - ~/Projects/common-config/
  
  # Paths to always flag (company-specific)
  sensitive_paths:
    ~/company-secrets/: 90
    ~/production-keys/: 95
  
  # Disable scope checking for specific sessions
  disabled_sessions: []
```

### 4.2 Default Behavior

| Setting | Default | Description |
|---------|---------|-------------|
| Scope checking | Enabled | Can be disabled per-session |
| Temp paths allowed | Yes | /tmp, .cache always OK |
| Write penalty | +15 | Extra score for write operations |
| Unknown path score | 25 (read), 35 (write) | Base score for generic out-of-scope |

---

## 5. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Out-of-scope detection rate | >95% | Manual review of test sessions |
| False positive rate | <5% | Legitimate accesses flagged |
| Performance overhead | <10ms per part | Benchmark enrichment time |
| Coverage | All tool types | read, write, edit, bash |

---

## 6. Security Considerations

### 6.1 What This Detects

1. **Data exfiltration preparation**: AI reads files from unrelated projects
2. **Config poisoning**: AI modifies shell configs, git config
3. **Credential access**: AI reads SSH keys, AWS credentials (already detected, now with scope context)
4. **Scope creep**: AI gradually accesses more files outside project

### 6.2 What This Doesn't Detect

1. **Malicious access within project**: If attacker controls project files
2. **Network exfiltration**: Covered by existing patterns
3. **Encoded paths**: Base64 encoded paths in commands (future work)

---

## 7. Future Enhancements

### 7.1 Smart Scope Learning

```python
# Learn legitimate cross-project patterns
class ScopeLearner:
    def learn_from_history(self, session_id: str):
        """Analyze past sessions to identify legitimate patterns."""
        # If user frequently accesses ~/shared-config/, auto-allow
```

### 7.2 Project Type Detection

```python
# Detect project type and adjust scope rules
class ProjectTypeDetector:
    def detect(self, project_root: Path) -> ProjectType:
        if (project_root / "package.json").exists():
            return ProjectType.NODE
        if (project_root / "pyproject.toml").exists():
            return ProjectType.PYTHON
        # ...
```

### 7.3 Monorepo Support

```python
# Detect monorepo and allow sibling package access
class MonorepoDetector:
    def get_allowed_siblings(self, project_root: Path) -> List[Path]:
        # Check for lerna.json, pnpm-workspace.yaml, etc.
```

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Too many false positives | Medium | High | Conservative default scores, easy configuration |
| Performance impact | Low | Medium | Efficient path resolution, caching |
| Path resolution edge cases | Medium | Low | Comprehensive test suite |
| User confusion | Medium | Medium | Clear documentation, UI explanations |

---

## 9. Dependencies

- **Plan 42** (Unified Indexing): Required - provides session.working_directory
- **Plan 43** (Security Heuristics): Optional - complements pattern-based detection

---

## 10. Open Questions

1. **Should we track "scope violations over time"?** Could indicate gradual scope creep attack
2. **Should we integrate with git to understand repo boundaries?** More accurate for monorepos
3. **Should we allow user to mark false positives?** Learning from user feedback
4. **Should out-of-scope access require confirmation?** Real-time blocking vs post-hoc alerting

---

## Appendix A: Complete File List

```
src/opencode_status_bar/security/scope/
├── __init__.py
├── analyzer.py          # ScopeAnalyzer class
├── path_extractor.py    # Extract paths from commands
├── config.py            # Configuration handling
└── verdicts.py          # ScopeVerdict enum and ScopeResult

tests/
├── test_scope_analyzer.py
├── test_path_extractor.py
└── test_scope_integration.py
```

---

## Appendix B: Example Scenarios

### Scenario 1: Normal Development

```
Project: ~/Projects/my-app/
Actions:
  - read ./src/main.py        → IN_SCOPE (score: 0)
  - write ./src/utils.py      → IN_SCOPE (score: 0)
  - bash "npm install"        → IN_SCOPE (score: 0)
  - read ./package.json       → IN_SCOPE (score: 0)
```

### Scenario 2: Suspicious Activity

```
Project: ~/Projects/my-app/
Actions:
  - read ~/.ssh/id_rsa        → OUT_OF_SCOPE_SENSITIVE (score: +80)
  - read ~/.aws/credentials   → OUT_OF_SCOPE_SENSITIVE (score: +75)
  - bash "curl -X POST ..."   → Pattern match (existing detection)
```

### Scenario 3: Scope Creep

```
Project: ~/Projects/my-app/
Actions:
  - read ./src/main.py        → IN_SCOPE (score: 0)
  - read ~/other-project/db.py → OUT_OF_SCOPE_NEUTRAL (score: +25)
  - read ~/Downloads/script.sh → OUT_OF_SCOPE_SUSPICIOUS (score: +50)
  - write ~/.bashrc           → OUT_OF_SCOPE_SENSITIVE (score: +75)
```

---

**Document End**
