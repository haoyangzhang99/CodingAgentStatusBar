import asyncio
import subprocess  # nosec B404 - required for port/TTY detection

from ..client import check_opencode_port
from ...utils.logger import info


_last_seen_ports: set[int] = set()


async def find_opencode_ports() -> list[int]:
    try:
        result = subprocess.run(  # nosec B603 B607 - trusted system command
            ["netstat", "-an"], capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.split("\n")
    except Exception:
        return []

    candidate_ports = set()
    for line in lines:
        if "127.0.0.1" in line and "LISTEN" in line:
            parts = line.split()
            for part in parts:
                if part.startswith("127.0.0.1."):
                    try:
                        port = int(part.split(".")[-1])
                        if 1024 < port < 65535:
                            candidate_ports.add(port)
                    except ValueError:
                        continue

    check_tasks = [check_opencode_port(port) for port in candidate_ports]
    results = await asyncio.gather(*check_tasks)

    opencode_ports = [
        port for port, is_opencode in zip(candidate_ports, results) if is_opencode
    ]

    global _last_seen_ports
    current_ports = set(opencode_ports)
    if current_ports != _last_seen_ports:
        info(f"[Ports] OpenCode instances changed: {len(opencode_ports)} active")
        _last_seen_ports = current_ports

    return opencode_ports


def get_tty_for_port(port: int) -> str:
    """Get the TTY associated with an OpenCode instance"""
    try:
        result = subprocess.run(  # nosec B603 B607 - trusted system command
            ["lsof", "-i", f":{port}"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "opencode" in line.lower() and "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[1]
                    # Get TTY from ps
                    ps_result = subprocess.run(  # nosec B603 B607 - trusted command
                        ["ps", "-o", "tty=", "-p", pid],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    tty = ps_result.stdout.strip()
                    if tty and tty != "??":
                        return tty
    except Exception:
        pass  # nosec B110 - TTY detection is best-effort
    return ""
