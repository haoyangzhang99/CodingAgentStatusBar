"""
Security Analyzer Patterns - Detection patterns for security analysis

Provides:
- DANGEROUS_PATTERNS: Patterns for risky command detection
- SAFE_PATTERNS: Patterns that reduce risk scores
- SENSITIVE_FILE_PATTERNS: Patterns for sensitive file detection
- SENSITIVE_URL_PATTERNS: Patterns for sensitive URL detection

MITRE ATT&CK Technique IDs:
- T1059 - Command and Scripting Interpreter
- T1048 - Exfiltration Over Alternative Protocol
- T1070 - Indicator Removal
- T1222 - File and Directory Permissions Modification
- T1105 - Ingress Tool Transfer
- T1053 - Scheduled Task/Job
- T1087 - Account Discovery
- T1082 - System Information Discovery
- T1485 - Data Destruction
- T1548 - Abuse Elevation Control Mechanism
"""

from typing import Dict, List, Tuple


# Pattern definitions with base scores and MITRE techniques
# Format: (pattern, score, reason, context_adjustments, mitre_techniques)
DANGEROUS_PATTERNS = [
    # === CRITICAL (80-100) ===
    (
        r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/",
        95,
        "Recursive delete from root",
        [],
        ["T1485", "T1070"],  # Data Destruction, Indicator Removal
    ),
    (
        r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+)?-[a-zA-Z]*f[a-zA-Z]*\s+/",
        95,
        "Forced recursive delete from root",
        [],
        ["T1485", "T1070"],
    ),
    (r"\brm\s+-rf\s+/\s*$", 100, "Delete entire filesystem", [], ["T1485"]),
    (r"\brm\s+-rf\s+/[a-z]+\s*$", 90, "Delete system directory", [], ["T1485"]),
    (r"\brm\s+-rf\s+~\s*$", 85, "Delete home directory", [], ["T1485"]),
    (
        r"curl\s+[^|]*\|\s*(ba)?sh",
        95,
        "Remote code execution via curl",
        [],
        ["T1059", "T1105"],
    ),
    (
        r"wget\s+[^|]*\|\s*(ba)?sh",
        95,
        "Remote code execution via wget",
        [],
        ["T1059", "T1105"],
    ),
    (r"curl\s+[^|]*\|\s*python", 90, "Remote Python execution", [], ["T1059", "T1105"]),
    (r'eval\s+"\$\(curl', 95, "Eval remote code", [], ["T1059", "T1105"]),
    (r"source\s+<\(curl", 95, "Source remote script", [], ["T1059", "T1105"]),
    (r"\bdd\s+.*of=/dev/", 90, "Direct disk write", [], ["T1485"]),
    (r"\bmkfs\.", 85, "Filesystem format", [], ["T1485"]),
    # === HIGH (50-79) ===
    (
        r"\bsudo\s+",
        55,
        "Privilege escalation",
        [
            (r"sudo\s+(brew|apt|yum|dnf|pacman)\s+install", -20),
            (r"sudo\s+rm\s+-rf", 30),
        ],
        ["T1548"],  # Abuse Elevation Control Mechanism
    ),
    (r"\bsu\s+-", 60, "Switch to root user", [], ["T1548"]),
    (r"\bdoas\s+", 55, "Privilege escalation (doas)", [], ["T1548"]),
    (r"\bchmod\s+777", 70, "World-writable permissions", [], ["T1222"]),
    (r"\bchmod\s+-R\s+777", 80, "Recursive world-writable", [], ["T1222"]),
    (r"\bchmod\s+[0-7]*[67][0-7]{2}", 50, "Permissive chmod", [], ["T1222"]),
    (r"\bchown\s+-R\s+root", 65, "Recursive chown to root", [], ["T1222"]),
    (r"git\s+push\s+.*--force.*\s+(main|master)\b", 85, "Force push to main", [], []),
    (
        r"git\s+push\s+.*--force",
        55,
        "Force push",
        [
            (r"--force.*origin\s+(main|master)", 30),
        ],
        [],
    ),
    (r"git\s+reset\s+--hard", 60, "Hard reset", [], ["T1070"]),
    (r"git\s+clean\s+-fd", 55, "Clean untracked files", [], ["T1070"]),
    (r"git\s+checkout\s+--\s+\.", 50, "Discard all changes", [], []),
    (r"\bDROP\s+(DATABASE|TABLE|SCHEMA)\b", 80, "SQL DROP operation", [], ["T1485"]),
    (r"\bTRUNCATE\s+TABLE\b", 75, "SQL TRUNCATE", [], ["T1485"]),
    (r"\bDELETE\s+FROM\s+\w+\s*;", 70, "DELETE without WHERE", [], ["T1485"]),
    (r"\bDELETE\s+FROM\s+\w+\s+WHERE", 40, "DELETE with WHERE", [], []),
    (r"\bUPDATE\s+\w+\s+SET\s+.*;\s*$", 60, "UPDATE without WHERE", [], []),
    (r"\bkill\s+-9", 50, "Force kill process", [], ["T1489"]),  # Service Stop
    (r"\bkillall\s+", 55, "Kill all matching processes", [], ["T1489"]),
    (r"\bpkill\s+-9", 55, "Force pkill", [], ["T1489"]),
    # === MEDIUM (20-49) ===
    (
        r"\b(rm|mv|cp)\s+.*(/etc/|/usr/|/var/|/boot/)",
        45,
        "Operation on system directory",
        [],
        [],
    ),
    (r"\becho\s+.*>\s*/etc/", 50, "Write to /etc/", [], ["T1222"]),
    (r"\brm\s+-rf\s+\*", 45, "Recursive delete with wildcard", [], ["T1070"]),
    # rm -rf with context-aware scoring: safe contexts reduce score significantly
    (
        r"\brm\s+-rf\s+(?!.*(?:/\s*$|/\*\s*$))\S+",
        70,
        "Recursive force delete",
        [
            # Safe context adjustments - development artifacts
            # Why safe: temp directories are designed for ephemeral data
            (r"/tmp/|/var/tmp/|\.cache/", -40),
            # Why safe: node_modules is frequently cleaned in JS development
            (r"node_modules", -50),
            # Why safe: Python cache directories are auto-generated
            (r"__pycache__|\.pytest_cache", -45),
            # Why safe: test data and fixtures are disposable
            (r"test.*data|fixtures|snapshots", -35),
            # Why safe: build output directories are regenerated (with or without trailing slash)
            (r"(?:^|/)(?:build|dist|target|out)(?:/|$)", -40),
            # Why safe: coverage output is regenerated
            (r"\.coverage|htmlcov/|\.nyc_output", -35),
        ],
        ["T1485", "T1070.004"],
    ),
    (r"\brm\s+-rf\s+\.git", 60, "Delete git directory", [], ["T1070"]),
    (r"\brm\s+-rf\s+(dist|build|target|out)\b", 20, "Delete build directory", [], []),
    (r"\bnc\s+-l", 40, "Netcat listener", [], ["T1059"]),
    (r"\bssh\s+-R", 45, "SSH reverse tunnel", [], ["T1572"]),  # Protocol Tunneling
    (r"\biptables\s+", 50, "Firewall modification", [], ["T1562"]),  # Impair Defenses
    (
        r"export\s+PATH=",
        30,
        "PATH modification",
        [],
        ["T1574"],
    ),  # Hijack Execution Flow
    (r"export\s+(AWS|GITHUB|API)_", 35, "Export sensitive env var", [], []),
    (
        r"\bnpm\s+publish",
        40,
        "Publish npm package",
        [],
        ["T1195"],
    ),  # Supply Chain Compromise
    (r"\bpip\s+install\s+--user", 25, "Pip user install", [], []),
    # Additional patterns for MITRE coverage
    (r"\bcrontab\s+", 40, "Crontab modification", [], ["T1053"]),  # Scheduled Task
    (r"\bhistory\s+-c", 50, "Clear command history", [], ["T1070"]),
    (r"\bshred\s+", 45, "Secure file deletion", [], ["T1070"]),
    (
        r"\bcat\s+/etc/passwd",
        30,
        "Read system passwd",
        [],
        ["T1087"],
    ),  # Account Discovery
    (
        r"\b(whoami|id|groups)\b",
        20,
        "User discovery",
        [],
        ["T1033"],
    ),  # System Owner/User Discovery
    (r"\buname\s+-a", 20, "System information", [], ["T1082"]),
    (r"\bcat\s+/proc/", 25, "Read proc filesystem", [], ["T1082"]),
    # === NEW PATTERNS FOR BROADER MITRE COVERAGE ===
    # T1560 - Archive Collected Data
    (r"\btar\s+.*-[a-z]*c[a-z]*f", 25, "Create tar archive", [], ["T1560"]),
    (r"\bzip\s+-r", 25, "Create zip archive recursively", [], ["T1560"]),
    (r"\bgzip\s+", 20, "Compress file", [], ["T1560"]),
    (r"\b7z\s+a\b", 25, "Create 7zip archive", [], ["T1560"]),
    # T1132 - Data Encoding / T1140 - Deobfuscate
    (r"\bbase64\s+[^-]", 30, "Base64 encode", [], ["T1132"]),
    (r"\bbase64\s+-d", 35, "Base64 decode", [], ["T1140"]),
    (r"\bopenssl\s+(enc|dec)", 35, "OpenSSL encrypt/decrypt", [], ["T1140"]),
    (r"\bxxd\s+", 25, "Hex dump/undump", [], ["T1132"]),
    # T1046 - Network Service Discovery
    (r"\bnmap\s+", 45, "Network port scan", [], ["T1046"]),
    (r"\bnetstat\s+-", 25, "Network connections", [], ["T1046", "T1016"]),
    (r"\bss\s+-[a-z]*l", 25, "Socket statistics", [], ["T1046"]),
    # T1016 - System Network Configuration Discovery
    (r"\bifconfig\b", 20, "Network interface config", [], ["T1016"]),
    (r"\bip\s+(addr|route|link)", 20, "IP configuration", [], ["T1016"]),
    (r"\bcat\s+/etc/(hosts|resolv)", 25, "Read network config", [], ["T1016"]),
    # T1057 - Process Discovery
    (r"\bps\s+(aux|ef)", 20, "Process listing", [], ["T1057"]),
    (r"\btop\s+-b", 20, "Batch process listing", [], ["T1057"]),
    (r"\blsof\s+", 25, "List open files", [], ["T1057"]),
    # T1083 - File and Directory Discovery
    (r"\bfind\s+/\s+-name", 25, "Find from root", [], ["T1083"]),
    (r"\bfind\s+.*-type\s+f.*-exec", 35, "Find with exec", [], ["T1083", "T1119"]),
    (r"\blocate\s+", 20, "Locate files", [], ["T1083"]),
    # T1555 - Credentials from Password Stores
    (
        r"\bsecurity\s+find-(generic|internet)-password",
        60,
        "macOS Keychain access",
        [],
        ["T1555"],
    ),
    (r"\bkeychain\b", 40, "Keychain access", [], ["T1555"]),
    (r"\bpass\s+(show|ls)", 50, "Password store access", [], ["T1555"]),
    (r"\bgpg\s+--decrypt", 40, "GPG decrypt", [], ["T1555"]),
    # T1539 - Steal Web Session Cookie
    (r"Cookies\.sqlite", 50, "Browser cookies file", [], ["T1539"]),
    (r"cookies\.json", 45, "Cookies JSON file", [], ["T1539"]),
    (r"\.cookie", 40, "Cookie file", [], ["T1539"]),
    # T1119 - Automated Collection
    (r"\brsync\s+.*-a", 30, "Rsync archive mode", [], ["T1119"]),
    (r"\bscp\s+-r", 30, "Recursive SCP", [], ["T1119", "T1048"]),
    # T1003 - OS Credential Dumping
    (r"/etc/shadow", 70, "Shadow file access", [], ["T1003"]),
    (r"\.docker/config\.json", 50, "Docker credentials", [], ["T1552"]),
    (r"\.kube/config", 50, "Kubernetes config", [], ["T1552"]),
    # T1562 - Impair Defenses
    (r"\bsystemctl\s+(stop|disable)", 40, "Stop/disable service", [], ["T1562"]),
    (r"\blaunchctl\s+unload", 40, "Unload launch agent", [], ["T1562"]),
    (r"\bsetenforce\s+0", 60, "Disable SELinux", [], ["T1562"]),
    # T1497 - Sandbox/VM Detection (potential evasion)
    (r"\bdmesg\s+\|.*grep.*(vmware|virtual|vbox)", 35, "VM detection", [], ["T1497"]),
    (r"\bsystemd-detect-virt", 30, "Virtualization detection", [], ["T1497"]),
    # === AI-SPECIFIC PATTERNS ===
    # Prompt Injection Indicators
    (
        r"#\s*Base64:\s*[A-Za-z0-9+/=]{10,}",
        85,
        "Encoded instruction in comment",
        [],
        ["T1027"],
    ),
    (
        r'["\'].*(?:curl|wget|rm|sudo|chmod).*\|.*sh["\']',
        70,
        "Shell command in string literal",
        [],
        ["T1059.004"],
    ),
    (
        r"\\x[0-9a-fA-F]{2}(?:\\x[0-9a-fA-F]{2}){4,}",
        60,
        "Hex-encoded payload",
        [],
        ["T1027"],
    ),
    (
        r"(?i)ignore.*previous.*instruction",
        90,
        "Prompt injection - ignore instructions",
        [],
        ["T1059"],
    ),
    (
        r"(?i)system.*prompt",
        85,
        "Prompt injection - system prompt reference",
        [],
        ["T1059"],
    ),
    (r"(?i)do.*not.*follow.*safety", 95, "Safety bypass attempt", [], ["T1059"]),
    # === EVASION DETECTION PATTERNS ===
    # Base64/Encoding Evasion
    (r"\bbase64\s+-d\s+<<<", 75, "Base64 decode execution", [], ["T1027", "T1140"]),
    (r"\bbase64\s+-d\s*\|", 80, "Base64 pipe to execution", [], ["T1027", "T1140"]),
    (
        r"\becho\s+[A-Za-z0-9+/=]{20,}\s*\|\s*base64\s+-d",
        85,
        "Encoded command decode",
        [],
        ["T1027"],
    ),
    (r"\bprintf\s+['\"]\\\\x[0-9a-fA-F]", 70, "Printf hex decode", [], ["T1027"]),
    # Variable/Command Substitution Evasion
    (r"\$\([^)]+\)\s+-rf\s+/", 85, "Subshell command to rm -rf", [], ["T1059.004"]),
    (r"\$\{[^}]+\}\s+-rf\s+/", 85, "Variable expansion to rm -rf", [], ["T1059.004"]),
    (
        r"eval\s+[\"'].*(?:rm|curl|wget|chmod)",
        90,
        "Eval with dangerous command",
        [],
        ["T1059.004"],
    ),
    # === NEW MITRE TECHNIQUE PATTERNS ===
    # T1136 - Create Account
    (r"\buseradd\s+", 70, "User account creation", [], ["T1136.001"]),
    (r"\badduser\s+", 70, "User account creation", [], ["T1136.001"]),
    (r"\bdscl\s+.*create.*Users", 75, "macOS user creation", [], ["T1136.001"]),
    # T1543 - Create or Modify System Process
    (r"\bsystemctl\s+enable\s+", 65, "Enable system service", [], ["T1543.002"]),
    (r"\blaunchctl\s+load\s+", 70, "Load macOS launch daemon", [], ["T1543.001"]),
    (r"/Library/LaunchDaemons/", 70, "macOS system daemon", [], ["T1543.001"]),
    # T1547 - Boot or Logon Autostart Execution
    (
        r"\.bashrc|\.bash_profile|\.zshrc|\.profile",
        50,
        "Shell startup file",
        [],
        ["T1547.004"],
    ),
    (r"/etc/rc\.local", 75, "rc.local persistence", [], ["T1547.004"]),
    (r"HKEY_.*\\\\Run", 80, "Windows registry run key", [], ["T1547.001"]),
    # T1567 - Exfiltration Over Web Service
    (
        r"\baws\s+s3\s+cp\s+.*--acl\s+public",
        85,
        "S3 upload with public ACL",
        [],
        ["T1567.002"],
    ),
    (r"\bgcloud\s+.*storage\s+.*cp\s+", 60, "GCS upload", [], ["T1567.002"]),
    (r"\brclone\s+(?:copy|sync)\s+", 65, "Rclone cloud sync", [], ["T1567.002"]),
    # T1611 - Escape to Host (Container Escape)
    (r"docker\s+run\s+.*--privileged", 85, "Privileged container run", [], ["T1611"]),
    (r"docker\s+.*-v\s+/:/", 90, "Docker mount root filesystem", [], ["T1611"]),
    (
        r"kubectl\s+exec\s+.*--\s+.*chroot",
        95,
        "Kubernetes container escape",
        [],
        ["T1611"],
    ),
    # === PHASE 4: REMAINING MITRE TECHNIQUE PATTERNS ===
    # T1550 - Use Alternate Authentication Material
    (r"\boauth_token\b|oauth2_token", 55, "OAuth token reference", [], ["T1550.001"]),
    (r"\bjwt[_\s]*token", 50, "JWT token reference", [], ["T1550.001"]),
    # Bearer token: case-insensitive, matches JWT format (xxx.yyy.zzz or just xxx.yyy)
    (
        r"(?i)\bbearer\s+[A-Za-z0-9\-_=]+",
        60,
        "Bearer token pattern",
        [],
        ["T1550.001"],
    ),
    (r"\brefresh[_\s]*token", 55, "Refresh token reference", [], ["T1550.001"]),
    (r"\baccess[_\s]*token\s*=", 50, "Access token assignment", [], ["T1550.001"]),
    # T1556 - Modify Authentication Process
    (r"/etc/pam\.d/", 75, "PAM configuration access", [], ["T1556.003"]),
    (r"/etc/sudoers", 80, "Sudoers file access", [], ["T1556", "T1548.003"]),
    (r"\bvisudo\b", 70, "Editing sudoers", [], ["T1556"]),
    # PAM module patterns - matches within quotes or directly
    (r"pam_unix\.so|pam_permit\.so", 80, "PAM module manipulation", [], ["T1556.003"]),
    (
        r"auth\s+sufficient\s+pam_permit",
        90,
        "PAM bypass configuration",
        [],
        ["T1556.003"],
    ),
    # T1564 - Hide Artifacts (additional patterns)
    # setfattr with user.hidden extended attribute (note: proper escape of dot)
    (
        r"\bsetfattr\b.*user\.hidden",
        55,
        "Extended attribute hiding",
        [],
        ["T1564.001"],
    ),
    (r"\bxattr\b.*hidden", 50, "macOS extended attribute", [], ["T1564.001"]),
    (r"attrib\s+\+[hs]", 55, "Windows hidden/system attribute", [], ["T1564.001"]),
    # T1571 - Non-Standard Port
    (r"curl\s+.*:\d{5,}", 45, "Curl to high port number", [], ["T1571"]),
    (r"wget\s+.*:\d{5,}", 45, "Wget to high port number", [], ["T1571"]),
    (r"nc\s+.*\s+[3-6]\d{4}\b", 55, "Netcat to non-standard port", [], ["T1571"]),
    (r"ssh\s+.*-p\s*[3-6]\d{4}", 50, "SSH to non-standard port", [], ["T1571"]),
    # T1573 - Encrypted Channel
    (r"\bopenssl\s+s_client", 55, "OpenSSL client connection", [], ["T1573.002"]),
    (r"\bopenssl\s+s_server", 65, "OpenSSL server (potential C2)", [], ["T1573.002"]),
    (r"stunnel\s+", 60, "SSL tunnel", [], ["T1573.002"]),
    # socat SSL - matches ssl: anywhere in command (case-insensitive)
    (r"(?i)\bsocat\b.*\bssl:", 65, "Socat SSL connection", [], ["T1573.002"]),
    # T1578 - Modify Cloud Compute Infrastructure
    (
        r"\baws\s+ec2\s+(?:run-instances|terminate|modify)",
        65,
        "AWS EC2 modification",
        [],
        ["T1578.002"],
    ),
    (
        r"\bgcloud\s+compute\s+instances\s+(?:create|delete)",
        65,
        "GCP compute modification",
        [],
        ["T1578.002"],
    ),
    # Azure VM - matches az vm create/delete with flexible spacing
    (
        r"\baz\s+vm\s+(?:create|delete)\b",
        65,
        "Azure VM modification",
        [],
        ["T1578.002"],
    ),
    (
        r"\baws\s+lambda\s+(?:create|update|delete)-function",
        60,
        "AWS Lambda modification",
        [],
        ["T1578"],
    ),
    # T1583 - Acquire Infrastructure
    (
        r"\baws\s+route53\s+(?:create|change)",
        55,
        "AWS Route53 modification",
        [],
        ["T1583.001"],
    ),
    (
        r"\bgcloud\s+dns\s+(?:record-sets|managed-zones)",
        55,
        "GCP DNS modification",
        [],
        ["T1583.001"],
    ),
    (r"\baz\s+network\s+dns", 55, "Azure DNS modification", [], ["T1583.001"]),
    (r"\bwhois\s+", 25, "Domain lookup", [], ["T1583.001"]),
    # T1619 - Cloud Storage Object Discovery
    (r"\baws\s+s3\s+ls\b", 40, "S3 bucket listing", [], ["T1619"]),
    (r"\baws\s+s3api\s+list-objects", 45, "S3 object listing API", [], ["T1619"]),
    (r"\bgsutil\s+ls\b", 40, "GCS bucket listing", [], ["T1619"]),
    (r"\baz\s+storage\s+blob\s+list", 40, "Azure blob listing", [], ["T1619"]),
    (r"\baws\s+s3\s+cp\s+s3://", 35, "S3 download", [], ["T1619", "T1530"]),
    # T1530 - Data from Cloud Storage Object
    (r"\baws\s+s3\s+sync\s+s3://", 45, "S3 sync from cloud", [], ["T1530"]),
    (r"\bgsutil\s+cp\s+gs://", 40, "GCS download", [], ["T1530"]),
    (r"\brclone\s+.*:", 45, "Rclone cloud transfer", [], ["T1530"]),
    # T1018 - Remote System Discovery (additional)
    (r"\barp\s+-a", 30, "ARP table enumeration", [], ["T1018"]),
    (r"\bnbtscan\b", 45, "NetBIOS scan", [], ["T1018"]),
    (r"\bsmbclient\s+-L", 45, "SMB share enumeration", [], ["T1018"]),
]

