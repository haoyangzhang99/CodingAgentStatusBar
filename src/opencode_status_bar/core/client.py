"""Async HTTP client for OpenCode API"""

import asyncio
import json
import re
from typing import Optional, Any

import aiohttp

REQUEST_TIMEOUT = 2


def _clean_json(raw: str) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw)


async def get(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[str]:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url) as response:
                return await response.text()
    except Exception:
        return None


async def get_json(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[Any]:
    raw = await get(url, timeout)
    if raw is None:
        return None
    try:
        return json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        return None


async def check_opencode_port(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/session/status"
    result = await get(url, timeout=0.5)
    if result is None:
        return False
    return result == "{}" or result.startswith('{"ses_')


class OpenCodeClient:
    def __init__(self, port: int):
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

    async def get_status(self) -> Optional[dict]:
        return await get_json(f"{self.base_url}/session/status")

    async def get_all_sessions(self) -> Optional[list]:
        return await get_json(f"{self.base_url}/session")

    async def get_session_info(self, session_id: str) -> Optional[dict]:
        return await get_json(f"{self.base_url}/session/{session_id}")

    async def get_session_messages(
        self, session_id: str, limit: int = 1
    ) -> Optional[list]:
        return await get_json(
            f"{self.base_url}/session/{session_id}/message?limit={limit}"
        )

    async def get_session_todos(self, session_id: str) -> Optional[list]:
        return await get_json(f"{self.base_url}/session/{session_id}/todo")

    async def fetch_session_data(self, session_id: str) -> dict:
        info, messages, todos = await asyncio.gather(
            self.get_session_info(session_id),
            self.get_session_messages(session_id, limit=1),
            self.get_session_todos(session_id),
        )
        return {"info": info, "messages": messages, "todos": todos}
