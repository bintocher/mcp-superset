"""Инструменты для управления тегами в Superset."""

import json


def register_tag_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_tag_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список тегов Superset.

        Теги используются для группировки и организации дашбордов, графиков, датасетов.
        ВАЖНО: всегда вызывайте перед tag_get/tag_update, чтобы узнать актуальные ID.
        При создании тега API возвращает {} без ID — используйте tag_list для получения ID.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:name,opr:ct,value:поиск)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/tag/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/tag/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_get(tag_id: int) -> str:
        """Получить информацию о теге по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_tag_list.

        Args:
            tag_id: ID тега (целое число из результата tag_list).
        """
        result = await client.get(f"/api/v1/tag/{tag_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_create(
        name: str,
        description: str | None = None,
        objects_to_tag: str | None = None,
    ) -> str:
        """Создать новый тег и опционально привязать к объектам Superset.

        ВАЖНО: Superset API возвращает {} при создании (без ID тега).
        Для получения ID нового тега вызовите superset_tag_list после создания.

        Привязка к объектам возможна ТОЛЬКО при создании через objects_to_tag.
        Прямые эндпоинты привязки (POST/DELETE /api/v1/tag/{type}/{id}/) не работают в 6.0.1.

        Args:
            name: Название тега.
            description: Описание тега (опционально).
            objects_to_tag: JSON-строка со списком объектов для тегирования. Формат:
                [["dashboard", 1], ["chart", 5], ["dataset", 3], ["saved_query", 2]]
                Каждый элемент — пара [тип_объекта, id_объекта].
                Допустимые типы: "dashboard", "chart", "dataset", "saved_query".
        """
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        if objects_to_tag is not None:
            payload["objects_to_tag"] = json.loads(objects_to_tag)
        result = await client.post("/api/v1/tag/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_update(
        tag_id: int,
        name: str,
        description: str | None = None,
    ) -> str:
        """Обновить тег (переименовать или изменить описание).

        ВАЖНО: поле name ОБЯЗАТЕЛЬНО в Superset 6.0.1 — даже если название не меняется,
        его нужно передать. Без него Superset вернёт 500.

        Args:
            tag_id: ID тега для обновления.
            name: Название тега (ОБЯЗАТЕЛЬНО, даже если не меняется).
            description: Новое описание (опционально).
        """
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        result = await client.put(f"/api/v1/tag/{tag_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_delete(
        tag_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить тег. Привязки к объектам будут удалены.

        Args:
            tag_id: ID тега для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/tag/{tag_id}")
                name = info.get("result", {}).get("name", "?")
            except Exception:
                name = f"ID={tag_id}"
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: удаление тега '{name}' (ID={tag_id}) "
                        f"и всех его привязок к объектам. "
                        f"Передайте confirm_delete=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/tag/{tag_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_get_objects(
        tags: str | None = None,
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """Получить объекты, помеченные указанными тегами.

        Возвращает дашборды, графики, датасеты и запросы с указанными тегами.

        Args:
            tags: Названия тегов через запятую (напр. "analytics,production").
                Если не указано — возвращает все помеченные объекты.
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if tags:
                params["tags"] = tags
            result = await client.get_all("/api/v1/tag/get_objects/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if tags:
                params["tags"] = tags
            result = await client.get("/api/v1/tag/get_objects/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_bulk_create(
        tags: str,
    ) -> str:
        """Массовое создание тегов с привязкой к объектам.

        Позволяет создать несколько тегов и привязать их к объектам за один запрос.

        Args:
            tags: JSON-строка со списком тегов. Формат:
                [
                    {"name": "production", "objects_to_tag": [["dashboard", 1], ["chart", 5]]},
                    {"name": "analytics", "objects_to_tag": [["dataset", 3]]}
                ]
                objects_to_tag: пары [тип_объекта, id_объекта].
                Допустимые типы: "dashboard", "chart", "dataset", "saved_query".
        """
        payload = {"tags": json.loads(tags)}
        result = await client.post("/api/v1/tag/bulk_create", json_data=payload)
        return json.dumps(result, ensure_ascii=False)