SAFE_PATTERNS = [
    (r"--dry-run", -20, "Dry run mode"),
    (r"--no-preserve-root", 50, "Explicitly dangerous flag"),
    (r"-n\s", -10, "No-execute flag"),
    (r"--help", -50, "Help flag"),
    (r'echo\s+["\']', -10, "Echo command"),
    # Removed /tmp/ rules - dangerous operations in /tmp are still dangerous
    (r"node_modules", -40, "Node modules operation"),
    (r"\.cache/", -40, "Cache directory operation"),
    (r"/build/", -30, "Build directory operation"),
    (r"/dist/", -30, "Dist directory operation"),
    (r"/target/", -30, "Target directory operation"),
    (r"localhost[:/]", -50, "Localhost operation"),
    (r"127\.0\.0\.1[:/]", -50, "Localhost operation"),
    (r"0\.0\.0\.0[:/]", -40, "Local bind"),
    # === DEVELOPER WORKFLOW SAFE PATTERNS ===
    # Package managers
    (r"\b(?:npm|yarn|pnpm)\s+install\s+", -20, "Package manager install"),
    (r"\bpip\s+install\s+", -15, "Python pip install"),
    (r"\bbrew\s+install\s+", -15, "Homebrew install"),
    # Build tools
    (r"\bcargo\s+build\s+", -15, "Rust cargo build"),
    (r"\bgo\s+build\s+", -15, "Go build"),
    (r"\bmake\s+(?:clean|all|test)\s*$", -20, "Standard make targets"),
    # Version control (exclude --force operations)
    (r"\bgit\s+(?:pull|fetch|clone)\s+", -25, "Git operations"),
    (r"\bgit\s+push\s+(?!.*--force)", -25, "Git push without force"),
    # Testing frameworks
    (r"\bpytest\s+", -20, "Running tests"),
    (r"\bjest\s+", -20, "Running tests"),
    # === PHASE 2: FALSE POSITIVE REDUCTION PATTERNS ===
    # Development environment patterns
    # Why safe: virtualenv/venv creation is standard Python dev workflow
    (r"\bvirtualenv\s+|venv\s+", -15, "Python virtualenv creation"),
    # Why safe: sourcing activate scripts is required to use virtual environments
    (r"\bsource\s+.*(?:venv|\.env|activate)", -20, "Activating virtual environment"),
    # Why safe: docker-compose operations are standard container orchestration
    (r"\bdocker-compose\s+(?:up|down|build)\b", -15, "Docker compose operations"),
    # Why safe: kubectl read operations don't modify cluster state
    (r"\bkubectl\s+(?:get|describe|logs)\b", -20, "Kubectl read operations"),
    # Test and CI/CD patterns
    # Why safe: running pytest is a standard testing operation
    (r"\bpython\s+-m\s+pytest\b", -20, "Running pytest"),
    # Why safe: npm test is standard JavaScript testing
    (r"\bnpm\s+(?:run\s+)?test\b", -20, "Running npm test"),
    # Why safe: CI/CD workflow files are configuration, not execution
    (r"\b(?:ci|cd|actions?|workflow)\b.*\byaml\b", -15, "CI/CD workflow file"),
    # Why safe: GitHub Actions directory is standard CI/CD location
    (r"\.github/workflows/", -20, "GitHub Actions path"),
    # Documentation and help
    # Why safe: man pages are read-only documentation lookups
    (r"\bman\s+\w+\b", -25, "Man page lookup"),
    # Why safe: help/version flags are informational only
    (r"\b--help\b|--version\b|-h\b", -30, "Help/version flags"),
    # Why safe: which/type commands only locate executables
    (r"\bwhich\s+\w+\b", -20, "Which command lookup"),
    (r"\btype\s+-a\s+\w+\b", -20, "Type command lookup"),
    # Safe file operations
    # Why safe: reading standard documentation files
    (r"\bcat\s+(?:README|LICENSE|CHANGELOG)", -25, "Reading documentation"),
    # Why safe: file pagers are read-only viewing tools
    (r"\bless\s+|more\s+", -15, "File paging"),
    # Why safe: head with line count is a standard file inspection
    (r"\bhead\s+-n\s*\d+\b", -15, "Head with line count"),
    # Why safe: following log files is standard debugging
    (r"\btail\s+-f\s+.*\.log\b", -20, "Following log files"),
    # Safe network operations
    # Why safe: localhost curl is internal communication only
    (r"\bcurl\s+.*localhost:", -25, "Localhost curl"),
    # Why safe: loopback wget is internal communication only
    (r"\bwget\s+.*127\.0\.0\.1", -25, "Localhost wget"),
    # Why safe: ping with count limit is bounded network check
    (r"\bping\s+-c\s*\d+\s+", -20, "Ping with count limit"),
    # Why safe: DNS lookup is informational network query
    (r"\bnslookup\s+|dig\s+", -15, "DNS lookup"),
    # Path-specific safe patterns for file operations
    # Why safe: node_modules is frequently cleaned/rebuilt in JS projects
    (r"node_modules/", -30, "Node modules directory"),
    # Why safe: Python virtual environments are isolated and disposable
    (r"\.venv/|venv/|virtualenv/", -30, "Python virtual environment"),
    # Why safe: Python cache files are auto-generated and disposable
    (r"__pycache__/|\.pyc$", -25, "Python cache files"),
    # Why safe: Git internal objects are managed by git itself
    (r"\.git/objects/", -25, "Git internal objects"),
    # Why safe: cache directories are designed to be temporary
    (r"\.cache/|cache/", -20, "Cache directories"),
    # Why safe: temporary directories are designed to be ephemeral
    (r"tmp/|temp/|\.tmp/", -20, "Temporary directories"),
]


