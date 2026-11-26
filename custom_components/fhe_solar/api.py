from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp

from .const import API_BASE

class FheSolarApi:
    def __init__(self, session: aiohttp.ClientSession):
        self._session = session
        self._token: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token

    async def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        url = f"{API_BASE}/signIn"
        payload = {"email": email, "password": password}
        async with asyncio.timeout(20):
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Login failed ({resp.status}): {text}")
                data = await resp.json()
                token = data.get("token")
                if not token:
                    raise RuntimeError("Login response missing token")
                self._token = token
                return data

    async def get_home(self, home_id: int) -> Dict[str, Any]:
        if not self._token:
            raise RuntimeError("No token set")
        url = f"{API_BASE}/homes/{home_id}"
        headers = {"Authorization": f"Bearer {self._token}"}
        async with asyncio.timeout(20):
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    raise PermissionError("Unauthorized")
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Home fetch failed ({resp.status}): {text}")
                return await resp.json()