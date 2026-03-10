"""Инструменты для управления группами пользователей в Superset."""

import json


def register_group_tools(mcp):
    from superset_mcp.server import superset_client as client

    # === Группы ===

    @mcp.tool
    async def superset_group_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список групп пользователей Superset.

        Группа объединяет пользователей и роли. Пользователи в группе
        наследуют все роли, назначенные группе.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:name,opr:ct,value:moscow)))
            get_all: Получить ВСЕ записи с автоматической пагинацией.
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all(
                "/api/v1/security/groups/", params=params
            )
        else:
            params = {}
            if q:
                params["q"] = q
            else:
                params["q"] = f"(page:{page},page_size:{page_size})"
            result = await client.get("/api/v1/security/groups/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_get(group_id: int) -> str:
        """Получить детальную информацию о группе по ID.

        Возвращает: название, метку, описание, список ролей и пользователей.

        Args:
            group_id: ID группы (из group_list).
        """
        result = await client.get(f"/api/v1/security/groups/{group_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_create(
        name: str,
        label: str | None = None,
        description: str | None = None,
        roles: list[int] | None = None,
        users: list[int] | None = None,
    ) -> str:
        """Создать новую группу пользователей.

        Группа объединяет пользователей и роли. Пользователи в группе
        автоматически наследуют все роли группы.

        Args:
            name: Уникальное имя группы (напр. "la_region_Московская").
            label: Отображаемая метка (напр. "Московская область").
            description: Описание группы.
            roles: Список ID ролей для назначения группе.
            users: Список ID пользователей для добавления в группу.
        """
        payload: dict = {"name": name}
        if label is not None:
            payload["label"] = label
        if description is not None:
            payload["description"] = description

        result = await client.post(
            "/api/v1/security/groups/", json_data=payload
        )
        group_id = result.get("id")

        # Роли и пользователи назначаются через update (create принимает только name/label/description)
        if group_id and (roles is not None or users is not None):
            update_payload: dict = {}
            if roles is not None:
                update_payload["roles"] = roles
            if users is not None:
                update_payload["users"] = users
            await client.put(
                f"/api/v1/security/groups/{group_id}",
                json_data=update_payload,
            )
            # Получаем полную информацию
            detail = await client.get(f"/api/v1/security/groups/{group_id}")
            return json.dumps(
                {"id": group_id, "result": detail.get("result", {})},
                ensure_ascii=False,
            )

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_update(
        group_id: int,
        name: str | None = None,
        label: str | None = None,
        description: str | None = None,
        roles: list[int] | None = None,
        users: list[int] | None = None,
        confirm_roles_replace: bool = False,
        confirm_users_replace: bool = False,
    ) -> str:
        """Обновить группу. Передавайте только изменяемые поля.

        ВАЖНО: roles ЗАМЕНЯЕТ весь список ролей группы (не добавляет).
        ВАЖНО: users ЗАМЕНЯЕТ весь список пользователей группы (не добавляет).

        Для добавления одной роли/пользователя: получите текущие через group_get,
        добавьте ID в список, передайте полный список.

        Args:
            group_id: ID группы для обновления.
            name: Новое имя группы.
            label: Новая метка.
            description: Новое описание.
            roles: Новый ПОЛНЫЙ список ID ролей (ЗАМЕНЯЕТ все текущие).
            users: Новый ПОЛНЫЙ список ID пользователей (ЗАМЕНЯЕТ всех текущих).
            confirm_roles_replace: Подтверждение замены ролей (ОБЯЗАТЕЛЬНО при roles).
            confirm_users_replace: Подтверждение замены пользователей (ОБЯЗАТЕЛЬНО при users).
        """
        if roles is not None and not confirm_roles_replace:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                current_roles = current.get("roles", [])
                role_names = [f"{r['name']} (id={r['id']})" for r in current_roles]
            except Exception:
                role_names = ["не удалось получить"]
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: roles ЗАМЕНЯЕТ ВСЕ роли группы (ID={group_id}). "
                        f"Текущие роли: {role_names}. "
                        f"Передайте confirm_roles_replace=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        if users is not None and not confirm_users_replace:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                current_users = current.get("users", [])
                user_names = [
                    f"{u['username']} (id={u['id']})" for u in current_users
                ]
            except Exception:
                user_names = ["не удалось получить"]
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: users ЗАМЕНЯЕТ ВСЕХ пользователей группы (ID={group_id}). "
                        f"Текущие пользователи: {user_names}. "
                        f"Передайте confirm_users_replace=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        payload: dict = {}
        if name is not None:
            payload["name"] = name
        if label is not None:
            payload["label"] = label
        if description is not None:
            payload["description"] = description
        if roles is not None:
            payload["roles"] = roles
        if users is not None:
            payload["users"] = users

        if not payload:
            return json.dumps(
                {"error": "Не передано ни одного поля для обновления."},
                ensure_ascii=False,
            )

        result = await client.put(
            f"/api/v1/security/groups/{group_id}", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_delete(
        group_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить группу пользователей.

        Пользователи группы НЕ удаляются, но теряют роли,
        которые были назначены через эту группу.

        Args:
            group_id: ID группы для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/security/groups/{group_id}")
                current = info.get("result", {})
                name = current.get("name", "?")
                roles = [r["name"] for r in current.get("roles", [])]
                users = [u["username"] for u in current.get("users", [])]
            except Exception:
                name = f"ID={group_id}"
                roles = ["не удалось получить"]
                users = ["не удалось получить"]
            return json.dumps(
                {
                    "error": (
                        f"ОТКЛОНЕНО: удаление группы '{name}' (ID={group_id}). "
                        f"Роли: {roles}. Пользователи ({len(users)}): {users[:10]}{'...' if len(users) > 10 else ''}. "
                        f"Передайте confirm_delete=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/security/groups/{group_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_group_add_users(
        group_id: int,
        user_ids: list[int],
    ) -> str:
        """Добавить пользователей в группу (без удаления существующих).

        Удобный инструмент: получает текущих пользователей группы,
        добавляет новых и обновляет группу.

        Args:
            group_id: ID группы.
            user_ids: Список ID пользователей для добавления.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_user_ids = {u["id"] for u in current.get("users", [])}
        new_user_ids = current_user_ids | set(user_ids)

        result = await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"users": sorted(new_user_ids)},
        )

        added = set(user_ids) - current_user_ids
        already = set(user_ids) & current_user_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "added": sorted(added),
                "already_in_group": sorted(already),
                "total_users": len(new_user_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_remove_users(
        group_id: int,
        user_ids: list[int],
    ) -> str:
        """Удалить пользователей из группы (без удаления остальных).

        Args:
            group_id: ID группы.
            user_ids: Список ID пользователей для удаления из группы.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_user_ids = {u["id"] for u in current.get("users", [])}
        new_user_ids = current_user_ids - set(user_ids)

        result = await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"users": sorted(new_user_ids)},
        )

        removed = current_user_ids & set(user_ids)
        not_found = set(user_ids) - current_user_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "removed": sorted(removed),
                "not_in_group": sorted(not_found),
                "total_users": len(new_user_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_add_roles(
        group_id: int,
        role_ids: list[int],
    ) -> str:
        """Добавить роли в группу (без удаления существующих).

        Args:
            group_id: ID группы.
            role_ids: Список ID ролей для добавления.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_role_ids = {r["id"] for r in current.get("roles", [])}
        new_role_ids = current_role_ids | set(role_ids)

        result = await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"roles": sorted(new_role_ids)},
        )

        added = set(role_ids) - current_role_ids
        already = set(role_ids) & current_role_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "added_roles": sorted(added),
                "already_in_group": sorted(already),
                "total_roles": len(new_role_ids),
            },
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_group_remove_roles(
        group_id: int,
        role_ids: list[int],
    ) -> str:
        """Удалить роли из группы (без удаления остальных).

        Args:
            group_id: ID группы.
            role_ids: Список ID ролей для удаления.
        """
        info = await client.get(f"/api/v1/security/groups/{group_id}")
        current = info.get("result", {})
        current_role_ids = {r["id"] for r in current.get("roles", [])}
        new_role_ids = current_role_ids - set(role_ids)

        result = await client.put(
            f"/api/v1/security/groups/{group_id}",
            json_data={"roles": sorted(new_role_ids)},
        )

        removed = current_role_ids & set(role_ids)
        not_found = set(role_ids) - current_role_ids
        return json.dumps(
            {
                "result": "ok",
                "group_id": group_id,
                "group_name": current.get("name", "?"),
                "removed_roles": sorted(removed),
                "not_in_group": sorted(not_found),
                "total_roles": len(new_role_ids),
            },
            ensure_ascii=False,
        )
