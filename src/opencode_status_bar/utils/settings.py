"""
Settings management for OpenCode Status Bar
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

CONFIG_DIR = os.path.expanduser("~/.config/opencode-status-bar")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


@dataclass
class Settings:
    """Application settings"""

    # Usage API refresh interval in seconds
    usage_refresh_interval: int = 60

    # Permission detection threshold in seconds
    # Tools running longer than this may be waiting for permission (heuristic)
    permission_threshold_seconds: int = 5

    # Ask user notification timeout in seconds
    # How long to show 🔔 before dismissing (if user hasn't responded)
    ask_user_timeout: int = 30 * 60  # 30 minutes

    def save(self):
        """Save settings to config file"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from config file, or return defaults"""
        if not os.path.exists(CONFIG_FILE):
            return cls()

        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)

            # Filter to only known fields (ignore obsolete settings)
            valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
            filtered_data = {k: v for k, v in data.items() if k in valid_fields}

            return cls(**filtered_data)
        except (
            Exception
        ):  # Intentional catch-all: corrupted settings file returns defaults
            return cls()


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def save_settings():
    """Save the global settings"""
    if _settings is not None:
        _settings.save()
