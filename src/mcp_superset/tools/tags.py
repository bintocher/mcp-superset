"""Tools for managing tags in Superset."""

import json

from mcp_superset.tools.helpers import parse_json_arg


def register_tag_tools(mcp):
    from mcp_superset.server import superset_client as client

    @mcp.tool
    async def superset_tag_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """List Superset tags.

        Tags are used to group and organize dashboards, charts, and datasets.
        IMPORTANT: always call before tag_get/tag_update to find current IDs.
        When creating a tag, the API returns {} without an ID — use tag_list to get the ID.

        Args:
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            q: RISON filter for search. Examples:
                - By name: (filters:!((col:name,opr:ct,value:search_term)))
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/tag/", params=params)
        else:
            result = await client.get_page("/api/v1/tag/", page, page_size, q)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_get(tag_id: int) -> str:
        """Get tag information by ID.

        IMPORTANT: if the ID is unknown, call superset_tag_list first.

        Args:
            tag_id: Tag ID (integer from tag_list result).
        """
        result = await client.get(f"/api/v1/tag/{tag_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_create(
        name: str,
        description: str | None = None,
        objects_to_tag: str | None = None,
    ) -> str:
        """Create a new tag and optionally attach it to Superset objects.

        IMPORTANT: Superset API returns {} on creation (without tag ID).
        To get the new tag's ID, call superset_tag_list after creation.

        Object attachment is only possible during creation via objects_to_tag.
        Direct attachment endpoints (POST/DELETE /api/v1/tag/{type}/{id}/) do not work in 6.0.1.

        Args:
            name: Tag name.
            description: Tag description (optional).
            objects_to_tag: JSON string with a list of objects to tag. Format:
                [["dashboard", 1], ["chart", 5], ["dataset", 3], ["saved_query", 2]]
                Each element is a pair [object_type, object_id].
                Allowed types: "dashboard", "chart", "dataset", "saved_query".
        """
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        if objects_to_tag is not None:
            parsed, err = parse_json_arg(objects_to_tag, "objects_to_tag")
            if err:
                return json.dumps({"error": err}, ensure_ascii=False)
            payload["objects_to_tag"] = parsed
        result = await client.post("/api/v1/tag/", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_tag_update(
        tag_id: int,
        name: str,
        description: str | None = None,
    ) -> str:
        """Update a tag (rename or change description).

        IMPORTANT: the name field is REQUIRED in Superset 6.0.1 — even if the name is not
        changing, it must be provided. Without it, Superset returns 500.

        Args:
            tag_id: Tag ID to update.
            name: Tag name (REQUIRED, even if unchanged).
            description: New description (optional).
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
        """Delete a tag. All object attachments will be removed.

        Args:
            tag_id: Tag ID to delete.
            confirm_delete: Deletion confirmation (REQUIRED).
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
                        f"REJECTED: deletion of tag '{name}' (ID={tag_id}) "
                        f"and all its object attachments. "
                        f"Pass confirm_delete=True to confirm."
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
        """Get objects tagged with the specified tags.

        Returns dashboards, charts, datasets, and queries with the specified tags.

        Args:
            tags: Comma-separated tag names (e.g. "analytics,production").
                If not specified, returns all tagged objects.
            page: Page number (starting from 0).
            page_size: Number of records per page (max 100).
            get_all: Fetch ALL records with automatic pagination (ignores page/page_size).
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
        """Bulk-create tags with object attachments.

        Allows creating multiple tags and attaching them to objects in a single request.

        Args:
            tags: JSON string with a list of tags. Format:
                [
                    {"name": "production", "objects_to_tag": [["dashboard", 1], ["chart", 5]]},
                    {"name": "analytics", "objects_to_tag": [["dataset", 3]]}
                ]
                objects_to_tag: pairs of [object_type, object_id].
                Allowed types: "dashboard", "chart", "dataset", "saved_query".
        """
        parsed, err = parse_json_arg(tags, "tags")
        if err:
            return json.dumps({"error": err}, ensure_ascii=False)
        payload = {"tags": parsed}
        result = await client.post("/api/v1/tag/bulk_create", json_data=payload)
        return json.dumps(result, ensure_ascii=False)
