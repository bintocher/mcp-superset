"""Инструмент аудита прав доступа — матрица пользователь × ресурсы."""

import json
import re
from typing import Any


async def _build_role_permissions_map(client: Any) -> dict[int, set[int]]:
    """Строит маппинг role_id → set(permission_view_menu_id).

    Загружает permissions для всех ролей за один проход.
    """
    role_perms: dict[int, set[int]] = {}
    # Получаем все роли
    roles_resp = await client.get_all("/api/v1/security/roles/")
    for role in roles_resp.get("result", []):
        role_id = role["id"]
        try:
            perms_resp = await client.get(
                f"/api/v1/security/roles/{role_id}/permissions/"
            )
            perm_ids = set()
            for p in perms_resp.get("result", []):
                if isinstance(p, dict) and "id" in p:
                    perm_ids.add(p["id"])
                elif isinstance(p, int):
                    perm_ids.add(p)
            role_perms[role_id] = perm_ids
        except Exception:
            role_perms[role_id] = set()
    return role_perms


async def _build_datasource_access_map(client: Any) -> dict[int, int]:
    """Строит маппинг dataset_id → permission_view_menu_id для datasource_access."""
    ds_perm: dict[int, int] = {}
    page = 0
    while page < 50:
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
                # Извлекаем dataset_id из view_name вида "[DB].[table](id:N)"
                match = re.search(r"\(id:(\d+)\)", view_name)
                if match:
                    ds_id = int(match.group(1))
                    ds_perm[ds_id] = item["id"]
        if len(items) < 100:
            break
        page += 1
    return ds_perm


