"""HTTP-клиент для Superset REST API с автоматической аутентификацией."""

from typing import Any

import httpx

from superset_mcp.auth import AuthManager


class SupersetClient:
    """Единый async HTTP-клиент для взаимодействия с Superset REST API.

    Автоматически подставляет JWT + CSRF в заголовки,
    обрабатывает ошибки API и предоставляет удобные методы CRUD.
    """

    def __init__(self, auth_manager: AuthManager, base_url: str):
        self.auth = auth_manager
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        )

    async def _get_headers(self, need_csrf: bool = False) -> dict[str, str]:
        """Формирует заголовки с актуальным JWT и CSRF-токеном.

        Args:
            need_csrf: True для мутирующих запросов (POST/PUT/DELETE).
        """
        token = await self.auth.get_token(self._client)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": self.base_url,
        }
        if need_csrf:
            csrf = await self.auth.get_csrf_token(self._client)
            headers["X-CSRFToken"] = csrf
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполняет HTTP-запрос к Superset API с обработкой ошибок."""
        url = f"{self.base_url}{endpoint}"
        need_csrf = method.upper() in ("POST", "PUT", "DELETE")
        headers = await self._get_headers(need_csrf=need_csrf)

        resp = await self._client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
        )

        if resp.status_code == 401:
            # Токен протух — сбрасываем и пробуем ещё раз
            # НЕ ретраим 400 (Bad Request) — это ошибка валидации данных
            self.auth.invalidate()
            headers = await self._get_headers(need_csrf=need_csrf)
            resp = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
            )

        if resp.status_code >= 400:
            error_detail = ""
            try:
                error_body = resp.json()
                error_detail = error_body.get("message", "") or error_body.get("errors", str(error_body))
            except Exception:
                error_detail = resp.text[:500]
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API {method} {endpoint}: {resp.status_code} — {error_detail}",
            )

        if resp.status_code == 204:
            return {"status": "ok"}

        return resp.json()

    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("POST", endpoint, json_data=json_data)

    async def put(self, endpoint: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("PUT", endpoint, json_data=json_data)

    async def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("DELETE", endpoint, params=params)

    async def get_raw(self, endpoint: str, params: dict[str, Any] | None = None) -> bytes:
        """GET-запрос с возвратом сырых байтов (для export endpoints)."""
        url = f"{self.base_url}{endpoint}"
        headers = await self._get_headers(need_csrf=False)
        headers.pop("Content-Type", None)
        headers["Accept"] = "*/*"
        resp = await self._client.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
        )
        if resp.status_code == 401:
            self.auth.invalidate()
            headers = await self._get_headers(need_csrf=False)
            headers.pop("Content-Type", None)
            headers["Accept"] = "*/*"
            resp = await self._client.request(
                method="GET",
                url=url,
                headers=headers,
                params=params,
            )
        if resp.status_code >= 400:
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API GET {endpoint}: {resp.status_code} — {resp.text[:500]}",
            )
        return resp.content

    async def post_form(
        self,
        endpoint: str,
        files: dict,
        data: dict | None = None,
    ) -> dict[str, Any]:
        """POST multipart/form-data (для import endpoints)."""
        url = f"{self.base_url}{endpoint}"
        token = await self.auth.get_token(self._client)
        csrf = await self.auth.get_csrf_token(self._client)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-CSRFToken": csrf,
            "Referer": self.base_url,
        }
        resp = await self._client.post(
            url=url,
            headers=headers,
            files=files,
            data=data or {},
        )
        if resp.status_code == 401:
            self.auth.invalidate()
            token = await self.auth.get_token(self._client)
            csrf = await self.auth.get_csrf_token(self._client)
            headers["Authorization"] = f"Bearer {token}"
            headers["X-CSRFToken"] = csrf
            resp = await self._client.post(
                url=url,
                headers=headers,
                files=files,
                data=data or {},
            )
        if resp.status_code >= 400:
            error_detail = ""
            try:
                error_body = resp.json()
                error_detail = error_body.get("message", "") or error_body.get("errors", str(error_body))
            except Exception:
                error_detail = resp.text[:500]
            raise SupersetAPIError(
                status_code=resp.status_code,
                detail=f"Superset API POST {endpoint}: {resp.status_code} — {error_detail}",
            )
        if resp.status_code == 204:
            return {"status": "ok"}
        return resp.json()

    @staticmethod
    def _build_rison_q(page: int, page_size: int, existing_q: str | None = None) -> str:
        """Формирует RISON-строку с пагинацией, мержа с существующим q-фильтром.

        Superset игнорирует page/page_size как query-параметры —
        они ОБЯЗАТЕЛЬНО должны быть внутри RISON-параметра q.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Размер страницы.
            existing_q: Существующий RISON-фильтр (напр. "(filters:!(...))").

        Returns:
            RISON-строка с пагинацией: "(page:0,page_size:100,...)"
        """
        pagination = f"page:{page},page_size:{page_size}"
        if not existing_q:
            return f"({pagination})"
        # Мержим: вставляем пагинацию внутрь существующих RISON-скобок
        q = existing_q.strip()
        if q.startswith("(") and q.endswith(")"):
            inner = q[1:-1].strip()
            if inner:
                return f"({pagination},{inner})"
            return f"({pagination})"
        # Если формат нестандартный — оборачиваем
        return f"({pagination},{q})"

    async def get_all(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        page_size: int = 100,
        max_pages: int = 100,
    ) -> dict[str, Any]:
        """GET-запрос с автоматической пагинацией — возвращает ВСЕ записи.

        Последовательно запрашивает страницы по page_size записей,
        пока не получит все результаты (ориентируется на поле count в ответе).

        ВАЖНО: Superset требует пагинацию через RISON в параметре q,
        а НЕ через отдельные query-параметры page/page_size.

        Args:
            endpoint: API endpoint (напр. "/api/v1/security/roles/").
            params: Дополнительные query-параметры (q, фильтры и т.д.).
            page_size: Размер страницы (макс. 100 для Superset API).
            max_pages: Максимум страниц (защита от бесконечного цикла, default=100 → 10000 записей).

        Returns:
            Объединённый результат: {"result": [...все записи...], "count": N}.
        """
        all_results: list[Any] = []
        page = 0
        total_count = None
        existing_q = (params or {}).get("q")

        while page < max_pages:
            page_params = {k: v for k, v in (params or {}).items() if k != "q"}
            page_params["q"] = self._build_rison_q(page, page_size, existing_q)

            data = await self.get(endpoint, params=page_params)

            results = data.get("result", [])
            all_results.extend(results)

            if total_count is None:
                total_count = data.get("count", len(results))

            if len(all_results) >= total_count or len(results) < page_size:
                break

            page += 1

        return {"result": all_results, "count": total_count or len(all_results)}

    async def close(self) -> None:
        await self._client.aclose()


class SupersetAPIError(Exception):
    """Ошибка Superset REST API."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
