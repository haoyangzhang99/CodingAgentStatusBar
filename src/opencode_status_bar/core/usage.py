"""
Anthropic API usage monitoring
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from .models import Usage, UsagePeriod

AUTH_FILE = os.path.expanduser("~/.local/share/opencode/auth.json")
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"


def read_auth_token() -> Optional[str]:
    """Read OAuth token from opencode auth file"""
    try:
        with open(AUTH_FILE, "r") as f:
            auth = json.load(f)
            return auth.get("anthropic", {}).get("access")
    except Exception:  # Intentional catch-all: missing/invalid auth file returns None
        return None


def fetch_usage() -> Usage:
    """Fetch usage data from Anthropic API"""
    token = read_auth_token()

    if not token:
        return Usage(error="No auth token found")

    try:
        req = urllib.request.Request(USAGE_API_URL)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("anthropic-beta", "oauth-2025-04-20")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as response:  # nosec B310
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return Usage(error="Token expired")
        return Usage(error=f"HTTP {e.code}")
    except Exception as e:  # Intentional catch-all: network errors return error state
        return Usage(error=str(e))

    # Parse usage data
    try:
        if not isinstance(data, dict):
            return Usage(error="API unavailable")

        five_hour_data = data.get("five_hour")
        seven_day_data = data.get("seven_day")

        # API returns null values when unavailable
        if five_hour_data is None and seven_day_data is None:
            return Usage(error="API unavailable")

        five_hour = UsagePeriod(
            utilization=int((five_hour_data or {}).get("utilization", 0)),
            resets_at=(five_hour_data or {}).get("resets_at"),
        )
        seven_day = UsagePeriod(
            utilization=int((seven_day_data or {}).get("utilization", 0)),
            resets_at=(seven_day_data or {}).get("resets_at"),
        )
        return Usage(five_hour=five_hour, seven_day=seven_day)
    except Exception:  # Intentional catch-all: malformed API response
        return Usage(error="API unavailable")
