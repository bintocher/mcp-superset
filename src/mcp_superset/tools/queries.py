"""Tools for SQL Lab and query management in Superset."""

import json
import re


def _strip_sql_comments(sql: str) -> str:
    """Strip SQL comments (single-line -- and multi-line /* */).

    Required for correct DDL/DML detection — without this, a comment before
    a dangerous command bypasses the block: '/* */ DROP TABLE ...'

    Args:
        sql: Raw SQL string potentially containing comments.

    Returns:
        Cleaned SQL string with all comments removed.
    """
    # Remove multi-line comments /* ... */
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # Remove single-line comments -- ...
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


# DDL/DML keywords that must never be executed via MCP. Detected as
# WHOLE WORDS ANYWHERE in the query (not just at the start) to prevent
# bypasses via CTE (WITH ... DELETE), statement chaining (SELECT 1; DROP ...),
# parentheses ((DELETE FROM t)), a leading EXPLAIN/ANALYZE, or a PL/pgSQL
# anonymous block (DO $$ BEGIN EXECUTE '...' END $$) that hides the DDL in a
# string literal. Order matters: keywords that subsume others (TRUNCATE, MERGE)
# come first so the rejection message names the most specific operation.
_DANGEROUS_KEYWORDS = (
    "DROP",
    "TRUNCATE",
    "MERGE",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "DO",  # PL/pgSQL anonymous block
    "EXECUTE",  # dynamic SQL inside a DO block
)


def _strip_sql_strings(sql: str) -> str:
    """Remove single-quoted string literals so keywords inside them don't
    trigger false positives (and so they can't hide a chained statement).

    Handles SQL-standard escaped quotes ('' inside a literal).

    Args:
        sql: SQL string (ideally with comments already stripped).

    Returns:
        SQL with single-quoted literals replaced by a space.
    """
    return re.sub(r"'(?:''|[^'])*'", " ", sql)


def _detect_dangerous_sql(sql: str) -> str | None:
    """Return the first DDL/DML keyword found in the query, or None if safe.

    Strips comments and string literals first, then matches each dangerous
    keyword as a whole word anywhere in the statement. Word boundaries keep
    legitimate identifiers safe (e.g. update_date, deleted_at, call_datetime).

    Args:
        sql: Raw SQL query.

    Returns:
        The matched dangerous keyword (uppercase), or None.
    """
    cleaned = _strip_sql_strings(_strip_sql_comments(sql)).upper()
    for keyword in _DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", cleaned):
            return keyword
    return None


def register_query_tools(mcp):
    from mcp_superset.server import superset_client as client

    @mcp.tool
    async def superset_sqllab_execute(
        database_id: int,
        sql: str,
        schema: str | None = None,
        catalog: str | None = None,
        tab_name: str | None = None,
        template_params: str | None = None,
    ) -> str:
        """Execute a SQL query via SQL Lab and return the result.

        IMPORTANT: before executing, make sure the SQL query is correct.
        Use superset_database_table_metadata or superset_database_tables
        to find actual table and column names.
        Maximum 1000 rows in the result (queryLimit).

        Args:
            database_id: Database connection ID (from superset_database_list).
            sql: SQL query to execute. Examples:
                - SELECT * FROM public.my_table LIMIT 10
                - SELECT count(*) FROM source.stat
            schema: Default schema for the query (e.g. "public", "source").
                If not specified, the database default schema is used.
            catalog: Database catalog (for databases with catalog support, optional).
            tab_name: Tab name in SQL Lab UI (optional, for organization).
            template_params: JSON string with Jinja template parameters (optional).
                Example: '{"start_date": "2024-01-01"}'
        """
        # Guard against DDL/DML. Detects dangerous keywords as whole words
        # ANYWHERE in the query (after stripping comments and string literals),
        # so CTE/chained/parenthesised/EXPLAIN-prefixed bypasses are caught.
        # NOTE: this is a best-effort safety net, not a full SQL parser — the
        # authoritative protection is allow_dml=false on the DB connection.
        dangerous = _detect_dangerous_sql(sql)
        if dangerous:
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: SQL query contains '{dangerous}' — "
                        f"this is a modifying operation (DDL/DML). "
                        f"Executing such queries via MCP is prohibited. "
                        f"If the operation is truly needed — execute it "
                        f"directly via SQL Lab in the Superset UI."
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
        """Format a SQL query (pretty print with indentation).

        Args:
            sql: SQL query to format.
        """
        result = await client.post("/api/v1/sqllab/format_sql/", json_data={"sql": sql})
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_results(results_key: str) -> str:
        """Retrieve results of a previously executed query by key.

        IMPORTANT: requires a configured Results Backend (Redis/S3) in Superset.
        Without it, returns 500. The key is taken from the results_key field of sqllab_execute response.

        Args:
            results_key: Results key from the superset_sqllab_execute response.
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
        """Estimate the cost of executing a SQL query (EXPLAIN).

        Not all database engines support this feature. PostgreSQL does.

        Args:
            database_id: Database connection ID.
            sql: SQL query to estimate.
            schema: Schema for context (e.g. "public").
        """
        payload = {"database_id": database_id, "sql": sql}
        if schema is not None:
            payload["schema"] = schema
        result = await client.post("/api/v1/sqllab/estimate/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_sqllab_export_csv(client_id: str) -> str:
        """Export query results to CSV format.

        IMPORTANT: requires a configured Results Backend (Redis/S3) in Superset.

        Args:
            client_id: Query client_id (from the superset_sqllab_execute result).
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
        """Retrieve the history of executed SQL queries.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By status: (filters:!((col:status,opr:eq,value:success)))
                - By database: (filters:!((col:database,opr:rel_o_m,value:1)))
            get_all: Retrieve ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/query/", params=params)
        else:
            result = await client.get_page("/api/v1/query/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_query_get(query_id: int) -> str:
        """Retrieve detailed information about a query from the history by ID.

        Args:
            query_id: Query ID (integer from query_list result).
        """
        result = await client.get(f"/api/v1/query/{query_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_query_stop(query_id: str) -> str:
        """Stop a running asynchronous query.

        Args:
            query_id: Query client_id to stop (string from sqllab_execute result).
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
        """Retrieve a list of saved SQL queries.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By label: (filters:!((col:label,opr:ct,value:search_term)))
                - By database: (filters:!((col:database,opr:rel_o_m,value:1)))
            get_all: Retrieve ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/saved_query/", params=params)
        else:
            result = await client.get_page("/api/v1/saved_query/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_saved_query_create(
        label: str,
        db_id: int,
        sql: str,
        schema: str | None = None,
        description: str | None = None,
    ) -> str:
        """Create a saved SQL query for reuse.

        Args:
            label: Query name (displayed in the list).
            db_id: Database connection ID (from superset_database_list).
            sql: SQL query to save.
            schema: Default schema (e.g. "public").
            description: Query description.
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
        """Retrieve a saved query by ID: SQL text, schema, description.

        Args:
            saved_query_id: Saved query ID (from saved_query_list).
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
        """Update a saved query. Pass only the fields to change.

        Args:
            saved_query_id: Saved query ID.
            label: New name.
            sql: New SQL query.
            schema: New default schema.
            description: New description.
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
        """Delete a saved query.

        Args:
            saved_query_id: Saved query ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
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
                        f"REJECTED: deletion of saved query '{label}' "
                        f"(ID={saved_query_id}, DB={db_name}). "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/saved_query/{saved_query_id}")
        return json.dumps(result, ensure_ascii=False)
