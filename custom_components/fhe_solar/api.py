from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import aiohttp

from .const import API_BASE


class FheSolarApiError(Exception):
    """Base error for the FHE Solar API."""


class FheSolarAuthError(FheSolarApiError, PermissionError):
    """Credentials or token rejected by the API.

    Observed responses (own test 2026-11-26, see RESULTS.md):
    - POST /signIn with wrong password -> 400 {"message":"Invalid username or password"}
    - GET /homes/{id} with invalid token -> 401 {"message":"Failed to authenticate token"}
    Subclasses PermissionError to stay compatible with existing callers.
    """


class FheSolarConnectionError(FheSolarApiError):
    """The API could not be reached (network error or timeout)."""


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
        try:
            async with asyncio.timeout(20):
                async with self._session.post(url, json=payload) as resp:
                    if resp.status in (400, 401, 403):
                        raise FheSolarAuthError(f"Login rejected ({resp.status})")
                    if resp.status != 200:
                        text = await resp.text()
                        raise FheSolarApiError(f"Login failed ({resp.status}): {text}")
                    data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FheSolarConnectionError(str(err)) from err
        token = data.get("token")
        if not token:
            raise FheSolarApiError("Login response missing token")
        self._token = token
        return data

    async def get_home(self, home_id: int) -> Dict[str, Any]:
        if not self._token:
            raise FheSolarAuthError("No token set")
        url = f"{API_BASE}/homes/{home_id}"
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(20):
                async with self._session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        raise FheSolarAuthError("Unauthorized")
                    if resp.status != 200:
                        text = await resp.text()
                        raise FheSolarApiError(f"Home fetch failed ({resp.status}): {text}")
                    return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise FheSolarConnectionError(str(err)) from err
