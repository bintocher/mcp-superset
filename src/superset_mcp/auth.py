"""Менеджер аутентификации в Superset — JWT с CSRF и refresh."""

import time
import httpx


class AuthManager:
    """Управление аутентификацией в Superset REST API.

    Использует JWT-аутентификацию:
    - Login: POST /api/v1/security/login с refresh=true
    - CSRF: GET /api/v1/security/csrf_token/ (обязателен для POST/PUT/DELETE)
    - Refresh: POST /api/v1/security/refresh при истечении access_token
    """

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        provider: str = "db",
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.provider = provider

        # JWT-состояние
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._csrf_token: str | None = None
        self._token_expires_at: float = 0

    async def get_token(self, client: httpx.AsyncClient) -> str:
        """Возвращает актуальный access_token."""
        # Проверяем не истёк ли токен (с запасом 30 сек)
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token

        # Пробуем refresh, если есть refresh-токен
        if self._refresh_token:
            refreshed = await self._refresh(client)
            if refreshed:
                return self._access_token

        # Полный логин
        await self._login(client)
        return self._access_token

    async def get_csrf_token(self, client: httpx.AsyncClient) -> str:
        """Возвращает актуальный CSRF-токен (получает при необходимости)."""
        if self._csrf_token:
            return self._csrf_token
        await self._fetch_csrf(client)
        return self._csrf_token

    async def _login(self, client: httpx.AsyncClient) -> None:
        """Выполняет JWT-логин через POST /api/v1/security/login."""
        url = f"{self.base_url}/api/v1/security/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "provider": self.provider,
            "refresh": True,
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        # По умолчанию JWT_ACCESS_TOKEN_EXPIRES = 15 минут (900 сек)
        self._token_expires_at = time.time() + 900
        # Сбрасываем CSRF — он привязан к сессии/токену
        self._csrf_token = None

    async def _refresh(self, client: httpx.AsyncClient) -> bool:
        """Пробует обновить JWT через refresh-токен."""
        url = f"{self.base_url}/api/v1/security/refresh"
        headers = {"Authorization": f"Bearer {self._refresh_token}"}
        try:
            resp = await client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + 900
            # Сбрасываем CSRF — нужен новый для нового токена
            self._csrf_token = None
            return True
        except (httpx.HTTPStatusError, KeyError):
            # Refresh не удался — нужен полный логин
            self._refresh_token = None
            return False

    async def _fetch_csrf(self, client: httpx.AsyncClient) -> None:
        """Получает CSRF-токен через GET /api/v1/security/csrf_token/."""
        token = await self.get_token(client)
        url = f"{self.base_url}/api/v1/security/csrf_token/"
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self._csrf_token = data["result"]

    def invalidate(self) -> None:
        """Сбрасывает все кешированные токены."""
        self._access_token = None
        self._refresh_token = None
        self._csrf_token = None
        self._token_expires_at = 0