def register_audit_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_permissions_audit(
        page: int = 0,
        page_size: int = 20,
        username_filter: str | None = None,
        include_admin: bool = False,
    ) -> str:
        """Аудит прав доступа: матрица пользователь × дашборды/датасеты/RLS.

        Для каждого пользователя показывает:
        - Группы, в которых он состоит
        - Эффективные роли (прямые + из групп)
        - Доступ к каждому дашборду (1/0) — на основе datasource_access
        - Доступ к каждому датасету (1/0)
        - Доступные регионы через RLS

        Args:
            page: Страница результатов (начиная с 0).
            page_size: Пользователей на странице (макс. 50).
            username_filter: Фильтр по username (подстрока).
            include_admin: Включать Admin-пользователей (у них доступ ко всему).
        """
        page_size = min(page_size, 50)

        # === 1. Собираем все данные параллельно ===

        # Пользователи
        users_resp = await client.get_all("/api/v1/security/users/")
        all_users = users_resp.get("result", [])

        # Группы (с ролями и пользователями)
        groups_resp = await client.get_all("/api/v1/security/groups/")
        all_groups_list = groups_resp.get("result", [])

        # Детали групп (list не возвращает users/roles полностью)
        groups_detail: dict[int, dict] = {}
        for g in all_groups_list:
            gid = g.get("id")
            if gid:
                try:
                    detail = await client.get(f"/api/v1/security/groups/{gid}")
                    groups_detail[gid] = detail.get("result", {})
                except Exception:
                    groups_detail[gid] = g

        # Дашборды
        dashboards_resp = await client.get_all("/api/v1/dashboard/")
        all_dashboards = dashboards_resp.get("result", [])

        # Датасеты
        datasets_resp = await client.get_all("/api/v1/dataset/")
        all_datasets = datasets_resp.get("result", [])

        # Маппинг дашборд → датасеты (через charts)
        dashboard_datasets: dict[int, set[int]] = {}
        for db in all_dashboards:
            db_id = db["id"]
            try:
                ds_resp = await client.get(
                    f"/api/v1/dashboard/{db_id}/datasets"
                )
                ds_ids = set()
                for ds in ds_resp.get("result", []):
                    if isinstance(ds, dict) and "id" in ds:
                        ds_ids.add(ds["id"])
                dashboard_datasets[db_id] = ds_ids
            except Exception:
                dashboard_datasets[db_id] = set()

        # Role → permissions
        role_perms_map = await _build_role_permissions_map(client)

        # Dataset → datasource_access permission_view_menu_id
        ds_access_map = await _build_datasource_access_map(client)

        # RLS-правила
        rls_resp = await client.get_all("/api/v1/rowlevelsecurity/")
        all_rls = rls_resp.get("result", [])

        # === 2. Построение вспомогательных структур ===

        # Группы пользователя: user_id → [{name, roles: [role_id]}]
        user_groups: dict[int, list[dict]] = {}
        # Роли из групп: user_id → set(role_id)
        user_group_roles: dict[int, set[int]] = {}
        for gid, gdata in groups_detail.items():
            g_name = gdata.get("name", "?")
            g_roles = {r["id"] for r in gdata.get("roles", [])}
            for u in gdata.get("users", []):
                uid = u["id"]
                if uid not in user_groups:
                    user_groups[uid] = []
                    user_group_roles[uid] = set()
                user_groups[uid].append({
                    "name": g_name,
                    "roles": sorted(g_roles),
                })
                user_group_roles[uid] |= g_roles

        # RLS: role_id → список регионов
        role_rls_regions: dict[int, list[str]] = {}
        for rule in all_rls:
            clause = rule.get("clause", "")
            roles = rule.get("roles", [])
            # Извлекаем регион из clause типа "operation_region = 'Московская'"
            region_match = re.search(
                r"operation_region\s*=\s*'([^']+)'", clause
            )
            if clause == "1=1":
                region = "_all_"
            elif region_match:
                region = region_match.group(1)
            elif clause == "1=0":
                region = "_deny_"
            else:
                continue
            for r in roles:
                rid = r["id"]
                if rid not in role_rls_regions:
                    role_rls_regions[rid] = []
                role_rls_regions[rid].append(region)

        # Имена ролей
        roles_resp_all = await client.get_all("/api/v1/security/roles/")
        role_names: dict[int, str] = {
            r["id"]: r["name"] for r in roles_resp_all.get("result", [])
        }

        # Названия дашбордов и датасетов
        dashboard_info = {
            d["id"]: d.get("dashboard_title", d.get("slug", f"id:{d['id']}"))
            for d in all_dashboards
        }
        dataset_info = {
            d["id"]: d.get("table_name", f"id:{d['id']}")
            for d in all_datasets
        }

        # === 3. Фильтрация пользователей ===

        filtered_users = all_users
        if not include_admin:
            filtered_users = [
                u for u in filtered_users
                if not any(
                    r.get("name") == "Admin" for r in u.get("roles", [])
                )
            ]
        if username_filter:
            filtered_users = [
                u for u in filtered_users
                if username_filter.lower() in u.get("username", "").lower()
            ]

        total = len(filtered_users)
        start = page * page_size
        end = start + page_size
        page_users = filtered_users[start:end]

        # === 4. Матрица доступа ===

        audit_rows = []
        for user in page_users:
            uid = user["id"]
            uname = user.get("username", "?")

            # Эффективные роли = прямые + из групп
            direct_role_ids = {r["id"] for r in user.get("roles", [])}
            group_role_ids = user_group_roles.get(uid, set())
            effective_role_ids = direct_role_ids | group_role_ids

            # Собираем все permission_view_menu_ids пользователя
            user_perm_ids: set[int] = set()
            for rid in effective_role_ids:
                user_perm_ids |= role_perms_map.get(rid, set())

            # Доступ к датасетам
            datasets_access: dict[str, int] = {}
            for ds in all_datasets:
                ds_id = ds["id"]
                ds_name = dataset_info[ds_id]
                pvm_id = ds_access_map.get(ds_id)
                if pvm_id and pvm_id in user_perm_ids:
                    datasets_access[ds_name] = 1
                else:
                    datasets_access[ds_name] = 0

            # Доступ к дашбордам (нужен datasource_access ко ВСЕМ датасетам)
            dashboards_access: dict[str, int] = {}
            for db in all_dashboards:
                db_id = db["id"]
                db_name = dashboard_info[db_id]
                required_ds = dashboard_datasets.get(db_id, set())
                if not required_ds:
                    # Нет датасетов — доступен всем
                    dashboards_access[db_name] = 1
                else:
                    has_all = all(
                        ds_access_map.get(ds_id) in user_perm_ids
                        for ds_id in required_ds
                        if ds_access_map.get(ds_id) is not None
                    )
                    dashboards_access[db_name] = 1 if has_all else 0

            # RLS-регионы
            rls_regions: list[str] = []
            has_deny = False
            for rid in effective_role_ids:
                regions = role_rls_regions.get(rid, [])
                for region in regions:
                    if region == "_all_":
                        rls_regions = ["ВСЕ РЕГИОНЫ"]
                        break
                    elif region == "_deny_":
                        has_deny = True
                    elif region not in rls_regions:
                        rls_regions.append(region)
                if rls_regions == ["ВСЕ РЕГИОНЫ"]:
                    break

            if not rls_regions and has_deny:
                rls_regions = ["ЗАПРЕЩЕНО (1=0)"]
            elif not rls_regions:
                rls_regions = ["нет RLS"]

            # Группы пользователя
            groups_names = [
                g["name"] for g in user_groups.get(uid, [])
            ]

            audit_rows.append({
                "user_id": uid,
                "username": uname,
                "active": user.get("active", True),
                "groups": groups_names,
                "direct_roles": sorted(
                    role_names.get(rid, f"id:{rid}")
                    for rid in direct_role_ids
                ),
                "group_roles": sorted(
                    role_names.get(rid, f"id:{rid}")
                    for rid in group_role_ids
                ),
                "dashboards": dashboards_access,
                "datasets": datasets_access,
                "rls_regions": sorted(rls_regions),
            })

        result = {
            "page": page,
            "page_size": page_size,
            "total_users": total,
            "total_pages": (total + page_size - 1) // page_size,
            "dashboards_checked": list(dashboard_info.values()),
            "datasets_checked": list(dataset_info.values()),
            "users": audit_rows,
        }

        return json.dumps(result, ensure_ascii=False)
