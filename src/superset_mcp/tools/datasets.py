"""Инструменты для управления датасетами Superset."""

import base64
import json


def register_dataset_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_dataset_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список датасетов Superset с пагинацией.

        Датасет — ссылка на таблицу/вью или виртуальный SQL-запрос в Superset.
        ВАЖНО: всегда вызывайте перед dataset_get, чтобы узнать актуальные ID.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:table_name,opr:ct,value:поиск)))
                - По схеме: (filters:!((col:schema,opr:eq,value:public)))
                - По БД: (filters:!((col:database,opr:rel_o_m,value:1)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/dataset/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/dataset/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_get(dataset_id: int) -> str:
        """Получить детальную информацию о датасете: колонки, метрики, SQL.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_dataset_list.

        Args:
            dataset_id: ID датасета (целое число из результата dataset_list).
        """
        result = await client.get(f"/api/v1/dataset/{dataset_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_create(
        table_name: str,
        database: int,
        schema_name: str | None = None,
        sql: str | None = None,
    ) -> str:
        """Создать новый датасет (физический или виртуальный).

        Физический датасет — ссылка на существующую таблицу/вью в БД.
        Виртуальный датасет — произвольный SQL-запрос как источник данных.

        Args:
            table_name: Название таблицы/вью (для физического) или название датасета (для виртуального).
            database: ID подключения к БД (из superset_database_list).
            schema_name: Схема БД (напр. "public", "source"). Если не указана — default-схема БД.
            sql: SQL-запрос для виртуального датасета. Если указан, создаётся
                виртуальный датасет на основе этого запроса.
        """
        payload = {"table_name": table_name, "database": database}
        if schema_name is not None:
            payload["schema"] = schema_name
        if sql is not None:
            payload["sql"] = sql
        result = await client.post("/api/v1/dataset/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_update(
        dataset_id: int,
        table_name: str | None = None,
        sql: str | None = None,
        description: str | None = None,
        columns: str | None = None,
        metrics: str | None = None,
        confirm_columns_replace: bool = False,
    ) -> str:
        """Обновить датасет. Передавайте только изменяемые поля.

        Args:
            dataset_id: ID датасета для обновления.
            table_name: Новое название таблицы/датасета.
            sql: Новый SQL-запрос (только для виртуального датасета).
            description: Описание датасета (отображается в Superset UI).
            columns: JSON-строка с описанием колонок.
                КРИТИЧНО: передача columns ЗАМЕНЯЕТ ВСЕ колонки датасета!
                Для обновления одной колонки (напр. verbose_name) — передавайте
                ВСЕ колонки с их ID. После ошибки — dataset_refresh_schema восстановит.
                Формат: [{"id": 123, "column_name": "id", "type": "INTEGER", ...}]
            metrics: JSON-строка с описанием метрик. Формат:
                [{"metric_name": "count", "expression": "COUNT(*)", "metric_type": "count"}]
            confirm_columns_replace: Подтверждение замены ВСЕХ колонок (ОБЯЗАТЕЛЬНО при columns).
        """
        # Защита от случайной потери колонок
        if columns is not None and not confirm_columns_replace:
            return json.dumps(
                {
                    "error": (
                        "ОТКЛОНЕНО: передан columns без confirm_columns_replace=True. "
                        "Superset PUT /dataset/{id} с полем columns ЗАМЕНЯЕТ ВСЕ колонки "
                        "датасета списком из параметра. Для обновления одной колонки "
                        "(напр. verbose_name) — передавайте ВСЕ колонки с их ID. "
                        "Сначала получите текущие колонки через dataset_get, "
                        "затем передайте полный список с confirm_columns_replace=True. "
                        "При ошибке — dataset_refresh_schema восстановит колонки из SQL."
                    )
                },
                ensure_ascii=False,
            )

        payload = {}
        if table_name is not None:
            payload["table_name"] = table_name
        if sql is not None:
            payload["sql"] = sql
        if description is not None:
            payload["description"] = description
        if columns is not None:
            payload["columns"] = json.loads(columns)
        if metrics is not None:
            payload["metrics"] = json.loads(metrics)
        result = await client.put(f"/api/v1/dataset/{dataset_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_refresh_schema(dataset_id: int) -> str:
        """Обновить схему датасета из источника (пересканировать колонки и типы).

        Полезно после ALTER TABLE или изменения структуры таблицы в БД.

        Args:
            dataset_id: ID датасета.
        """
        result = await client.put(f"/api/v1/dataset/{dataset_id}/refresh", json_data={})
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_delete(
        dataset_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить датасет. Графики, использующие этот датасет, перестанут работать.

        КРИТИЧНО: удаление датасета ломает все привязанные чарты и дашборды.

        Args:
            dataset_id: ID датасета для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                ds_info = await client.get(f"/api/v1/dataset/{dataset_id}")
                ds_name = ds_info.get("result", {}).get("table_name", "?")
                related = await client.get(f"/api/v1/dataset/{dataset_id}/related_objects")
                charts_count = related.get("charts", {}).get("count", 0)
                dashboards_count = related.get("dashboards", {}).get("count", 0)
            except Exception:
                ds_name = f"ID={dataset_id}"
                charts_count = dashboards_count = "?"
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: удаление датасета '{ds_name}' (ID={dataset_id}) "
                        f"сломает {charts_count} чартов и {dashboards_count} дашбордов. "
                        f"Передайте confirm_delete=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/dataset/{dataset_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_duplicate(
        base_model_id: int,
        table_name: str,
    ) -> str:
        """Создать копию существующего датасета (с колонками и метриками).

        Args:
            base_model_id: ID исходного датасета для копирования.
                ВАЖНО: поле называется base_model_id, НЕ base_id и НЕ dataset_id.
            table_name: Название нового датасета (должно быть уникальным).
        """
        result = await client.post(
            "/api/v1/dataset/duplicate",
            json_data={"base_model_id": base_model_id, "table_name": table_name},
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_related_objects(dataset_id: int) -> str:
        """Получить объекты, связанные с датасетом (графики и дашборды).

        Полезно перед удалением датасета, чтобы понять, что сломается.

        Args:
            dataset_id: ID датасета.
        """
        result = await client.get(f"/api/v1/dataset/{dataset_id}/related_objects")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_export(
        dataset_ids: str,
    ) -> str:
        """Экспортировать датасеты с зависимостями (БД) в ZIP-файл.

        Результат — base64-кодированный ZIP. Можно импортировать через dataset_import.

        Args:
            dataset_ids: ID датасетов через запятую (напр. "1,2,3").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        params = {"q": f"[{dataset_ids}]"}
        raw = await client.get_raw("/api/v1/dataset/export/", params=params)
        return json.dumps(
            {
                "format": "zip",
                "encoding": "base64",
                "data": base64.b64encode(raw).decode(),
                "size_bytes": len(raw),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_dataset_import(
        file_path: str,
        overwrite: bool = False,
    ) -> str:
        """Импортировать датасеты из ZIP-файла (созданного через export).

        Args:
            file_path: Абсолютный путь к ZIP-файлу на диске.
            overwrite: Перезаписать существующие объекты с такими же UUID (по умолчанию False).
        """
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/dataset/import/",
                files=files,
                data=data,
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dataset_get_or_create(
        database_id: int,
        table_name: str,
        schema_name: str | None = None,
    ) -> str:
        """Получить существующий датасет или создать новый для таблицы.

        Если датасет на указанную таблицу уже существует — возвращает его.
        Если нет — создаёт новый физический датасет.

        Args:
            database_id: ID подключения к БД (из superset_database_list).
            table_name: Название таблицы в БД.
            schema_name: Схема БД (напр. "public", "source"). Если не указана — default-схема.
        """
        payload = {"database_id": database_id, "table_name": table_name}
        if schema_name is not None:
            payload["schema"] = schema_name
        result = await client.post(
            "/api/v1/dataset/get_or_create/",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)