# File patterns with MITRE techniques
# Format: (pattern, score, reason, mitre_techniques)
SENSITIVE_FILE_PATTERNS: Dict[str, List[Tuple[str, int, str, List[str]]]] = {
    "critical": [
        (r"\.ssh/", 95, "SSH directory", ["T1552"]),  # Unsecured Credentials
        (r"id_rsa", 95, "SSH private key", ["T1552", "T1145"]),  # Private Keys
        (r"id_ed25519", 95, "SSH private key", ["T1552", "T1145"]),
        (r"\.pem$", 90, "PEM certificate/key", ["T1552", "T1145"]),
        (r"\.key$", 90, "Private key file", ["T1552", "T1145"]),
        (r"\.env$", 85, "Environment file", ["T1552"]),
        (r"\.env\.", 85, "Environment file", ["T1552"]),
        (
            r"password",
            85,
            "Password file",
            ["T1552", "T1555"],
        ),  # Credentials from Password Stores
        (r"secret", 85, "Secret file", ["T1552"]),
        (
            r"/etc/shadow",
            100,
            "System shadow file",
            ["T1003", "T1087"],
        ),  # OS Credential Dumping
    ],
    "high": [
        (r"/etc/passwd", 60, "System passwd file", ["T1087"]),  # Account Discovery
        (r"/etc/", 55, "System config", ["T1082"]),  # System Information Discovery
        (r"\.aws/", 70, "AWS credentials", ["T1552"]),
        (r"\.kube/", 65, "Kubernetes config", ["T1552"]),
        (r"credential", 60, "Credentials file", ["T1552"]),
        (r"token", 55, "Token file", ["T1528"]),  # Steal Application Access Token
        (r"\.npmrc", 60, "NPM config with tokens", ["T1552"]),
        (r"\.pypirc", 60, "PyPI config with tokens", ["T1552"]),
        # Additional high-risk patterns
        (r"\.docker/config\.json", 65, "Docker credentials", ["T1552"]),
        (r"\.netrc", 70, "Netrc credentials", ["T1552"]),
        (r"\.pgpass", 65, "PostgreSQL password", ["T1552"]),
        (r"\.my\.cnf", 65, "MySQL config", ["T1552"]),
        (r"Cookies", 55, "Browser cookies", ["T1539"]),
        (r"\.bash_history", 50, "Bash history", ["T1552", "T1083"]),
        (r"\.zsh_history", 50, "Zsh history", ["T1552", "T1083"]),
        (r"known_hosts", 50, "SSH known hosts", ["T1018"]),  # Remote System Discovery
        (
            r"authorized_keys",
            60,
            "SSH authorized keys",
            ["T1098"],
        ),  # Account Manipulation
    ],
    "medium": [
        (r"\.config/", 30, "Config directory", []),
        (r"\.git/config", 40, "Git config", ["T1552"]),
        (r"auth", 35, "Auth-related file", ["T1552"]),
        (r"\.db$", 35, "Database file", ["T1005"]),  # Data from Local System
        (r"\.sqlite", 35, "SQLite database", ["T1005", "T1539"]),
        (r"\.json$", 25, "JSON config", []),
        # Additional medium-risk patterns
        (r"\.log$", 25, "Log file", ["T1005"]),
        (r"backup", 30, "Backup file", ["T1005"]),
        (r"\.bak$", 30, "Backup file", ["T1005"]),
        (r"\.old$", 25, "Old file version", ["T1005"]),
        (r"\.cache/", 25, "Cache directory", ["T1005"]),
        (r"Downloads/", 25, "Downloads directory", ["T1005"]),
        (r"Desktop/", 25, "Desktop directory", ["T1005"]),
        (r"Documents/", 25, "Documents directory", ["T1005"]),
    ],
}

