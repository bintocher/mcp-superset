"""Инструменты для управления подключениями к базам данных в Superset."""

import json


def register_database_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_database_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список подключений к базам данных в Superset.

        Возвращает ID, название, тип движка и статус каждого подключения.
        ВАЖНО: всегда вызывайте перед database_get, чтобы узнать актуальные ID.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:database_name,opr:ct,value:postgres)))
                - По типу: (filters:!((col:backend,opr:eq,value:postgresql)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/database/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/database/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_get(database_id: int) -> str:
        """Получить детальную информацию о подключении к БД по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_database_list.

        Args:
            database_id: ID подключения (целое число из результата database_list).
        """
        result = await client.get(f"/api/v1/database/{database_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_create(
        database_name: str,
        sqlalchemy_uri: str,
        expose_in_sqllab: bool = True,
        allow_ctas: bool = False,
        allow_cvas: bool = False,
        allow_dml: bool = False,
        allow_run_async: bool = False,
        extra: str | None = None,
    ) -> str:
        """Создать новое подключение к базе данных.

        ВАЖНО: Superset проверяет доступность БД при создании.
        URI должен быть доступен с сервера Superset (не localhost клиента).

        Args:
            database_name: Человекочитаемое название подключения.
            sqlalchemy_uri: SQLAlchemy URI строка подключения. Примеры:
                - PostgreSQL: postgresql://user:pass@host:5432/dbname
                - MySQL: mysql://user:pass@host:3306/dbname
                - SQLite: sqlite:///path/to/db.sqlite
            expose_in_sqllab: Показывать ли в SQL Lab (по умолчанию True).
            allow_ctas: Разрешить CREATE TABLE AS SELECT.
            allow_cvas: Разрешить CREATE VIEW AS SELECT.
            allow_dml: Разрешить INSERT/UPDATE/DELETE.
            allow_run_async: Разрешить асинхронное выполнение запросов.
            extra: JSON-строка с дополнительными настройками (engine_params, metadata_params).
        """
        payload = {
            "database_name": database_name,
            "sqlalchemy_uri": sqlalchemy_uri,
            "expose_in_sqllab": expose_in_sqllab,
            "allow_ctas": allow_ctas,
            "allow_cvas": allow_cvas,
            "allow_dml": allow_dml,
            "allow_run_async": allow_run_async,
        }
        if extra is not None:
            payload["extra"] = extra
        result = await client.post("/api/v1/database/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_update(
        database_id: int,
        database_name: str | None = None,
        sqlalchemy_uri: str | None = None,
        expose_in_sqllab: bool | None = None,
        allow_ctas: bool | None = None,
        allow_cvas: bool | None = None,
        allow_dml: bool | None = None,
        extra: str | None = None,
        confirm_uri_change: bool = False,
    ) -> str:
        """Обновить подключение к базе данных. Передавайте только изменяемые поля.

        Args:
            database_id: ID подключения для обновления.
            database_name: Новое название подключения.
            sqlalchemy_uri: Новый SQLAlchemy URI.
                КРИТИЧНО: смена URI ломает все датасеты и чарты на этом подключении.
            expose_in_sqllab: Показывать ли в SQL Lab.
            allow_ctas: Разрешить CREATE TABLE AS SELECT.
            allow_cvas: Разрешить CREATE VIEW AS SELECT.
            allow_dml: Разрешить INSERT/UPDATE/DELETE.
            extra: JSON-строка с дополнительными настройками.
            confirm_uri_change: Подтверждение смены URI (ОБЯЗАТЕЛЬНО при изменении sqlalchemy_uri).
        """
        if sqlalchemy_uri is not None and not confirm_uri_change:
            try:
                db_info = await client.get(f"/api/v1/database/{database_id}")
                db_name = db_info.get("result", {}).get("database_name", "?")
                related = await client.get(
                    f"/api/v1/database/{database_id}/related_objects/"
                )
                charts_count = related.get("charts", {}).get("count", 0)
                dashboards_count = related.get("dashboards", {}).get("count", 0)
            except Exception:
                db_name = f"ID={database_id}"
                charts_count = dashboards_count = "?"
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: смена sqlalchemy_uri подключения '{db_name}' "
                    f"(ID={database_id}) может сломать {charts_count} чартов "
                    f"и {dashboards_count} дашбордов. "
                    f"Передайте confirm_uri_change=True для подтверждения."
                )
            }, ensure_ascii=False)

        payload = {}
        if database_name is not None:
            payload["database_name"] = database_name
        if sqlalchemy_uri is not None:
            payload["sqlalchemy_uri"] = sqlalchemy_uri
        if expose_in_sqllab is not None:
            payload["expose_in_sqllab"] = expose_in_sqllab
        if allow_ctas is not None:
            payload["allow_ctas"] = allow_ctas
        if allow_cvas is not None:
            payload["allow_cvas"] = allow_cvas
        if allow_dml is not None:
            payload["allow_dml"] = allow_dml
        if extra is not None:
            payload["extra"] = extra
        result = await client.put(
            f"/api/v1/database/{database_id}", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_delete(
        database_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить подключение к БД. Все связанные датасеты станут нерабочими.

        КРИТИЧНО: удаление подключения ломает ВСЕ датасеты, чарты и дашборды на этой БД.

        Args:
            database_id: ID подключения для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                db_info = await client.get(f"/api/v1/database/{database_id}")
                db_name = db_info.get("result", {}).get("database_name", "?")
                related = await client.get(
                    f"/api/v1/database/{database_id}/related_objects/"
                )
                charts_count = related.get("charts", {}).get("count", 0)
                dashboards_count = related.get("dashboards", {}).get("count", 0)
            except Exception:
                db_name = f"ID={database_id}"
                charts_count = dashboards_count = "?"
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление подключения '{db_name}' (ID={database_id}) "
                    f"сделает нерабочими {charts_count} чартов и {dashboards_count} дашбордов. "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        result = await client.delete(f"/api/v1/database/{database_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_test_connection(
        database_name: str,
        sqlalchemy_uri: str,
        extra: str | None = None,
    ) -> str:
        """Проверить подключение к базе данных без создания.

        ВАЖНО: URI должен быть доступен с сервера Superset.

        Args:
            database_name: Название подключения (для отображения в ошибках).
            sqlalchemy_uri: SQLAlchemy URI для проверки.
            extra: JSON-строка с дополнительными настройками.
        """
        payload = {
            "database_name": database_name,
            "sqlalchemy_uri": sqlalchemy_uri,
        }
        if extra is not None:
            payload["extra"] = extra
        result = await client.post(
            "/api/v1/database/test_connection/", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_schemas(database_id: int) -> str:
        """Получить список схем (schemas) в базе данных.

        Полезно для выбора схемы перед запросом таблиц или созданием датасета.

        Args:
            database_id: ID подключения к БД (из database_list).
        """
        result = await client.get(f"/api/v1/database/{database_id}/schemas/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_tables(
        database_id: int,
        schema_name: str,
    ) -> str:
        """Получить список таблиц и вью в указанной схеме базы данных.

        Полезно для выбора таблицы перед созданием датасета.

        Args:
            database_id: ID подключения к БД (из database_list).
            schema_name: Название схемы (из database_schemas). Примеры: "public", "source".
                Передаётся в RISON-формате без кавычек.
        """
        result = await client.get(
            f"/api/v1/database/{database_id}/tables/",
            params={"q": f"(schema_name:{schema_name})"},
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_catalogs(database_id: int) -> str:
        """Получить список каталогов в базе данных (для БД с поддержкой каталогов).

        Поддерживается не всеми движками. PostgreSQL и MySQL обычно не используют каталоги.

        Args:
            database_id: ID подключения к БД.
        """
        result = await client.get(f"/api/v1/database/{database_id}/catalogs/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_connection_info(database_id: int) -> str:
        """Получить информацию о подключении (URI без пароля, параметры).

        Args:
            database_id: ID подключения к БД.
        """
        result = await client.get(f"/api/v1/database/{database_id}/connection")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_function_names(database_id: int) -> str:
        """Получить список доступных SQL-функций в базе данных.

        Полезно для построения SQL-запросов с использованием специфичных функций движка.

        Args:
            database_id: ID подключения к БД.
        """
        result = await client.get(
            f"/api/v1/database/{database_id}/function_names/"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_related_objects(database_id: int) -> str:
        """Получить объекты, связанные с подключением (датасеты, графики).

        Полезно перед удалением подключения, чтобы понять, что сломается.

        Args:
            database_id: ID подключения к БД.
        """
        result = await client.get(
            f"/api/v1/database/{database_id}/related_objects/"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_validate_sql(
        database_id: int,
        sql: str,
        schema: str | None = None,
    ) -> str:
        """Проверить синтаксис SQL-запроса без выполнения (EXPLAIN-подобная проверка).

        ВАЖНО: не все движки БД поддерживают валидацию SQL. PostgreSQL поддерживает.

        Args:
            database_id: ID подключения к БД.
            sql: SQL-запрос для проверки.
            schema: Схема для контекста проверки (напр. "public").
        """
        payload = {"sql": sql}
        if schema is not None:
            payload["schema"] = schema
        result = await client.post(
            f"/api/v1/database/{database_id}/validate_sql/", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_validate_parameters(
        engine: str,
        parameters: dict,
        configuration_method: str = "sqlalchemy_form",
    ) -> str:
        """Проверить параметры подключения к БД без создания подключения.

        Args:
            engine: Тип движка БД: "postgresql", "mysql", "sqlite", "mssql" и т.д.
            parameters: Словарь параметров подключения:
                {"host": "...", "port": 5432, "database": "...",
                 "username": "...", "password": "..."}
            configuration_method: Метод конфигурации: "sqlalchemy_form" (по умолчанию)
                или "dynamic_form".
        """
        payload = {
            "engine": engine,
            "parameters": parameters,
            "configuration_method": configuration_method,
        }
        result = await client.post(
            "/api/v1/database/validate_parameters/", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_select_star(
        database_id: int,
        table_name: str,
        schema_name: str | None = None,
    ) -> str:
        """Сгенерировать SQL-запрос SELECT * для таблицы (с LIMIT).

        Полезно для быстрого просмотра структуры и данных таблицы.

        Args:
            database_id: ID подключения к БД.
            table_name: Название таблицы.
            schema_name: Схема (напр. "public"). Если не указана — default-схема.
        """
        if schema_name:
            endpoint = f"/api/v1/database/{database_id}/select_star/{table_name}/{schema_name}/"
        else:
            endpoint = f"/api/v1/database/{database_id}/select_star/{table_name}/"
        result = await client.get(endpoint)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_table_metadata(
        database_id: int,
        table_name: str,
        schema_name: str | None = None,
    ) -> str:
        """Получить метаданные таблицы: колонки, типы данных, индексы, первичные ключи.

        Полезно для понимания структуры таблицы перед написанием SQL-запросов.

        Args:
            database_id: ID подключения к БД.
            table_name: Название таблицы.
            schema_name: Схема (напр. "public"). Если не указана — default-схема.
        """
        params = {"name": table_name}
        if schema_name:
            params["schema"] = schema_name
        result = await client.get(
            f"/api/v1/database/{database_id}/table_metadata/", params=params,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_export(
        database_ids: str,
    ) -> str:
        """Экспортировать конфигурации подключений к БД в ZIP-файл.

        ВАЖНО: пароли НЕ экспортируются из соображений безопасности.

        Args:
            database_ids: ID подключений через запятую (напр. "1,2").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        import base64
        params = {"q": f"[{database_ids}]"}
        raw = await client.get_raw("/api/v1/database/export/", params=params)
        return json.dumps({
            "format": "zip",
            "encoding": "base64",
            "data": base64.b64encode(raw).decode(),
            "size_bytes": len(raw),
        }, ensure_ascii=False)

    @mcp.tool
    async def superset_database_available_engines() -> str:
        """Получить список поддерживаемых типов БД для создания подключений.

        Возвращает доступные движки: PostgreSQL, MySQL, SQLite, и т.д.
        Полезно для выбора engine при создании нового подключения.
        """
        result = await client.get("/api/v1/database/available/")
        return json.dumps(result, ensure_ascii=False)
