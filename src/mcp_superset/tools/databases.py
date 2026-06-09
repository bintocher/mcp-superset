"""Tools for managing database connections in Superset."""

import json


def register_database_tools(mcp):
    from mcp_superset.server import superset_client as client

    @mcp.tool
    async def superset_database_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List database connections configured in Superset.

        Returns the ID, name, engine type, and status of each connection.
        IMPORTANT: always call before database_get to discover current IDs.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for searching. Examples:
                - By name: (filters:!((col:database_name,opr:ct,value:postgres)))
                - By type: (filters:!((col:backend,opr:eq,value:postgresql)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/database/", params=params)
        else:
            result = await client.get_page("/api/v1/database/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_get(database_id: int) -> str:
        """Get detailed information about a database connection by ID.

        IMPORTANT: if the ID is unknown, call superset_database_list first.

        Args:
            database_id: Connection ID (integer from database_list result).
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
        """Create a new database connection.

        IMPORTANT: Superset validates database availability on creation.
        The URI must be reachable from the Superset server (not the client's localhost).

        Args:
            database_name: Human-readable connection name.
            sqlalchemy_uri: SQLAlchemy connection URI string. Examples:
                - PostgreSQL: postgresql://user:pass@host:5432/dbname
                - MySQL: mysql://user:pass@host:3306/dbname
                - SQLite: sqlite:///path/to/db.sqlite
            expose_in_sqllab: Whether to show in SQL Lab (default True).
            allow_ctas: Allow CREATE TABLE AS SELECT.
            allow_cvas: Allow CREATE VIEW AS SELECT.
            allow_dml: Allow INSERT/UPDATE/DELETE.
            allow_run_async: Allow asynchronous query execution.
            extra: JSON string with additional settings (engine_params, metadata_params).
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
        """Update a database connection. Pass only the fields you want to change.

        Args:
            database_id: Connection ID to update.
            database_name: New connection name.
            sqlalchemy_uri: New SQLAlchemy URI.
                CRITICAL: changing the URI breaks all datasets and charts using this connection.
            expose_in_sqllab: Whether to show in SQL Lab.
            allow_ctas: Allow CREATE TABLE AS SELECT.
            allow_cvas: Allow CREATE VIEW AS SELECT.
            allow_dml: Allow INSERT/UPDATE/DELETE.
            extra: JSON string with additional settings.
            confirm_uri_change: Confirmation for URI change (REQUIRED when changing sqlalchemy_uri).
        """
        if sqlalchemy_uri is not None and not confirm_uri_change:
            try:
                db_info = await client.get(f"/api/v1/database/{database_id}")
                db_name = db_info.get("result", {}).get("database_name", "?")
                related = await client.get(f"/api/v1/database/{database_id}/related_objects/")
                charts_count = related.get("charts", {}).get("count", 0)
                dashboards_count = related.get("dashboards", {}).get("count", 0)
            except Exception:
                db_name = f"ID={database_id}"
                charts_count = dashboards_count = "?"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: changing sqlalchemy_uri for connection '{db_name}' "
                        f"(ID={database_id}) may break {charts_count} charts "
                        f"and {dashboards_count} dashboards. "
                        f"Pass confirm_uri_change=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

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
        result = await client.put(f"/api/v1/database/{database_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_delete(
        database_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a database connection. All associated datasets will become broken.

        CRITICAL: deleting a connection breaks ALL datasets, charts, and dashboards using this DB.

        Args:
            database_id: Connection ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                db_info = await client.get(f"/api/v1/database/{database_id}")
                db_name = db_info.get("result", {}).get("database_name", "?")
                related = await client.get(f"/api/v1/database/{database_id}/related_objects/")
                charts_count = related.get("charts", {}).get("count", 0)
                dashboards_count = related.get("dashboards", {}).get("count", 0)
            except Exception:
                db_name = f"ID={database_id}"
                charts_count = dashboards_count = "?"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deleting connection '{db_name}' (ID={database_id}) "
                        f"will break {charts_count} charts and {dashboards_count} dashboards. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/database/{database_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_test_connection(
        database_name: str,
        sqlalchemy_uri: str,
        extra: str | None = None,
    ) -> str:
        """Test a database connection without creating it.

        IMPORTANT: the URI must be reachable from the Superset server.

        Args:
            database_name: Connection name (shown in error messages).
            sqlalchemy_uri: SQLAlchemy URI to test.
            extra: JSON string with additional settings.
        """
        payload = {
            "database_name": database_name,
            "sqlalchemy_uri": sqlalchemy_uri,
        }
        if extra is not None:
            payload["extra"] = extra
        result = await client.post("/api/v1/database/test_connection/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_schemas(database_id: int) -> str:
        """List schemas available in a database.

        Useful for selecting a schema before querying tables or creating a dataset.

        Args:
            database_id: Database connection ID (from database_list).
        """
        result = await client.get(f"/api/v1/database/{database_id}/schemas/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_tables(
        database_id: int,
        schema_name: str,
    ) -> str:
        """List tables and views in the specified database schema.

        Useful for selecting a table before creating a dataset.

        Args:
            database_id: Database connection ID (from database_list).
            schema_name: Schema name (from database_schemas). Examples: "public", "source".
                Passed in RISON format without quotes.
        """
        result = await client.get(
            f"/api/v1/database/{database_id}/tables/",
            params={"q": f"(schema_name:{schema_name})"},
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_catalogs(database_id: int) -> str:
        """List catalogs in a database (for engines that support catalogs).

        Not supported by all engines. PostgreSQL and MySQL typically do not use catalogs.

        Args:
            database_id: Database connection ID.
        """
        result = await client.get(f"/api/v1/database/{database_id}/catalogs/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_connection_info(database_id: int) -> str:
        """Get connection information (URI without password, parameters).

        Args:
            database_id: Database connection ID.
        """
        result = await client.get(f"/api/v1/database/{database_id}/connection")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_function_names(database_id: int) -> str:
        """List available SQL functions in the database.

        Useful for building SQL queries with engine-specific functions.

        Args:
            database_id: Database connection ID.
        """
        result = await client.get(f"/api/v1/database/{database_id}/function_names/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_related_objects(database_id: int) -> str:
        """Get objects related to a database connection (datasets, charts).

        Useful before deleting a connection to understand what will break.

        Args:
            database_id: Database connection ID.
        """
        result = await client.get(f"/api/v1/database/{database_id}/related_objects/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_validate_sql(
        database_id: int,
        sql: str,
        schema: str | None = None,
    ) -> str:
        """Validate SQL query syntax without executing it (EXPLAIN-like check).

        IMPORTANT: not all database engines support SQL validation. PostgreSQL does.

        Args:
            database_id: Database connection ID.
            sql: SQL query to validate.
            schema: Schema for validation context (e.g. "public").
        """
        payload = {"sql": sql}
        if schema is not None:
            payload["schema"] = schema
        result = await client.post(f"/api/v1/database/{database_id}/validate_sql/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_validate_parameters(
        engine: str,
        parameters: dict,
        configuration_method: str = "sqlalchemy_form",
    ) -> str:
        """Validate database connection parameters without creating a connection.

        Args:
            engine: Database engine type: "postgresql", "mysql", "sqlite", "mssql", etc.
            parameters: Connection parameters dictionary:
                {"host": "...", "port": 5432, "database": "...",
                 "username": "...", "password": "..."}
            configuration_method: Configuration method: "sqlalchemy_form" (default)
                or "dynamic_form".
        """
        payload = {
            "engine": engine,
            "parameters": parameters,
            "configuration_method": configuration_method,
        }
        result = await client.post("/api/v1/database/validate_parameters/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_select_star(
        database_id: int,
        table_name: str,
        schema_name: str | None = None,
    ) -> str:
        """Generate a SELECT * SQL query for a table (with LIMIT).

        Useful for quickly inspecting table structure and data.

        Args:
            database_id: Database connection ID.
            table_name: Table name.
            schema_name: Schema (e.g. "public"). If not specified, uses the default schema.
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
        """Get table metadata: columns, data types, indexes, and primary keys.

        Useful for understanding table structure before writing SQL queries.

        Args:
            database_id: Database connection ID.
            table_name: Table name.
            schema_name: Schema (e.g. "public"). If not specified, uses the default schema.
        """
        params = {"name": table_name}
        if schema_name:
            params["schema"] = schema_name
        result = await client.get(
            f"/api/v1/database/{database_id}/table_metadata/",
            params=params,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_database_export(
        database_ids: str,
    ) -> str:
        """Export database connection configurations as a ZIP file.

        IMPORTANT: passwords are NOT exported for security reasons.

        Args:
            database_ids: Comma-separated connection IDs (e.g. "1,2").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        import base64

        params = {"q": f"[{database_ids}]"}
        raw = await client.get_raw("/api/v1/database/export/", params=params)
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
    async def superset_database_available_engines() -> str:
        """List supported database engine types for creating connections.

        Returns available engines: PostgreSQL, MySQL, SQLite, etc.
        Useful for selecting an engine when creating a new connection.
        """
        result = await client.get("/api/v1/database/available/")
        return json.dumps(result, ensure_ascii=False)
