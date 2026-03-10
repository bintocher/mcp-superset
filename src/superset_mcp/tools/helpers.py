"""Общие хелперы для автоматической синхронизации прав доступа.

Принцип: если дашборд имеет roles=[R1, R2], то каждая роль R1, R2
автоматически получает datasource_access ко ВСЕМ датасетам этого дашборда.
Это гарантирует: добавил пользователя в группу → он видит дашборд и данные.
"""

from typing import Any


async def find_datasource_permissions(
    client: Any,
    dataset_ids: set[int],
) -> dict[int, int]:
    """Находит permission_view_menu_id для datasource_access на указанные датасеты.

    Args:
        client: SupersetClient.
        dataset_ids: Множество ID датасетов для поиска.

    Returns:
        Словарь {dataset_id: permission_view_menu_id}.
    """
    found: dict[int, int] = {}
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
                for ds_id in dataset_ids:
                    if f"(id:{ds_id})" in view_name:
                        found[ds_id] = item["id"]
        if found.keys() >= dataset_ids:
            break
        if len(items) < 100:
            break
        page += 1
    return found


async def auto_sync_dashboard_access(
    client: Any,
    dashboard_id: int,
) -> dict[str, Any]:
    """Автоматически синхронизирует datasource_access для ролей дашборда.

    Для каждой роли, указанной в dashboard.roles:
    1. Получает все датасеты дашборда
    2. Находит datasource_access permission_view_menu_id
    3. Проверяет текущие права роли
    4. Добавляет недостающие

    Args:
        client: SupersetClient.
        dashboard_id: ID дашборда.

    Returns:
        Отчёт о синхронизации.
    """
    result = {
        "dashboard_id": dashboard_id,
        "synced_roles": [],
        "already_ok": [],
        "errors": [],
    }

    # Получаем дашборд
    try:
        db_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        db_data = db_resp.get("result", {})
    except Exception as e:
        result["errors"].append(f"Не удалось получить дашборд {dashboard_id}: {e}")
        return result

    # Роли дашборда
    db_roles = db_data.get("roles", [])
    if not db_roles:
        result["already_ok"].append("Нет ролей на дашборде — синхронизация не требуется")
        return result

    role_ids = [r["id"] for r in db_roles if isinstance(r, dict)]

    # Датасеты дашборда
    try:
        ds_resp = await client.get(f"/api/v1/dashboard/{dashboard_id}/datasets")
        datasets = ds_resp.get("result", [])
    except Exception as e:
        result["errors"].append(f"Не удалось получить датасеты: {e}")
        return result

    if not datasets:
        result["already_ok"].append("Нет датасетов — нечего синхронизировать")
        return result

    dataset_ids = {d["id"] for d in datasets if isinstance(d, dict)}
    dataset_names = {d["id"]: d.get("table_name", f"id:{d['id']}") for d in datasets}

    # Находим permission_view_menu_id для каждого датасета
    ds_perms = await find_datasource_permissions(client, dataset_ids)

    if not ds_perms:
        result["errors"].append(
            f"Не найдены datasource_access permissions для датасетов: "
            f"{[dataset_names.get(did, did) for did in dataset_ids]}"
        )
        return result

    # Для каждой роли проверяем и добавляем недостающие
    for role_id in role_ids:
        try:
            perms_resp = await client.get(f"/api/v1/security/roles/{role_id}/permissions/")
            current_perm_ids = set()
            for p in perms_resp.get("result", []):
                if isinstance(p, dict) and "id" in p:
                    current_perm_ids.add(p["id"])
                elif isinstance(p, int):
                    current_perm_ids.add(p)

            # Проверяем какие datasource_access отсутствуют
            missing = {}
            for ds_id, pvm_id in ds_perms.items():
                if pvm_id not in current_perm_ids:
                    missing[ds_id] = pvm_id

            if not missing:
                result["already_ok"].append(f"Роль {role_id}: все datasource_access уже есть")
                continue

            # Добавляем недостающие
            new_perm_ids = sorted(current_perm_ids | set(missing.values()))
            await client.put(
                f"/api/v1/security/roles/{role_id}/permissions/",
                json_data={"permission_view_menu_ids": new_perm_ids},
            )

            missing_names = [dataset_names.get(did, f"id:{did}") for did in missing]
            result["synced_roles"].append(
                {
                    "role_id": role_id,
                    "added_datasets": missing_names,
                    "total_permissions": len(new_perm_ids),
                }
            )

        except Exception as e:
            result["errors"].append(f"Ошибка роли {role_id}: {e}")

    return result


async def auto_sync_chart_dashboards(
    client: Any,
    chart_id: int | None = None,
    datasource_id: int | None = None,
) -> list[dict[str, Any]]:
    """Синхронизирует доступ для всех дашбордов, содержащих указанный чарт.

    Вызывается после chart_create/chart_update. Находит дашборды чарта
    и для каждого запускает auto_sync_dashboard_access.

    Args:
        client: SupersetClient.
        chart_id: ID чарта (если известен).
        datasource_id: ID датасета чарта (опционально, для оптимизации).

    Returns:
        Список отчётов по каждому синхронизированному дашборду.
    """
    results = []

    if not chart_id:
        return results

    # Получаем чарт и его дашборды
    try:
        chart_resp = await client.get(f"/api/v1/chart/{chart_id}")
        chart_data = chart_resp.get("result", {})
        dashboards = chart_data.get("dashboards", [])
    except Exception:
        return results

    for db in dashboards:
        db_id = db.get("id") if isinstance(db, dict) else db
        if db_id:
            sync_result = await auto_sync_dashboard_access(client, db_id)
            results.append(sync_result)

    return results
