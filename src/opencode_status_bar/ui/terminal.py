"""
Terminal Focus - AppleScript to focus iTerm2 on a specific TTY
"""

import subprocess  # nosec B404 - required for AppleScript execution
from ..utils.logger import error


def focus_iterm2(tty: str) -> bool:
    """Focus iTerm2 on the given TTY

    Args:
        tty: The TTY path (e.g., "ttys001" or "/dev/ttys001")

    Returns:
        True if successful, False otherwise
    """
    tty_path = f"/dev/{tty}" if not tty.startswith("/dev/") else tty

    script = f'''
        on run
            set searchTerm to "{tty_path}"
            tell application "iTerm2"
                activate
                repeat with w in windows
                    repeat with t in tabs of w
                        try
                            set s to current session of t
                            if (tty of s) is equal to searchTerm then
                                select t
                                select w
                                return
                            else if name of s contains searchTerm then
                                select t
                                select w
                                return
                            end if
                        end try
                    end repeat
                end repeat
            end tell
        end run
    '''

    try:
        subprocess.run(  # nosec B603 B607 - trusted AppleScript execution
            ["osascript", "-e", script], capture_output=True, timeout=5
        )
        return True
    except (
        Exception
    ) as e:  # Intentional catch-all: AppleScript failures logged and return False
        error(f"Focus terminal failed: {e}")
        return False
