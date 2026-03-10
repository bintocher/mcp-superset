"""Инструменты для SQL Lab и управления запросами в Superset."""

import json
import re


def _strip_sql_comments(sql: str) -> str:
    """Убирает SQL-комментарии (однострочные -- и многострочные /* */).

    Нужно для корректной проверки DDL/DML — без этого комментарий перед
    опасной командой обходит блокировку: '/* */ DROP TABLE ...'
    """
    # Убираем многострочные комментарии /* ... */
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Убираем однострочные комментарии -- ...
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


def register_query_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_sqllab_execute(
        database_id: int,
        sql: str,
        schema: str | None = None,
        catalog: str | None = None,
        tab_name: str | None = None,
        template_params: str | None = None,
    ) -> str:
        """Выполнить SQL-запрос через SQL Lab и получить результат.

        ВАЖНО: перед выполнением убедитесь в правильности SQL-запроса.
        Используйте superset_database_table_metadata или superset_database_tables,
        чтобы узнать актуальные названия таблиц и колонок.
        Максимум 1000 строк в результате (queryLimit).

        Args:
            database_id: ID подключения к БД (из superset_database_list).
            sql: SQL-запрос для выполнения. Примеры:
                - SELECT * FROM public.my_table LIMIT 10
                - SELECT count(*) FROM source.stat
            schema: Схема по умолчанию для запроса (напр. "public", "source").
                Если не указана, используется default-схема БД.
            catalog: Каталог БД (для БД с поддержкой каталогов, опционально).
            tab_name: Название вкладки в SQL Lab UI (опционально, для организации).
            template_params: JSON-строка с параметрами Jinja-шаблона (опционально).
                Пример: '{"start_date": "2024-01-01"}'
        """
        # Защита от случайного DDL/DML
        # Убираем комментарии, чтобы нельзя было обойти через /* */ DROP ...
        _dangerous_prefixes = (
            "DROP",
            "DELETE",
            "UPDATE",
            "INSERT",
            "TRUNCATE",
            "ALTER",
            "CREATE",
            "GRANT",
            "REVOKE",
        )
        sql_clean = _strip_sql_comments(sql).upper()
        for prefix in _dangerous_prefixes:
            if sql_clean.startswith(prefix):
                return json.dumps(
                    {
                        "error": (
                            f"ОТКЛОНЕНО: SQL-запрос начинается с '{prefix}' — "
                            f"это модифицирующая операция (DDL/DML). "
                            f"Выполнение таких запросов через MCP запрещено. "
                            f"Если операция действительно необходима — выполните её "
                            f"напрямую через SQL Lab в Superset UI."
                        )
                    },
                    ensure_ascii=False,
                )

        payload = {
            "database_id": database_id,
            "sql": sql,
            "runAsync": False,
            "queryLimit": 1000,
        }
        if schema is not None:
            payload["schema"] = schema
        if catalog is not None:
            payload["catalog"] = catalog
        if tab_name is not None:
            payload["tab"] = tab_name
        if template_params is not None:
            payload["templateParams"] = template_params
        result = await client.post("/api/v1/sqllab/execute/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_format_sql(sql: str) -> str:
        """Отформатировать SQL-запрос (pretty print с отступами).

        Args:
            sql: SQL-запрос для форматирования.
        """
        result = await client.post("/api/v1/sqllab/format_sql/", json_data={"sql": sql})
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_results(results_key: str) -> str:
        """Получить результаты ранее выполненного запроса по ключу.

        ВАЖНО: требует настроенного Results Backend (Redis/S3) в Superset.
        Без него возвращает 500. Ключ берётся из поля results_key результата sqllab_execute.

        Args:
            results_key: Ключ результатов из ответа superset_sqllab_execute.
        """
        result = await client.get(
            "/api/v1/sqllab/results/",
            params={"q": f"(key:{results_key})"},
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_estimate_cost(
        database_id: int,
        sql: str,
        schema: str | None = None,
    ) -> str:
        """Оценить стоимость выполнения SQL-запроса (EXPLAIN).

        Не все движки БД поддерживают эту функцию. PostgreSQL поддерживает.

        Args:
            database_id: ID подключения к БД.
            sql: SQL-запрос для оценки.
            schema: Схема для контекста (напр. "public").
        """
        payload = {"database_id": database_id, "sql": sql}
        if schema is not None:
            payload["schema"] = schema
        result = await client.post("/api/v1/sqllab/estimate/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_export_csv(client_id: str) -> str:
        """Экспортировать результаты запроса в CSV-формат.

        ВАЖНО: требует настроенного Results Backend (Redis/S3) в Superset.

        Args:
            client_id: client_id запроса (из результата superset_sqllab_execute).
        """
        result = await client.get(f"/api/v1/sqllab/export/{client_id}/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_query_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить историю выполненных SQL-запросов.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По статусу: (filters:!((col:status,opr:eq,value:success)))
                - По БД: (filters:!((col:database,opr:rel_o_m,value:1)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/query/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/query/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_query_get(query_id: int) -> str:
        """Получить детальную информацию о запросе из истории по ID.

        Args:
            query_id: ID запроса (целое число из результата query_list).
        """
        result = await client.get(f"/api/v1/query/{query_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_query_stop(query_id: str) -> str:
        """Остановить выполняющийся асинхронный запрос.

        Args:
            query_id: client_id запроса для остановки (строка из результата sqllab_execute).
        """
        result = await client.post("/api/v1/query/stop", json_data={"client_id": query_id})
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список сохранённых SQL-запросов.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:label,opr:ct,value:поиск)))
                - По БД: (filters:!((col:database,opr:rel_o_m,value:1)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/saved_query/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/saved_query/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_create(
        label: str,
        db_id: int,
        sql: str,
        schema: str | None = None,
        description: str | None = None,
    ) -> str:
        """Создать сохранённый SQL-запрос для повторного использования.

        Args:
            label: Название запроса (отображается в списке).
            db_id: ID подключения к БД (из superset_database_list).
            sql: SQL-запрос для сохранения.
            schema: Схема по умолчанию (напр. "public").
            description: Описание запроса.
        """
        payload = {"label": label, "db_id": db_id, "sql": sql}
        if schema is not None:
            payload["schema"] = schema
        if description is not None:
            payload["description"] = description
        result = await client.post("/api/v1/saved_query/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_get(saved_query_id: int) -> str:
        """Получить сохранённый запрос по ID: SQL-текст, схему, описание.

        Args:
            saved_query_id: ID сохранённого запроса (из saved_query_list).
        """
        result = await client.get(f"/api/v1/saved_query/{saved_query_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_update(
        saved_query_id: int,
        label: str | None = None,
        sql: str | None = None,
        schema: str | None = None,
        description: str | None = None,
    ) -> str:
        """Обновить сохранённый запрос. Передавайте только изменяемые поля.

        Args:
            saved_query_id: ID сохранённого запроса.
            label: Новое название.
            sql: Новый SQL-запрос.
            schema: Новая схема по умолчанию.
            description: Новое описание.
        """
        payload = {}
        if label is not None:
            payload["label"] = label
        if sql is not None:
            payload["sql"] = sql
        if schema is not None:
            payload["schema"] = schema
        if description is not None:
            payload["description"] = description
        result = await client.put(f"/api/v1/saved_query/{saved_query_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_delete(
        saved_query_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить сохранённый запрос.

        Args:
            saved_query_id: ID сохранённого запроса для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/saved_query/{saved_query_id}")
                r = info.get("result", {})
                label = r.get("label", "?")
                db_name = r.get("database", {}).get("database_name", "?")
            except Exception:
                label = f"ID={saved_query_id}"
                db_name = "?"
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: удаление сохранённого запроса '{label}' "
                        f"(ID={saved_query_id}, БД={db_name}). "
                        f"Передайте confirm_delete=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/saved_query/{saved_query_id}")
        return json.dumps(result, ensure_ascii=False)
