"""Tools for system operations: reports, annotations, logs, menu, assets."""

import base64
import json

from mcp_superset.tools.helpers import parse_json_arg


def register_system_tools(mcp):
    from mcp_superset.server import superset_client as client

    # === Reports / Alerts ===

    @mcp.tool
    async def superset_report_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List Superset reports and alerts.

        Reports send periodic screenshots of dashboards/charts.
        Alerts send notifications when a SQL condition is met.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By name: (filters:!((col:name,opr:ct,value:search_term)))
                - By type: (filters:!((col:type,opr:eq,value:Report)))
                - Active only: (filters:!((col:active,opr:eq,value:!t)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/report/", params=params)
        else:
            result = await client.get_page("/api/v1/report/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_get(report_id: int) -> str:
        """Get detailed information about a report/alert by ID.

        IMPORTANT: if the ID is unknown, call superset_report_list first.

        Args:
            report_id: Report ID (integer from report_list result).
        """
        result = await client.get(f"/api/v1/report/{report_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_create(
        name: str,
        crontab: str,
        report_type: str = "Report",
        dashboard: int | None = None,
        chart: int | None = None,
        database: int | None = None,
        sql: str | None = None,
        recipients: str | None = None,
        active: bool = True,
    ) -> str:
        """Create a report (periodic delivery) or alert (SQL-condition based).

        For Report: specify dashboard or chart — Superset will send a screenshot on schedule.
        For Alert: specify database and sql — Superset checks the condition and notifies on trigger.

        Args:
            name: Report/alert name.
            crontab: Cron schedule. Examples:
                - "0 9 * * *" — every day at 9:00
                - "0 9 * * 1" — every Monday at 9:00
                - "0 */6 * * *" — every 6 hours
            report_type: Type: "Report" (periodic delivery, default) or "Alert" (condition-based).
            dashboard: Dashboard ID for screenshot (for Report).
            chart: Chart ID for screenshot (for Report).
            database: Database connection ID (for Alert — SQL condition).
            sql: SQL query for condition check (for Alert).
                The alert triggers when the query returns a non-empty result.
            recipients: JSON string with recipient list. Format:
                [{"type": "Email", "recipient_config_json": {"target": "user@example.com"}}]
            active: Whether active (default True).
        """
        payload = {
            "name": name,
            "type": report_type,
            "crontab": crontab,
            "active": active,
        }
        if dashboard is not None:
            payload["dashboard"] = dashboard
        if chart is not None:
            payload["chart"] = chart
        if database is not None:
            payload["database"] = database
        if sql is not None:
            payload["sql"] = sql
        if recipients is not None:
            parsed, err = parse_json_arg(recipients, "recipients")
            if err:
                return json.dumps({"error": err}, ensure_ascii=False)
            payload["recipients"] = parsed
        result = await client.post("/api/v1/report/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_update(
        report_id: int,
        name: str | None = None,
        crontab: str | None = None,
        active: bool | None = None,
        recipients: str | None = None,
    ) -> str:
        """Update a report/alert. Pass only the fields to change.

        Args:
            report_id: Report ID to update.
            name: New name.
            crontab: New cron schedule (e.g. "0 9 * * *").
            active: Enable/disable the report.
            recipients: JSON string with new recipient list (REPLACES all current recipients).
        """
        payload = {}
        if name is not None:
            payload["name"] = name
        if crontab is not None:
            payload["crontab"] = crontab
        if active is not None:
            payload["active"] = active
        if recipients is not None:
            parsed, err = parse_json_arg(recipients, "recipients")
            if err:
                return json.dumps({"error": err}, ensure_ascii=False)
            payload["recipients"] = parsed
        result = await client.put(f"/api/v1/report/{report_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_delete(
        report_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete a report/alert. The delivery schedule will be stopped.

        Args:
            report_id: Report ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/report/{report_id}")
                r = info.get("result", {})
                name = r.get("name", "?")
                rtype = r.get("type", "?")
                active = r.get("active", "?")
            except Exception:
                name = f"ID={report_id}"
                rtype = active = "?"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deletion of {rtype} '{name}' "
                        f"(ID={report_id}, active={active}). "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/report/{report_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Annotations ===

    @mcp.tool
    async def superset_annotation_layer_list(
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """List annotation layers.

        An annotation layer is a container for annotations (timeline events)
        that can be overlaid on charts.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            result = await client.get_all("/api/v1/annotation_layer/")
        else:
            result = await client.get_page("/api/v1/annotation_layer/", page, page_size)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_list(
        annotation_layer_id: int,
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """List annotations in the specified layer.

        Args:
            annotation_layer_id: Annotation layer ID (from annotation_layer_list).
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            result = await client.get_all(
                f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
            )
        else:
            result = await client.get_page(
                f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
                page,
                page_size,
            )
        return json.dumps(result, ensure_ascii=False)

    # === Activity & Logs ===

    @mcp.tool
    async def superset_recent_activity(
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """Get recent activity of the current user (views, edits).

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            result = await client.get_all("/api/v1/log/recent_activity/")
        else:
            # recent_activity is a CUSTOM endpoint (not a standard FAB list) — it
            # reads page/page_size from plain query args, NOT from RISON q.
            params = {"page": page, "page_size": page_size}
            result = await client.get("/api/v1/log/recent_activity/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_log_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Get the audit log of all Superset user actions.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By user: (filters:!((col:user,opr:rel_o_m,value:1)))
                - By action: (filters:!((col:action,opr:ct,value:explore)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/log/", params=params)
        else:
            result = await client.get_page("/api/v1/log/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    # === Menu & System ===

    @mcp.tool
    async def superset_get_menu() -> str:
        """Get the Superset navigation menu structure.

        Useful for understanding available sections and the current user's permissions.
        """
        result = await client.get("/api/v1/menu/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_get_base_url() -> str:
        """Get the base URL of the configured Superset instance.

        Returns the URL used by the MCP server to connect to Superset.
        """
        from mcp_superset.server import SUPERSET_BASE_URL

        return json.dumps({"base_url": SUPERSET_BASE_URL}, ensure_ascii=False)

    # === Annotation Layer CRUD ===

    @mcp.tool
    async def superset_annotation_layer_create(
        name: str,
        descr: str | None = None,
    ) -> str:
        """Create a new annotation layer.

        A layer is a container for annotations that can be overlaid on time-series charts.

        Args:
            name: Layer name.
            descr: Layer description (optional).
        """
        payload = {"name": name}
        if descr is not None:
            payload["descr"] = descr
        result = await client.post(
            "/api/v1/annotation_layer/",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_layer_get(
        annotation_layer_id: int,
    ) -> str:
        """Get annotation layer information by ID.

        IMPORTANT: if the ID is unknown, call annotation_layer_list first.

        Args:
            annotation_layer_id: Layer ID (from annotation_layer_list).
        """
        result = await client.get(f"/api/v1/annotation_layer/{annotation_layer_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_layer_update(
        annotation_layer_id: int,
        name: str | None = None,
        descr: str | None = None,
    ) -> str:
        """Update an annotation layer. Pass only the fields to change.

        Args:
            annotation_layer_id: Layer ID to update.
            name: New layer name.
            descr: New layer description.
        """
        payload = {}
        if name is not None:
            payload["name"] = name
        if descr is not None:
            payload["descr"] = descr
        result = await client.put(
            f"/api/v1/annotation_layer/{annotation_layer_id}",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_layer_delete(
        annotation_layer_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete an annotation layer along with all its annotations.

        CRITICAL: deletes the layer AND all annotations within it permanently.

        Args:
            annotation_layer_id: Layer ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/annotation_layer/{annotation_layer_id}")
                name = info.get("result", {}).get("name", "?")
                annotations = await client.get(
                    f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
                    params={"page": 0, "page_size": 1},
                )
                ann_count = annotations.get("count", "?")
            except Exception:
                name = f"ID={annotation_layer_id}"
                ann_count = "?"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deletion of annotation layer '{name}' "
                        f"(ID={annotation_layer_id}) along with {ann_count} annotations. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/annotation_layer/{annotation_layer_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Annotation CRUD ===

    @mcp.tool
    async def superset_annotation_create(
        annotation_layer_id: int,
        short_descr: str,
        start_dttm: str,
        end_dttm: str,
        long_descr: str | None = None,
        json_metadata: str | None = None,
    ) -> str:
        """Create an annotation (timeline event) in the specified layer.

        Annotations are displayed as vertical lines or areas on time-series charts.

        Args:
            annotation_layer_id: Annotation layer ID (from annotation_layer_list).
            short_descr: Brief event description (displayed on the chart).
            start_dttm: Start datetime in ISO format. Example: "2024-01-01T00:00:00"
            end_dttm: End datetime in ISO format. Example: "2024-01-01T23:59:59"
                For a point-in-time event, set start_dttm = end_dttm.
            long_descr: Detailed event description (optional).
            json_metadata: JSON string with additional metadata (optional).
        """
        payload = {
            "short_descr": short_descr,
            "start_dttm": start_dttm,
            "end_dttm": end_dttm,
        }
        if long_descr is not None:
            payload["long_descr"] = long_descr
        if json_metadata is not None:
            payload["json_metadata"] = json_metadata
        result = await client.post(
            f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_get(
        annotation_layer_id: int,
        annotation_id: int,
    ) -> str:
        """Get an annotation by ID.

        Args:
            annotation_layer_id: Annotation layer ID.
            annotation_id: Annotation ID (from annotation_list).
        """
        result = await client.get(f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/{annotation_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_update(
        annotation_layer_id: int,
        annotation_id: int,
        short_descr: str | None = None,
        start_dttm: str | None = None,
        end_dttm: str | None = None,
        long_descr: str | None = None,
    ) -> str:
        """Update an annotation. Pass only the fields to change.

        Args:
            annotation_layer_id: Annotation layer ID.
            annotation_id: Annotation ID to update.
            short_descr: New brief description.
            start_dttm: New start datetime (ISO format: "2024-01-01T00:00:00").
            end_dttm: New end datetime (ISO format).
            long_descr: New detailed description.
        """
        payload = {}
        if short_descr is not None:
            payload["short_descr"] = short_descr
        if start_dttm is not None:
            payload["start_dttm"] = start_dttm
        if end_dttm is not None:
            payload["end_dttm"] = end_dttm
        if long_descr is not None:
            payload["long_descr"] = long_descr
        result = await client.put(
            f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/{annotation_id}",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_delete(
        annotation_layer_id: int,
        annotation_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Delete an annotation from a layer.

        Args:
            annotation_layer_id: Annotation layer ID.
            annotation_id: Annotation ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/{annotation_id}")
                descr = info.get("result", {}).get("short_descr", "?")
            except Exception:
                descr = f"ID={annotation_id}"
            return json.dumps(
                {
                    "error": (
                        f"REJECTED: deletion of annotation '{descr}' "
                        f"(ID={annotation_id}) from layer {annotation_layer_id}. "
                        f"Pass confirm_delete=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/{annotation_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Assets Export/Import ===

    @mcp.tool
    async def superset_assets_export() -> str:
        """Export ALL Superset assets into a single ZIP file.

        Includes: dashboards, charts, datasets, database connections (without passwords).
        Useful for backup or migration between instances.

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        raw = await client.get_raw("/api/v1/assets/export/")
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
    async def superset_assets_import(
        file_path: str,
        overwrite: bool = False,
        confirm_overwrite: bool = False,
    ) -> str:
        """Import Superset assets from a ZIP file (created via assets_export).

        CRITICAL: overwrite=True overwrites ALL matching objects
        (dashboards, charts, datasets, databases). This is irreversible.

        Args:
            file_path: Absolute path to the ZIP file on disk.
            overwrite: Overwrite existing objects with matching UUIDs (default False).
            confirm_overwrite: Overwrite confirmation (REQUIRED when overwrite=True).
        """
        if overwrite and not confirm_overwrite:
            return json.dumps(
                {
                    "error": (
                        "REJECTED: overwrite=True without confirm_overwrite=True. "
                        "assets_import with overwrite=True overwrites ALL matching "
                        "objects (dashboards, charts, datasets, database connections). "
                        "This may roll back the entire Superset to the state from the ZIP file. "
                        "Pass confirm_overwrite=True to confirm."
                    )
                },
                ensure_ascii=False,
            )

        with open(file_path, "rb") as f:
            files = {"bundle": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/assets/import/",
                files=files,
                data=data,
            )
        return json.dumps(result, ensure_ascii=False)
