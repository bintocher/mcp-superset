"""Инструменты для управления безопасностью: пользователи, роли, права, RLS."""

import json
from typing import Any


async def _find_datasource_permissions(
    client: Any,
    dataset_ids: set[int],
) -> dict[int, int]:
    """Находит permission_view_menu_id для datasource_access на указанные датасеты.

    Пагинирует через /api/v1/security/permissions-resources/ и ищет записи
    вида datasource_access + [Database].[table](id:N).

    Args:
        client: SupersetClient.
        dataset_ids: Множество ID датасетов для поиска.

    Returns:
        Словарь {dataset_id: permission_view_menu_id}.
    """
    found: dict[int, int] = {}
    page = 0
    while page < 50:  # защита от бесконечного цикла
        try:
            resp = await client.get(
                "/api/v1/security/permissions-resources/",
                params={"q": f"(page:{page},page_size:100)"},
            )
        except Exception:
            break
        items = resp.get("result", [])
        if not items:
            break
        for item in items:
            perm_name = item.get("permission", {}).get("name", "")
            view_name = item.get("view_menu", {}).get("name", "")
            if perm_name == "datasource_access":
                for ds_id in dataset_ids:
                    if f"(id:{ds_id})" in view_name:
                        found[ds_id] = item["id"]
        # Все найдены — выходим раньше
        if found.keys() >= dataset_ids:
            break
        if len(items) < 100:
            break
        page += 1
    return found


