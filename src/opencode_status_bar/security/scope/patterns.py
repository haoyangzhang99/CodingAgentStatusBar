"""
Scope Patterns - Path patterns for scope-aware security analysis.

Provides categorized path patterns with associated risk scores:
- ALLOWED_PATHS: Safe locations that don't require penalty
- SUSPICIOUS_PATHS: Potentially concerning locations
- SENSITIVE_PATHS: Security-critical locations requiring high scrutiny

Score Modifiers:
- Read operations use base scores
- Write operations add +10-15 penalty depending on sensitivity
"""

from typing import Dict, List, Tuple


# Allowed paths - no score penalty for accessing these
# Format: (pattern, reason)
# These are common development/system paths that are expected to be accessed
ALLOWED_PATHS: List[Tuple[str, str]] = [
    # Temporary directories
    ("/tmp/", "System temp directory"),
    ("/var/tmp/", "System temp directory"),
    ("/private/tmp/", "macOS temp directory"),
    # macOS uses /var/folders/xx/yyyy/T/ for temp - match the /T/ indicator
    ("/T/", "macOS temp directory"),
    # User cache directories
    ("/.cache/", "User cache directory"),
    ("/.local/share/", "XDG local share"),
    ("/.local/state/", "XDG local state"),
    # Package manager caches
    ("/.npm/", "NPM cache"),
    ("/.yarn/", "Yarn cache"),
    ("/.pnpm-store/", "PNPM store"),
    ("/.cargo/registry/", "Cargo registry cache"),
    ("/.cargo/git/", "Cargo git cache"),
    ("/.m2/repository/", "Maven repository cache"),
    ("/.gradle/caches/", "Gradle cache"),
    ("/.nuget/", "NuGet cache"),
    ("/.pub-cache/", "Dart pub cache"),
    # Python caches
    ("/.pyenv/", "Pyenv directory"),
    ("/.virtualenvs/", "Virtualenvwrapper"),
    ("/.uv/", "UV cache"),
    ("/.rye/", "Rye directory"),
    # Node version managers
    ("/.nvm/", "NVM directory"),
    ("/.fnm/", "FNM directory"),
    ("/.volta/", "Volta directory"),
    # Development tools
    ("/.vscode-server/", "VSCode remote server"),
    ("/.cursor-server/", "Cursor remote server"),
    # Build outputs (commonly accessed)
    ("/node_modules/", "Node modules"),
    ("/__pycache__/", "Python cache"),
    ("/.pytest_cache/", "Pytest cache"),
    ("/.mypy_cache/", "Mypy cache"),
    ("/.ruff_cache/", "Ruff cache"),
    ("/dist/", "Distribution directory"),
    ("/build/", "Build directory"),
    ("/target/", "Target directory (Rust/Maven)"),
]


# Suspicious paths - moderate penalty for accessing these
# Format: (pattern, base_score, reason)
# These are locations that might indicate concerning behavior
SUSPICIOUS_PATHS: List[Tuple[str, int, str]] = [
    # User data directories
    ("/Downloads/", 50, "Downloads directory - common malware location"),
    ("/Desktop/", 40, "Desktop directory - user data"),
    ("/Documents/", 40, "Documents directory - user data"),
    ("/Pictures/", 35, "Pictures directory - user data"),
    ("/Videos/", 35, "Videos directory - user data"),
    ("/Music/", 35, "Music directory - user data"),
    # System directories
    ("/usr/", 40, "System binaries directory"),
    ("/usr/local/", 35, "Local system directory"),
    ("/opt/", 35, "Optional software directory"),
    ("/var/", 40, "Variable data directory"),
    ("/var/log/", 45, "System logs - potential information disclosure"),
    # Application directories
    ("/Applications/", 45, "macOS Applications - could modify apps"),
    ("/Library/", 40, "macOS Library directory"),
    ("/.Trash/", 40, "Trash directory - data recovery concerns"),
    # Other users
    ("/Users/", 50, "Other user directories"),
    ("/home/", 50, "Other user home directories"),
]


# Sensitive paths - high penalty for accessing these
# Format: (pattern, base_score, reason)
# These are security-critical locations that should rarely be accessed
SENSITIVE_PATHS: List[Tuple[str, int, str]] = [
    # SSH and keys
    ("/.ssh/", 80, "SSH directory - authentication keys"),
    ("/id_rsa", 85, "SSH private key"),
    ("/id_ed25519", 85, "SSH private key"),
    ("/id_ecdsa", 85, "SSH private key"),
    ("/id_dsa", 85, "SSH private key (legacy)"),
    ("/.gnupg/", 80, "GPG directory - encryption keys"),
    # Cloud credentials
    ("/.aws/", 75, "AWS credentials"),
    ("/.aws/credentials", 85, "AWS credentials file"),
    ("/.azure/", 70, "Azure credentials"),
    ("/.config/gcloud/", 75, "GCP credentials"),
    ("/.kube/config", 75, "Kubernetes config"),
    ("/.docker/config.json", 70, "Docker credentials"),
    # Shell configuration - persistence vectors
    ("/.bashrc", 60, "Bash config - persistence vector"),
    ("/.bash_profile", 60, "Bash profile - persistence vector"),
    ("/.zshrc", 60, "Zsh config - persistence vector"),
    ("/.zprofile", 60, "Zsh profile - persistence vector"),
    ("/.profile", 60, "Shell profile - persistence vector"),
    # System configuration
    ("/etc/", 65, "System configuration directory"),
    ("/etc/passwd", 70, "System user database"),
    ("/etc/shadow", 95, "System password hashes"),
    ("/etc/sudoers", 85, "Sudo configuration"),
    ("/etc/hosts", 65, "Hosts file - DNS override"),
    # Secrets and tokens
    ("/.netrc", 75, "Network credentials"),
    ("/.pgpass", 70, "PostgreSQL credentials"),
    ("/.my.cnf", 70, "MySQL credentials"),
    ("/.npmrc", 65, "NPM config with tokens"),
    ("/.pypirc", 65, "PyPI config with tokens"),
    (".env", 70, "Environment file with secrets"),
    # History files - information disclosure
    ("/.bash_history", 60, "Bash history - information disclosure"),
    ("/.zsh_history", 60, "Zsh history - information disclosure"),
    ("/.python_history", 55, "Python history"),
    # Browser data
    ("/Cookies", 65, "Browser cookies"),
    ("/Login Data", 75, "Browser saved passwords"),
    ("/History", 55, "Browser history"),
    # macOS specific
    ("/Library/Keychains/", 85, "macOS Keychain - credentials"),
    ("/.keychain", 80, "Keychain files"),
    ("/Library/LaunchDaemons/", 80, "macOS system daemons - persistence"),
    ("/Library/LaunchAgents/", 75, "macOS launch agents - persistence"),
    ("~/Library/LaunchAgents/", 70, "User launch agents - persistence"),
]


# Write penalty additions by path category
WRITE_PENALTIES: Dict[str, int] = {
    "suspicious": 10,  # Additional penalty for writes to suspicious paths
    "sensitive": 15,  # Additional penalty for writes to sensitive paths
}