# URL patterns with MITRE techniques
SENSITIVE_URL_PATTERNS: Dict[str, List[Tuple[str, int, str, List[str]]]] = {
    "critical": [
        (
            r"raw\.githubusercontent\.com.*\.sh$",
            90,
            "Shell script from GitHub",
            ["T1059", "T1105"],
        ),
        (r"pastebin\.com", 85, "Pastebin content", ["T1105"]),  # Ingress Tool Transfer
        (r"hastebin", 85, "Hastebin content", ["T1105"]),
        (r"\.(sh|bash|zsh)$", 80, "Shell script download", ["T1059", "T1105"]),
        (r"\.exe$", 95, "Executable download", ["T1105"]),
        # Additional critical URLs
        (r"ngrok\.io", 80, "Ngrok tunnel", ["T1572", "T1090"]),  # Proxy
        (r"webhook\.site", 75, "Webhook testing site", ["T1048"]),  # Exfiltration
        (r"requestbin", 75, "Request capture", ["T1048"]),
    ],
    "high": [
        (r"raw\.githubusercontent\.com", 55, "Raw GitHub content", ["T1105"]),
        (r"gist\.github", 50, "GitHub Gist", ["T1105"]),
        (r"\.py$", 50, "Python script download", ["T1059", "T1105"]),
        (r"\.js$", 50, "JavaScript download", ["T1059"]),
        # Additional high-risk URLs
        (r"\.tar\.gz$", 45, "Archive download", ["T1105", "T1560"]),
        (r"\.zip$", 45, "Zip download", ["T1105", "T1560"]),
        (r"\.deb$", 55, "Debian package", ["T1105"]),
        (r"\.rpm$", 55, "RPM package", ["T1105"]),
        (r"\.pkg$", 55, "macOS package", ["T1105"]),
        (r"\.dmg$", 55, "macOS disk image", ["T1105"]),
        (r"install\.sh", 60, "Install script", ["T1059", "T1105"]),
        (r"setup\.py", 50, "Python setup script", ["T1059"]),
    ],
    "medium": [
        (r"api\.", 25, "API endpoint", []),
        (r"\.json$", 20, "JSON data", []),
        (r"\.xml$", 20, "XML data", []),
        # Additional medium-risk URLs
        (r"\.sql$", 35, "SQL file", ["T1005"]),
        (r"\.csv$", 25, "CSV data", ["T1005"]),
        (r"\.yaml$", 25, "YAML config", []),
        (r"\.toml$", 25, "TOML config", []),
    ],
}