def register_security_tools(mcp):
    from superset_mcp.server import superset_client as client

    # === Текущий пользователь ===

    @mcp.tool
    async def superset_get_current_user() -> str:
        """Получить информацию о текущем аутентифицированном пользователе (mcp_service).

        Возвращает: username, имя, email, роли, статус активности.
        """
        result = await client.get("/api/v1/me/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_get_current_user_roles() -> str:
        """Получить список ролей текущего пользователя (mcp_service).

        Возвращает ID и названия всех назначенных ролей.
        """
        result = await client.get("/api/v1/me/roles/")
        return json.dumps(result, ensure_ascii=False)

    # === Пользователи ===

    @mcp.tool
    async def superset_user_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список пользователей Superset.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По username: (filters:!((col:username,opr:ct,value:admin)))
                - Активные: (filters:!((col:active,opr:eq,value:!t)))
                - По роли: (filters:!((col:roles,opr:rel_m_m,value:1)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/users/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/security/users/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_get(user_id: int) -> str:
        """Получить детальную информацию о пользователе по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_user_list.

        Args:
            user_id: ID пользователя (целое число из результата user_list).
        """
        result = await client.get(f"/api/v1/security/users/{user_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_create(
        first_name: str,
        last_name: str,
        username: str,
        email: str,
        password: str,
        roles: list[int] | None = None,
        active: bool = True,
    ) -> str:
        """Создать нового пользователя Superset.

        Args:
            first_name: Имя пользователя.
            last_name: Фамилия пользователя.
            username: Логин для входа (уникальный).
            email: Email (уникальный).
            password: Пароль.
            roles: Список ID ролей для назначения (из superset_role_list).
                Если не указан — будет назначена роль по умолчанию (Public).
            active: Активен ли аккаунт (по умолчанию True).
        """
        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "email": email,
            "password": password,
            "active": active,
        }
        if roles is not None:
            payload["roles"] = roles
        result = await client.post(
            "/api/v1/security/users/", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_update(
        user_id: int,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        roles: list[int] | None = None,
        active: bool | None = None,
        confirm_roles_replace: bool = False,
    ) -> str:
        """Обновить пользователя. Передавайте только изменяемые поля.

        ВАЖНО: roles ЗАМЕНЯЕТ весь список ролей (не добавляет).
        Для добавления одной роли: получите текущие через user_get,
        добавьте ID в список, передайте полный список.

        Args:
            user_id: ID пользователя для обновления.
            first_name: Новое имя.
            last_name: Новая фамилия.
            email: Новый email (должен быть уникальным).
            roles: Новый список ID ролей (ЗАМЕНЯЕТ все текущие роли).
            active: Активировать/деактивировать аккаунт.
            confirm_roles_replace: Подтверждение замены ролей (ОБЯЗАТЕЛЬНО при roles).
        """
        # Защита от случайной потери ролей
        if roles is not None and not confirm_roles_replace:
            try:
                user_info = await client.get(f"/api/v1/security/users/{user_id}")
                user = user_info.get("result", {})
                current_roles = [
                    {"id": r["id"], "name": r.get("name", "?")}
                    for r in user.get("roles", [])
                ]
            except Exception:
                current_roles = "не удалось получить"
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: roles ЗАМЕНИТ все текущие роли пользователя. "
                    f"Текущие роли: {current_roles}. "
                    f"Запрошенные роли: {roles}. "
                    f"Для добавления одной роли — включите её ID в полный список. "
                    f"Передайте confirm_roles_replace=True для подтверждения."
                )
            }, ensure_ascii=False)

        payload = {}
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if email is not None:
            payload["email"] = email
        if roles is not None:
            payload["roles"] = roles
        if active is not None:
            payload["active"] = active
        result = await client.put(
            f"/api/v1/security/users/{user_id}", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_user_delete(
        user_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить пользователя Superset. Необратимая операция.

        КРИТИЧНО: удаление текущего сервисного аккаунта (mcp_service)
        заблокирует весь MCP-сервер. Удаление владельцев дашбордов может
        изменить доступ к ним.

        Args:
            user_id: ID пользователя для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            # Получаем информацию о пользователе для предупреждения
            try:
                user_info = await client.get(f"/api/v1/security/users/{user_id}")
                user = user_info.get("result", {})
                username = user.get("username", "?")
                roles = [r.get("name", "?") for r in user.get("roles", [])]
            except Exception:
                username = f"ID={user_id}"
                roles = []
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление пользователя '{username}' "
                    f"(роли: {roles}) необратимо. "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        # Защита от удаления текущего сервисного аккаунта
        try:
            me = await client.get("/api/v1/me/")
            me_result = me.get("result", {})
            if me_result.get("pk") == user_id or me_result.get("id") == user_id:
                return json.dumps({
                    "error": (
                        "ЗАБЛОКИРОВАНО: нельзя удалить текущий сервисный аккаунт "
                        f"('{me_result.get('username', 'mcp_service')}'). "
                        "Это заблокирует весь MCP-сервер."
                    )
                }, ensure_ascii=False)
        except Exception:
            pass

        result = await client.delete(f"/api/v1/security/users/{user_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Роли ===

    @mcp.tool
    async def superset_role_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список ролей Superset.

        Стандартные роли: Admin, Alpha, Gamma, sql_lab, Public.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:name,opr:ct,value:admin)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/security/roles/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/security/roles/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_get(role_id: int) -> str:
        """Получить информацию о роли по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_role_list.

        Args:
            role_id: ID роли (целое число из результата role_list).
        """
        result = await client.get(f"/api/v1/security/roles/{role_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_create(name: str) -> str:
        """Создать новую роль (без прав). Права добавляются через role_permission_add.

        Args:
            name: Название роли (уникальное).
        """
        result = await client.post(
            "/api/v1/security/roles/", json_data={"name": name}
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_update(role_id: int, name: str) -> str:
        """Переименовать роль.

        Args:
            role_id: ID роли для переименования.
            name: Новое название роли.
        """
        result = await client.put(
            f"/api/v1/security/roles/{role_id}", json_data={"name": name}
        )
        return json.dumps(result, ensure_ascii=False)

    # Защищённые роли, которые нельзя удалять
    _PROTECTED_ROLE_NAMES = frozenset({
        "Admin", "Alpha", "Gamma", "Public", "sql_lab",
        "no_access", "la_region_all",
    })
    _PROTECTED_ROLE_PREFIXES = ("la_report_", "la_region_", "la_developer")

    @mcp.tool
    async def superset_role_delete(
        role_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить роль. Пользователи с этой ролью потеряют связанные права.

        ЗАБЛОКИРОВАНО для системных ролей: Admin, Alpha, Gamma, Public,
        sql_lab, no_access, la_report_*, la_region_*, la_developer.

        Args:
            role_id: ID роли для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        # Получаем информацию о роли
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", "?")
        except Exception:
            role_name = f"ID={role_id}"

        # Блокировка защищённых ролей
        if role_name in _PROTECTED_ROLE_NAMES or any(
            role_name.startswith(p) for p in _PROTECTED_ROLE_PREFIXES
        ):
            return json.dumps({
                "error": (
                    f"ЗАБЛОКИРОВАНО: роль '{role_name}' (ID={role_id}) "
                    f"является системной или частью RLS-архитектуры проекта. "
                    f"Удаление этой роли может нарушить доступ пользователей "
                    f"к дашбордам или снять RLS-защиту данных."
                )
            }, ensure_ascii=False)

        if not confirm_delete:
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление роли '{role_name}' (ID={role_id}). "
                    f"Все пользователи с этой ролью потеряют связанные права. "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        result = await client.delete(f"/api/v1/security/roles/{role_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Права (Permissions) ===

    @mcp.tool
    async def superset_permission_list(
        page: int = 0,
        page_size: int = 100,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список всех доступных прав (permission_view_menu) в Superset.

        Каждое право — комбинация действия (can_read, can_write, can_explore) и ресурса.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (по умолчанию 100).
            q: RISON-фильтр для поиска.
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all(
                "/api/v1/security/permissions/", params=params
            )
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get(
                "/api/v1/security/permissions/", params=params
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_permissions_get(role_id: int) -> str:
        """Получить текущий список прав роли.

        ВАЖНО: вызывайте ПЕРЕД role_permission_add, чтобы не потерять существующие права.

        Args:
            role_id: ID роли.
        """
        result = await client.get(
            f"/api/v1/security/roles/{role_id}/permissions/"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_role_permission_add(
        role_id: int,
        permission_view_menu_ids: list[int],
        confirm_full_replace: bool = False,
    ) -> str:
        """Установить список прав для роли (ПОЛНАЯ ЗАМЕНА).

        ВНИМАНИЕ: этот эндпоинт ЗАМЕНЯЕТ ВСЕ права роли на переданный список!
        Чтобы ДОБАВИТЬ одно право, нужно:
        1. Вызвать superset_role_permissions_get — получить текущие ID прав
        2. Добавить новый ID в список
        3. Передать ПОЛНЫЙ список в этот инструмент с confirm_full_replace=True

        Args:
            role_id: ID роли.
            permission_view_menu_ids: ПОЛНЫЙ список ID прав для роли.
                ID прав можно получить через superset_permission_list.
            confirm_full_replace: Подтверждение полной замены прав (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_full_replace:
            return json.dumps({
                "error": (
                    "ОТКЛОНЕНО: не передан confirm_full_replace=True. "
                    "POST /api/v1/security/roles/{id}/permissions ЗАМЕНЯЕТ ВСЕ "
                    "права роли на переданный список. Для добавления одного права: "
                    "1) Получите текущие через role_permissions_get, "
                    "2) Добавьте новый ID в список, "
                    "3) Передайте ПОЛНЫЙ список с confirm_full_replace=True."
                )
            }, ensure_ascii=False)

        result = await client.post(
            f"/api/v1/security/roles/{role_id}/permissions",
            json_data={"permission_view_menu_ids": permission_view_menu_ids},
        )
        return json.dumps(result, ensure_ascii=False)

    # === Управление доступом к дашбордам ===

    @mcp.tool
    async def superset_dashboard_grant_role_access(
        dashboard_id: int,
        role_id: int,
        confirm_grant: bool = False,
    ) -> str:
        """Выдать роли доступ к дашборду: автоматически найти все датасеты
        дашборда и добавить datasource_access в права роли.

        Инструмент автоматически:
        1. Находит все датасеты, используемые чартами дашборда
        2. Находит permission_view_menu_id для datasource_access каждого датасета
        3. Проверяет, какие права уже есть у роли
        4. Добавляет недостающие datasource_access к существующим правам роли
        5. Проверяет наличие RLS-правил на датасетах и предупреждает

        Без confirm_grant=True покажет план действий (dry-run).

        Args:
            dashboard_id: ID дашборда (из dashboard_list).
            role_id: ID роли, которой выдаём доступ (из role_list).
            confirm_grant: True для применения изменений. False — только показать план.
        """
        errors: list[str] = []

        # 1. Проверяем дашборд
        try:
            dash_info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            dash = dash_info.get("result", {})
            dash_title = dash.get("dashboard_title", f"ID={dashboard_id}")
            dash_slug = dash.get("slug", "")
        except Exception as e:
            return json.dumps({
                "error": f"Дашборд ID={dashboard_id} не найден: {e}"
            }, ensure_ascii=False)

        # 2. Проверяем роль
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
        except Exception as e:
            return json.dumps({
                "error": f"Роль ID={role_id} не найдена: {e}"
            }, ensure_ascii=False)

        # 3. Получаем датасеты дашборда
        try:
            ds_resp = await client.get(
                f"/api/v1/dashboard/{dashboard_id}/datasets"
            )
            datasets = ds_resp.get("result", [])
        except Exception as e:
            return json.dumps({
                "error": (
                    f"Не удалось получить датасеты дашборда "
                    f"'{dash_title}': {e}"
                )
            }, ensure_ascii=False)

        if not datasets:
            return json.dumps({
                "error": (
                    f"Дашборд '{dash_title}' (ID={dashboard_id}) не содержит "
                    f"датасетов. Возможно, на нём нет чартов."
                )
            }, ensure_ascii=False)

        dataset_ids = {ds["id"] for ds in datasets}
        dataset_names = {
            ds["id"]: f"{ds.get('schema', '?')}.{ds.get('table_name', '?')}"
            for ds in datasets
        }

        # 4. Находим datasource_access для каждого датасета
        ds_perms = await _find_datasource_permissions(client, dataset_ids)

        missing_ds = dataset_ids - ds_perms.keys()
        if missing_ds:
            missing_names = [
                f"{dataset_names.get(d, '?')} (id:{d})" for d in missing_ds
            ]
            errors.append(
                f"Не найден datasource_access для датасетов: "
                f"{', '.join(missing_names)}. "
                f"Возможно, датасеты были созданы недавно и Superset ещё "
                f"не сгенерировал permission_view_menu. "
                f"Попробуйте открыть датасет в UI Superset."
            )

        # 5. Получаем текущие права роли
        try:
            role_perms_resp = await client.get(
                f"/api/v1/security/roles/{role_id}/permissions/"
            )
            role_perms = role_perms_resp.get("result", [])
            if isinstance(role_perms, str):
                role_perms = json.loads(role_perms)
            current_perm_ids = {p["id"] for p in role_perms}
        except Exception as e:
            return json.dumps({
                "error": f"Не удалось получить права роли '{role_name}': {e}"
            }, ensure_ascii=False)

        # 6. Определяем, какие datasource_access нужно добавить
        already_have = []
        to_add = []
        for ds_id, perm_id in ds_perms.items():
            ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
            if perm_id in current_perm_ids:
                already_have.append(
                    f"  ✓ {ds_name} (dataset={ds_id}, perm={perm_id})"
                )
            else:
                to_add.append({
                    "dataset_id": ds_id,
                    "dataset_name": ds_name,
                    "perm_id": perm_id,
                })

        # 7. Проверяем RLS на датасетах
        rls_warnings: list[str] = []
        try:
            rls_resp = await client.get_all(
                "/api/v1/rowlevelsecurity/", params={}
            )
            all_rls = rls_resp.get("result", [])
            if isinstance(all_rls, str):
                all_rls = json.loads(all_rls)

            for ds_id in dataset_ids:
                ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
                has_rls = any(
                    ds_id in [t.get("id", -1) for t in rls.get("tables", [])]
                    for rls in all_rls
                )
                if not has_rls:
                    rls_warnings.append(
                        f"  ⚠ {ds_name} (id:{ds_id}) — нет RLS-правил. "
                        f"Пользователи с ролью '{role_name}' увидят ВСЕ данные."
                    )
        except Exception:
            rls_warnings.append(
                "  ⚠ Не удалось проверить RLS-правила"
            )

        # 8. Формируем отчёт
        report_lines = [
            f"Дашборд: {dash_title} (ID={dashboard_id}, slug={dash_slug})",
            f"Роль: {role_name} (ID={role_id})",
            f"Датасеты дашборда: {len(dataset_ids)} шт.",
            "",
        ]

        if already_have:
            report_lines.append("Уже есть доступ:")
            report_lines.extend(already_have)
            report_lines.append("")

        if to_add:
            report_lines.append("Будет добавлено:")
            for item in to_add:
                report_lines.append(
                    f"  + {item['dataset_name']} "
                    f"(dataset={item['dataset_id']}, perm={item['perm_id']})"
                )
            report_lines.append("")
        else:
            report_lines.append(
                "Все datasource_access уже есть в роли — добавлять нечего."
            )
            report_lines.append("")

        if rls_warnings:
            report_lines.append("Предупреждения по RLS:")
            report_lines.extend(rls_warnings)
            report_lines.append("")

        if errors:
            report_lines.append("Ошибки:")
            for e in errors:
                report_lines.append(f"  ✗ {e}")
            report_lines.append("")

        # 9. Применяем или показываем dry-run
        if not to_add:
            return json.dumps({
                "result": "\n".join(report_lines),
                "status": "nothing_to_do",
            }, ensure_ascii=False)

        if not confirm_grant:
            report_lines.append(
                "Передайте confirm_grant=True для применения изменений."
            )
            return json.dumps({
                "result": "\n".join(report_lines),
                "status": "dry_run",
            }, ensure_ascii=False)

        # Применяем: текущие права + новые datasource_access
        new_perm_ids = sorted(
            current_perm_ids | {item["perm_id"] for item in to_add}
        )
        try:
            await client.post(
                f"/api/v1/security/roles/{role_id}/permissions",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )
        except Exception as e:
            return json.dumps({
                "error": f"Ошибка при обновлении прав роли: {e}",
                "report": "\n".join(report_lines),
            }, ensure_ascii=False)

        added_names = [item["dataset_name"] for item in to_add]
        report_lines.append(
            f"✓ Готово! Добавлено {len(to_add)} datasource_access "
            f"в роль '{role_name}': {', '.join(added_names)}"
        )

        return json.dumps({
            "result": "\n".join(report_lines),
            "status": "applied",
            "added_count": len(to_add),
            "total_permissions": len(new_perm_ids),
        }, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_revoke_role_access(
        dashboard_id: int,
        role_id: int,
        confirm_revoke: bool = False,
    ) -> str:
        """Отозвать у роли доступ к дашборду: убрать datasource_access
        на датасеты этого дашборда из прав роли.

        ВАЖНО: если датасет используется другими дашбордами, к которым роль
        тоже имеет доступ — отзыв сломает доступ и к тем дашбордам.
        Инструмент проверит и предупредит об этом.

        Без confirm_revoke=True покажет план действий (dry-run).

        Args:
            dashboard_id: ID дашборда (из dashboard_list).
            role_id: ID роли, у которой отзываем доступ (из role_list).
            confirm_revoke: True для применения. False — только показать план.
        """
        # 1. Проверяем дашборд
        try:
            dash_info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            dash = dash_info.get("result", {})
            dash_title = dash.get("dashboard_title", f"ID={dashboard_id}")
        except Exception as e:
            return json.dumps({
                "error": f"Дашборд ID={dashboard_id} не найден: {e}"
            }, ensure_ascii=False)

        # 2. Проверяем роль
        try:
            role_info = await client.get(f"/api/v1/security/roles/{role_id}")
            role_name = role_info.get("result", {}).get("name", f"ID={role_id}")
        except Exception as e:
            return json.dumps({
                "error": f"Роль ID={role_id} не найдена: {e}"
            }, ensure_ascii=False)

        # 3. Получаем датасеты дашборда
        try:
            ds_resp = await client.get(
                f"/api/v1/dashboard/{dashboard_id}/datasets"
            )
            datasets = ds_resp.get("result", [])
        except Exception as e:
            return json.dumps({
                "error": f"Не удалось получить датасеты дашборда: {e}"
            }, ensure_ascii=False)

        if not datasets:
            return json.dumps({
                "error": f"Дашборд '{dash_title}' не содержит датасетов."
            }, ensure_ascii=False)

        dataset_ids = {ds["id"] for ds in datasets}
        dataset_names = {
            ds["id"]: f"{ds.get('schema', '?')}.{ds.get('table_name', '?')}"
            for ds in datasets
        }

        # 4. Находим datasource_access permission_view_menu_id
        ds_perms = await _find_datasource_permissions(client, dataset_ids)
        perm_ids_to_remove = set(ds_perms.values())

        if not perm_ids_to_remove:
            return json.dumps({
                "error": "Не найдены datasource_access для датасетов дашборда."
            }, ensure_ascii=False)

        # 5. Получаем текущие права роли
        try:
            role_perms_resp = await client.get(
                f"/api/v1/security/roles/{role_id}/permissions/"
            )
            role_perms = role_perms_resp.get("result", [])
            if isinstance(role_perms, str):
                role_perms = json.loads(role_perms)
            current_perm_ids = {p["id"] for p in role_perms}
        except Exception as e:
            return json.dumps({
                "error": f"Не удалось получить права роли: {e}"
            }, ensure_ascii=False)

        # Какие реально удаляем (пересечение)
        actual_remove = perm_ids_to_remove & current_perm_ids
        if not actual_remove:
            return json.dumps({
                "result": (
                    f"Роль '{role_name}' не имеет datasource_access "
                    f"к датасетам дашборда '{dash_title}' — отзывать нечего."
                ),
                "status": "nothing_to_do",
            }, ensure_ascii=False)

        # 6. Формируем отчёт
        report_lines = [
            f"Дашборд: {dash_title} (ID={dashboard_id})",
            f"Роль: {role_name} (ID={role_id})",
            "",
            "Будет удалено:",
        ]
        for ds_id, perm_id in ds_perms.items():
            if perm_id in actual_remove:
                ds_name = dataset_names.get(ds_id, f"id:{ds_id}")
                report_lines.append(
                    f"  - {ds_name} (dataset={ds_id}, perm={perm_id})"
                )
        report_lines.append("")

        if not confirm_revoke:
            report_lines.append(
                "Передайте confirm_revoke=True для применения."
            )
            return json.dumps({
                "result": "\n".join(report_lines),
                "status": "dry_run",
            }, ensure_ascii=False)

        # 7. Применяем
        new_perm_ids = sorted(current_perm_ids - actual_remove)
        try:
            await client.post(
                f"/api/v1/security/roles/{role_id}/permissions",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )
        except Exception as e:
            return json.dumps({
                "error": f"Ошибка при обновлении прав роли: {e}",
            }, ensure_ascii=False)

        report_lines.append(
            f"✓ Готово! Удалено {len(actual_remove)} datasource_access "
            f"из роли '{role_name}'."
        )

        return json.dumps({
            "result": "\n".join(report_lines),
            "status": "applied",
            "removed_count": len(actual_remove),
        }, ensure_ascii=False)

    # === Row Level Security (RLS) ===

    @mcp.tool
    async def superset_rls_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список правил Row Level Security (ограничения строк).

        RLS добавляет WHERE-условие к запросам для определённых ролей.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска.
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/rowlevelsecurity/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/rowlevelsecurity/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_get(rls_id: int) -> str:
        """Получить детальную информацию о правиле RLS по ID.

        Args:
            rls_id: ID правила RLS (из rls_list).
        """
        result = await client.get(f"/api/v1/rowlevelsecurity/{rls_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_create(
        name: str,
        clause: str,
        tables: list[int],
        roles: list[int],
        filter_type: str = "Regular",
        group_key: str | None = None,
        description: str | None = None,
    ) -> str:
        """Создать правило Row Level Security.

        RLS автоматически добавляет WHERE-условие (clause) к запросам
        пользователей с указанными ролями к указанным датасетам.

        Args:
            name: Название правила.
            clause: SQL WHERE-условие без слова WHERE. Примеры:
                - "region = 'Москва'"
                - "user_id = {{ current_user_id() }}"
                - "status IN ('active', 'pending')"
            tables: Список ID датасетов, к которым применяется правило (из dataset_list).
            roles: Список ID ролей, для которых применяется правило (из role_list).
            filter_type: Тип фильтра:
                - "Regular" (по умолчанию) — дополнительное ограничение для указанных ролей
                - "Base" — базовый фильтр, применяется ко всем пользователям
            group_key: Ключ группировки правил (опционально).
            description: Описание правила (опционально).
        """
        # Предупреждение для Base filter_type
        if filter_type == "Base":
            return json.dumps({
                "error": (
                    "ОТКЛОНЕНО: filter_type='Base' применяется ко ВСЕМ пользователям "
                    "и может переопределить существующие Regular-правила (deny-by-default). "
                    "В архитектуре этого проекта используется только 'Regular'. "
                    "Если вы уверены — используйте superset_rls_create_unsafe "
                    "или измените filter_type на 'Regular'."
                )
            }, ensure_ascii=False)

        payload = {
            "name": name,
            "filter_type": filter_type,
            "clause": clause,
            "tables": tables,
            "roles": roles,
        }
        if group_key is not None:
            payload["group_key"] = group_key
        if description is not None:
            payload["description"] = description
        result = await client.post(
            "/api/v1/rowlevelsecurity/", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_update(
        rls_id: int,
        name: str | None = None,
        filter_type: str | None = None,
        clause: str | None = None,
        tables: list[int] | None = None,
        roles: list[int] | None = None,
        group_key: str | None = None,
        description: str | None = None,
    ) -> str:
        """Обновить правило RLS.

        КРИТИЧНО: Superset PUT API ЗАМЕНЯЕТ поля roles и tables целиком.
        Если передать только roles без tables — Superset ЗАТРЁТ tables пустым
        списком (и наоборот). Поэтому этот инструмент ТРЕБУЕТ передавать
        roles и tables одновременно, если хотя бы одно из них указано.

        Для безопасного обновления:
        1. Сначала получите текущее правило через rls_list
        2. Передайте И roles, И tables (даже если меняете только одно)

        Args:
            rls_id: ID правила RLS для обновления.
            name: Новое название.
            filter_type: Новый тип: "Regular" или "Base".
            clause: Новое SQL WHERE-условие (без слова WHERE).
            tables: Список ID датасетов (ЗАМЕНЯЕТ все текущие). ОБЯЗАТЕЛЕН если указан roles.
            roles: Список ID ролей (ЗАМЕНЯЕТ все текущие). ОБЯЗАТЕЛЕН если указан tables.
            group_key: Новый ключ группировки.
            description: Новое описание.
        """
        # Защита от потери данных: roles и tables должны передаваться вместе
        if (roles is not None) != (tables is not None):
            missing = "tables" if tables is None else "roles"
            provided = "roles" if tables is None else "tables"
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: передан только {provided} без {missing}. "
                    f"Superset PUT API ЗАМЕНЯЕТ оба поля — если не передать {missing}, "
                    f"оно будет затёрто пустым списком. "
                    f"Сначала получите текущие значения через rls_list, "
                    f"затем передайте И roles, И tables одновременно."
                )
            }, ensure_ascii=False)

        payload = {}
        if name is not None:
            payload["name"] = name
        if filter_type is not None:
            payload["filter_type"] = filter_type
        if clause is not None:
            payload["clause"] = clause
        if tables is not None:
            payload["tables"] = tables
        if roles is not None:
            payload["roles"] = roles
        if group_key is not None:
            payload["group_key"] = group_key
        if description is not None:
            payload["description"] = description
        result = await client.put(
            f"/api/v1/rowlevelsecurity/{rls_id}", json_data=payload
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_rls_delete(
        rls_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить правило RLS. Ограничения для связанных ролей будут сняты.

        КРИТИЧНО: удаление deny-by-default правила (clause='1=0') немедленно
        откроет ВСЕ данные для пользователей с этими ролями.

        Args:
            rls_id: ID правила RLS для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                rls_info = await client.get(f"/api/v1/rowlevelsecurity/{rls_id}")
                rls = rls_info.get("result", {})
                name = rls.get("name", "?")
                clause = rls.get("clause", "?")
                roles = [r.get("name", "?") for r in rls.get("roles", [])]
                tables = [t.get("table_name", "?") for t in rls.get("tables", [])]
            except Exception:
                name, clause, roles, tables = f"ID={rls_id}", "?", [], []
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление RLS-правила '{name}' "
                    f"(clause: '{clause}', роли: {roles}, датасеты: {tables}). "
                    f"Удаление изменит доступ к данным для указанных ролей. "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        result = await client.delete(f"/api/v1/rowlevelsecurity/{rls_id}")
        return json.dumps(result, ensure_ascii=False)
