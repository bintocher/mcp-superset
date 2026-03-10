"""Инструменты для управления дашбордами Superset."""

import base64
import json
import uuid


KPI_VIZ_TYPES = {"big_number_total", "big_number"}
MIN_KPI_HEIGHT = 16  # 2 grid cells (1 cell = 8 units)

# Типы фильтров, для которых нужен granularity_sqla на чартах
_TIME_FILTER_TYPES = {"filter_time", "filter_timecolumn", "filter_timegrain"}


async def _ensure_datasets_filter_ready(client, dashboard_id: int) -> list[dict]:
    """Устанавливает always_filter_main_dttm=True на всех датасетах дашборда.

    Вызывается автоматически при создании/копировании дашборда и добавлении фильтров.

    Returns:
        list of {id, name, action} для обновлённых датасетов.
    """
    updated = []
    try:
        datasets_resp = await client.get(
            f"/api/v1/dashboard/{dashboard_id}/datasets"
        )
        datasets = datasets_resp.get("result", [])
    except Exception:
        return updated

    for ds in datasets:
        ds_id = ds.get("id")
        if not ds_id:
            continue
        try:
            ds_detail = await client.get(f"/api/v1/dataset/{ds_id}")
            ds_data = ds_detail.get("result", {})
            if not ds_data.get("always_filter_main_dttm"):
                await client.put(
                    f"/api/v1/dataset/{ds_id}",
                    json_data={"always_filter_main_dttm": True},
                )
                updated.append({
                    "id": ds_id,
                    "name": ds_data.get("table_name", "?"),
                    "action": "always_filter_main_dttm = True",
                })
        except Exception:
            pass
    return updated


async def _auto_fix_charts_for_filter(
    client,
    dashboard_id: int,
    filter_column: str,
    filter_type: str,
) -> dict:
    """Автоматически настраивает ВСЕ чарты дашборда для работы с фильтром.

    Для ЛЮБОГО типа фильтра:
    1. Устанавливает granularity_sqla на чартах без него (для работы time range).
       - Для time-фильтров: берёт колонку фильтра.
       - Для прочих (select, range): берёт main_dttm_col из датасета чарта.
    2. Проверяет что колонка фильтра существует в датасете каждого чарта.
       Если нет — добавляет предупреждение (фильтр не повлияет на этот чарт).

    Returns:
        dict: charts_updated, charts_already_ok, column_warnings, warnings.
    """
    result = {
        "charts_updated": [],
        "charts_already_ok": [],
        "column_warnings": [],
        "warnings": [],
    }

    is_time_filter = filter_type in _TIME_FILTER_TYPES

    try:
        charts_resp = await client.get(
            f"/api/v1/dashboard/{dashboard_id}/charts"
        )
        charts = charts_resp.get("result", [])
    except Exception:
        return result

    # Кеш датасетов: ds_id -> {main_dttm_col, column_names}
    ds_cache: dict[int, dict] = {}

    async def _get_dataset_info(ds_id: int) -> dict:
        if ds_id in ds_cache:
            return ds_cache[ds_id]
        try:
            ds_resp = await client.get(f"/api/v1/dataset/{ds_id}")
            ds_data = ds_resp.get("result", {})
            columns = ds_data.get("columns", [])
            col_names = {c.get("column_name") for c in columns if c.get("column_name")}
            info = {
                "main_dttm_col": ds_data.get("main_dttm_col"),
                "column_names": col_names,
                "table_name": ds_data.get("table_name", "?"),
            }
        except Exception:
            info = {"main_dttm_col": None, "column_names": set(), "table_name": "?"}
        ds_cache[ds_id] = info
        return info

    for chart_info in charts:
        chart_id = chart_info.get("id")
        if not chart_id:
            continue
        try:
            chart_resp = await client.get(f"/api/v1/chart/{chart_id}")
            chart = chart_resp.get("result", {})
        except Exception:
            result["warnings"].append(f"chart {chart_id}: не удалось получить")
            continue

        chart_name = chart.get("slice_name", "?")
        ds_id = chart.get("datasource_id")

        # --- Проверка колонки фильтра в датасете чарта ---
        if ds_id and not is_time_filter:
            ds_info = await _get_dataset_info(ds_id)
            if filter_column not in ds_info["column_names"]:
                result["column_warnings"].append({
                    "chart_id": chart_id,
                    "chart_name": chart_name,
                    "dataset_id": ds_id,
                    "dataset_name": ds_info["table_name"],
                    "missing_column": filter_column,
                    "message": (
                        f"Фильтр по '{filter_column}' НЕ повлияет на чарт "
                        f"'{chart_name}' (ID={chart_id}): колонка отсутствует "
                        f"в датасете '{ds_info['table_name']}' (ID={ds_id})"
                    ),
                })

        # --- granularity_sqla ---
        params_str = chart.get("params", "{}")
        try:
            params = (
                json.loads(params_str)
                if isinstance(params_str, str)
                else (params_str or {})
            )
        except json.JSONDecodeError:
            params = {}

        current = params.get("granularity_sqla")
        if current:
            result["charts_already_ok"].append({
                "id": chart_id,
                "name": chart_name,
                "granularity_sqla": current,
            })
            continue

        # Определяем колонку для granularity_sqla
        if is_time_filter:
            sqla_col = filter_column
        else:
            # Для non-time фильтров: берём main_dttm_col из датасета
            ds_info = await _get_dataset_info(ds_id) if ds_id else {}
            sqla_col = ds_info.get("main_dttm_col")
            if not sqla_col:
                result["warnings"].append(
                    f"chart {chart_id} ({chart_name}): нет granularity_sqla "
                    f"и main_dttm_col не задан в датасете — time range "
                    f"фильтр не будет работать для этого чарта"
                )
                continue

        params["granularity_sqla"] = sqla_col
        try:
            await client.put(
                f"/api/v1/chart/{chart_id}",
                json_data={
                    "params": json.dumps(params, ensure_ascii=False),
                },
            )
            result["charts_updated"].append({
                "id": chart_id,
                "name": chart_name,
                "set": f"granularity_sqla = '{sqla_col}'",
            })
        except Exception as e:
            result["warnings"].append(
                f"chart {chart_id} ({chart_name}): "
                f"ошибка обновления granularity_sqla: {e}"
            )

    return result


def register_dashboard_tools(mcp):
    from superset_mcp.server import superset_client as client
    from superset_mcp.tools.helpers import auto_sync_dashboard_access

    async def _validate_kpi_height(position: dict) -> str | None:
        """Проверяет что KPI-чарты (big_number_total/big_number) имеют высоту >= 2 клеток.

        Возвращает сообщение об ошибке или None если всё OK.
        """
        small_charts = {}  # chartId -> height
        for v in position.values():
            if not isinstance(v, dict) or v.get("type") != "CHART":
                continue
            meta = v.get("meta", {})
            chart_id = meta.get("chartId")
            height = meta.get("height", 0)
            if chart_id and height < MIN_KPI_HEIGHT:
                small_charts[chart_id] = height

        if not small_charts:
            return None

        kpi_violations = []
        for cid, height in small_charts.items():
            try:
                chart = await client.get(f"/api/v1/chart/{cid}")
                vt = chart.get("result", {}).get("viz_type", "")
                if vt in KPI_VIZ_TYPES:
                    kpi_violations.append((cid, height, vt))
            except Exception:
                pass

        if kpi_violations:
            details = ", ".join(
                f"chart_id={cid} (viz_type={vt}, height={h}, минимум={MIN_KPI_HEIGHT})"
                for cid, h, vt in kpi_violations
            )
            return (
                f"ОТКЛОНЕНО: KPI-чарты (big_number_total/big_number) требуют минимум "
                f"2 клетки высоты (height >= {MIN_KPI_HEIGHT}) в position_json. "
                f"Нарушения: {details}. "
                f"Исправьте height на {MIN_KPI_HEIGHT} или больше."
            )
        return None

    @mcp.tool
    async def superset_dashboard_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список дашбордов Superset с пагинацией.

        ВАЖНО: всегда вызывайте этот инструмент перед dashboard_get,
        чтобы узнать актуальные ID дашбордов.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:dashboard_title,opr:ct,value:поиск)))
                - По владельцу: (filters:!((col:owners,opr:rel_m_m,value:1)))
                - Только опубликованные: (filters:!((col:published,opr:eq,value:!t)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/dashboard/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/dashboard/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_get(dashboard_id: int) -> str:
        """Получить детальную информацию о дашборде по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_dashboard_list,
        чтобы найти нужный дашборд. Несуществующий ID вернёт 404.

        Args:
            dashboard_id: ID дашборда (целое число из результата dashboard_list).
        """
        result = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_create(
        dashboard_title: str,
        slug: str | None = None,
        published: bool = False,
        json_metadata: str | None = None,
        css: str | None = None,
        position_json: str | None = None,
        roles: list[int] | None = None,
    ) -> str:
        """Создать новый дашборд.

        ВАЖНО: при указании roles автоматически синхронизируются datasource_access
        для указанных ролей — каждая роль получит доступ ко всем датасетам дашборда.

        Args:
            dashboard_title: Название дашборда (отображается в UI).
            slug: URL-slug для красивой ссылки (напр. "my-dashboard"). Должен быть уникальным.
            published: Опубликовать сразу (по умолчанию False — черновик).
            json_metadata: JSON-строка с метаданными дашборда. Содержит настройки фильтров,
                цветовой палитры, refresh-интервала. Для пустых метаданных используйте "{}".
            css: Пользовательский CSS для стилизации дашборда.
            position_json: JSON-строка с позиционированием виджетов на дашборде.
                Определяет расположение графиков, заголовков, разделителей в сетке.
            roles: Список ID ролей, которым доступен дашборд. Пользователи без
                одной из этих ролей НЕ увидят дашборд. Пустой список = доступен всем.
        """
        # Валидация высоты KPI-чартов в position_json
        if position_json is not None:
            pos = json.loads(position_json) if isinstance(position_json, str) else position_json
            kpi_error = await _validate_kpi_height(pos)
            if kpi_error:
                return json.dumps({"error": kpi_error}, ensure_ascii=False)

        payload = {"dashboard_title": dashboard_title}
        if slug is not None:
            payload["slug"] = slug
        if published:
            payload["published"] = published
        if json_metadata is not None:
            payload["json_metadata"] = json_metadata
        if css is not None:
            payload["css"] = css
        if position_json is not None:
            payload["position_json"] = position_json
        if roles is not None:
            payload["roles"] = roles
        result = await client.post("/api/v1/dashboard/", json_data=payload)

        # Автоматика: если дашборд создан с чартами — включить
        # always_filter_main_dttm на всех датасетах
        new_id = result.get("id")
        datasets_auto = []
        if new_id and position_json:
            datasets_auto = await _ensure_datasets_filter_ready(client, new_id)

        if datasets_auto:
            result["_auto_datasets_updated"] = datasets_auto

        # Автоматика: синхронизировать datasource_access для ролей дашборда
        if new_id:
            sync = await auto_sync_dashboard_access(client, new_id)
            if sync.get("synced_roles"):
                result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_update(
        dashboard_id: int,
        dashboard_title: str | None = None,
        slug: str | None = None,
        published: bool | None = None,
        json_metadata: str | dict | None = None,
        css: str | None = None,
        position_json: str | dict | None = None,
        owners: list[int] | None = None,
        roles: list[int] | None = None,
    ) -> str:
        """Обновить существующий дашборд. Передавайте только изменяемые поля.

        ВАЖНО: после обновления автоматически синхронизируются datasource_access —
        каждая роль из dashboard.roles получит доступ ко всем датасетам дашборда.

        Args:
            dashboard_id: ID дашборда для обновления.
            dashboard_title: Новое название.
            slug: Новый URL-slug (должен быть уникальным).
            published: Изменить статус публикации (true — опубликован, false — черновик).
            json_metadata: JSON-метаданные дашборда (строка или объект, перезаписывают полностью).
            css: Новый пользовательский CSS для дашборда.
                Инъектируется как <style> тег на странице дашборда.
                НЕ влияет на Explore view (редактор чарта) — только на дашборд.

                Типовые CSS-фиксы:

                  1) KPI big_number_total — размер цифр и скролл:
                  Контейнер KPI имеет фиксированную высоту (~60px при 2 клетках).
                  По умолчанию шрифт мелкий. Для увеличения через CSS:
                    div[class*="big_number"] .header-line {
                      font-size: 3.3rem !important;  /* цифры */
                      font-weight: 700 !important;
                      line-height: 1.1 !important;
                      margin-bottom: 0 !important;  /* ОБЯЗАТЕЛЬНО! иначе скролл */
                    }
                    div[class*="big_number"] .subheader-line {
                      font-size: 1rem !important;  /* надпись */
                      font-weight: 400 !important;
                      opacity: 0.7;
                    }
                  ВАЖНО: margin-bottom у .header-line по умолчанию 8px — вместе с
                  line-height вызывает overflow и скролл. Формула проверки:
                  font_size_px * 1.1 + margin_bottom <= 60px.
                  3.3rem = 52.8px → 52.8 * 1.1 = 58px + 0 = 58px < 60px ✓

                  2) Country Map tooltip обрезается контейнером — виновник
                  DIV.dashboard-chart (styled-component с overflow:hidden).
                  Tooltip = DIV.hover-popup (НЕ .datamaps-hoverover!). Фикс:
                    .dashboard-chart-id-{N} .dashboard-chart {
                      overflow: visible !important;
                    }
                    .hover-popup { z-index: 99999 !important; }

                  Для анализа CSS-проблем: открыть дашборд в Playwright,
                  найти элемент чарта, пройти вверх по parentElement,
                  проверить getComputedStyle(el).overflow на каждом уровне.

            position_json: Позиционирование виджетов на дашборде (строка или объект).
                Определяет расположение графиков, заголовков, разделителей в сетке.
                ВАЖНО: перезаписывает полностью — сначала получите текущий layout
                через dashboard_get, измените нужные элементы и передайте весь JSON.
            owners: Список ID пользователей-владельцев (ЗАМЕНЯЕТ всех текущих владельцев).
            roles: Список ID ролей для доступа к дашборду (ЗАМЕНЯЕТ текущие).
                При изменении автоматически синхронизируются datasource_access.
        """
        # Валидация высоты KPI-чартов в position_json
        if position_json is not None:
            pos = json.loads(position_json) if isinstance(position_json, str) else position_json
            kpi_error = await _validate_kpi_height(pos)
            if kpi_error:
                return json.dumps({"error": kpi_error}, ensure_ascii=False)

        payload = {}
        if dashboard_title is not None:
            payload["dashboard_title"] = dashboard_title
        if slug is not None:
            payload["slug"] = slug
        if published is not None:
            payload["published"] = published
        if json_metadata is not None:
            payload["json_metadata"] = (
                json.dumps(json_metadata, ensure_ascii=False)
                if isinstance(json_metadata, dict)
                else json_metadata
            )
        if css is not None:
            payload["css"] = css
        if position_json is not None:
            payload["position_json"] = (
                json.dumps(position_json, ensure_ascii=False)
                if isinstance(position_json, dict)
                else position_json
            )
        if owners is not None:
            payload["owners"] = owners
        if roles is not None:
            payload["roles"] = roles
        result = await client.put(
            f"/api/v1/dashboard/{dashboard_id}", json_data=payload
        )

        # Автоматика: синхронизировать datasource_access для ролей дашборда
        sync = await auto_sync_dashboard_access(client, dashboard_id)
        if sync.get("synced_roles"):
            result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_publish(dashboard_id: int) -> str:
        """Опубликовать дашборд (сделать видимым для пользователей с правами).

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.put(
            f"/api/v1/dashboard/{dashboard_id}", json_data={"published": True}
        )
        return json.dumps({"status": "ok", "dashboard_id": dashboard_id, "published": True}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_unpublish(dashboard_id: int) -> str:
        """Снять дашборд с публикации (перевести в черновик).

        Дашборд останется доступен владельцам и админам, но скроется из общего списка.

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.put(
            f"/api/v1/dashboard/{dashboard_id}", json_data={"published": False}
        )
        return json.dumps({"status": "ok", "dashboard_id": dashboard_id, "published": False}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_delete(
        dashboard_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить дашборд по ID. Графики и датасеты НЕ удаляются — только сам дашборд.

        КРИТИЧНО: дашборд будет удалён безвозвратно.

        Args:
            dashboard_id: ID дашборда для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                info = await client.get(f"/api/v1/dashboard/{dashboard_id}")
                r = info.get("result", {})
                title = r.get("dashboard_title", "?")
                slug = r.get("slug", "")
                published = r.get("published", False)
                charts = await client.get(
                    f"/api/v1/dashboard/{dashboard_id}/charts"
                )
                charts_count = len(charts.get("result", []))
            except Exception:
                title = f"ID={dashboard_id}"
                slug = ""
                published = "?"
                charts_count = "?"
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление дашборда '{title}'"
                    f"{f' (slug={slug})' if slug else ''} "
                    f"(ID={dashboard_id}, published={published}, "
                    f"чартов={charts_count}). "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        result = await client.delete(f"/api/v1/dashboard/{dashboard_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_copy(
        dashboard_id: int,
        dashboard_title: str,
        json_metadata: str | None = None,
    ) -> str:
        """Создать копию существующего дашборда со всеми графиками.

        Args:
            dashboard_id: ID исходного дашборда для копирования.
            dashboard_title: Название новой копии.
            json_metadata: JSON-метаданные для копии.
                ВАЖНО: Superset требует это поле. Если не указано, будет передано "{}".
        """
        payload = {
            "dashboard_title": dashboard_title,
            "json_metadata": json_metadata or "{}",
        }
        result = await client.post(
            f"/api/v1/dashboard/{dashboard_id}/copy/",
            json_data=payload,
        )

        # Автоматика: включить always_filter_main_dttm на всех датасетах копии
        new_id = result.get("id")
        datasets_auto = []
        if new_id:
            datasets_auto = await _ensure_datasets_filter_ready(client, new_id)
        if datasets_auto:
            result["_auto_datasets_updated"] = datasets_auto

        # Автоматика: синхронизировать datasource_access для ролей копии
        if new_id:
            sync = await auto_sync_dashboard_access(client, new_id)
            if sync.get("synced_roles"):
                result["_auto_access_synced"] = sync["synced_roles"]

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_charts(dashboard_id: int) -> str:
        """Получить список всех графиков (charts), размещённых на дашборде.

        Возвращает ID и названия графиков. Полезно для анализа содержимого дашборда.

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.get(
            f"/api/v1/dashboard/{dashboard_id}/charts"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_datasets(dashboard_id: int) -> str:
        """Получить список всех датасетов, используемых графиками дашборда.

        Полезно для понимания зависимостей дашборда от источников данных.

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.get(
            f"/api/v1/dashboard/{dashboard_id}/datasets"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_export(
        dashboard_ids: str,
    ) -> str:
        """Экспортировать дашборды со всеми зависимостями (графики, датасеты, БД) в ZIP.

        Результат — base64-кодированный ZIP-файл. Можно импортировать обратно
        через superset_dashboard_import.

        Args:
            dashboard_ids: ID дашбордов через запятую (напр. "1,2,3").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        params = {"q": f"[{dashboard_ids}]"}
        raw = await client.get_raw("/api/v1/dashboard/export/", params=params)
        return json.dumps({
            "format": "zip",
            "encoding": "base64",
            "data": base64.b64encode(raw).decode(),
            "size_bytes": len(raw),
        }, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_import(
        file_path: str,
        overwrite: bool = False,
    ) -> str:
        """Импортировать дашборды из ZIP-файла (созданного через export).

        ZIP должен содержать YAML-файлы с конфигурацией дашбордов и зависимостей.

        Args:
            file_path: Абсолютный путь к ZIP-файлу на диске.
            overwrite: Перезаписать существующие объекты с такими же UUID (по умолчанию False).
        """
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/dashboard/import/", files=files, data=data,
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_get(dashboard_id: int) -> str:
        """Получить настройки встраивания (embedded) дашборда.

        ВАЖНО: вернёт 404, если embedded mode не был настроен через embedded_set.

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.get(
            f"/api/v1/dashboard/{dashboard_id}/embedded"
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_set(
        dashboard_id: int,
        allowed_domains: list[str] | None = None,
    ) -> str:
        """Включить встраивание дашборда (embedded mode) и настроить разрешённые домены.

        После включения дашборд можно встраивать через iframe на указанных доменах.

        Args:
            dashboard_id: ID дашборда.
            allowed_domains: Список доменов, на которых разрешено встраивание
                (напр. ["example.com", "app.example.com"]). Пустой список = все домены.
        """
        payload = {}
        if allowed_domains is not None:
            payload["allowed_domains"] = allowed_domains
        result = await client.post(
            f"/api/v1/dashboard/{dashboard_id}/embedded",
            json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_embedded_delete(dashboard_id: int) -> str:
        """Отключить встраивание (embedded mode) дашборда.

        После отключения дашборд больше нельзя встраивать через iframe.

        Args:
            dashboard_id: ID дашборда.
        """
        result = await client.delete(
            f"/api/v1/dashboard/{dashboard_id}/embedded"
        )
        return json.dumps(result, ensure_ascii=False)

    # --- Инструменты для native-фильтров дашборда ---

    def _extract_chart_ids(position: dict) -> list[int]:
        """Извлекает ID чартов из position_json дашборда."""
        return [
            v["meta"]["chartId"]
            for v in position.values()
            if isinstance(v, dict) and v.get("type") == "CHART"
        ]

    @mcp.tool
    async def superset_dashboard_filter_list(dashboard_id: int) -> str:
        """Получить список native-фильтров дашборда в читаемом формате.

        Парсит json_metadata и возвращает конфигурацию каждого фильтра:
        ID, название, тип, колонку, датасет, chartsInScope, controlValues.

        Args:
            dashboard_id: ID дашборда.
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata", "{}"))
        filters = metadata.get("native_filter_configuration", [])
        summary = []
        for f in filters:
            targets = f.get("targets", [])
            column = None
            dataset_id = None
            if targets:
                column = targets[0].get("column", {}).get("name")
                dataset_id = targets[0].get("datasetId")
            summary.append({
                "id": f.get("id"),
                "name": f.get("name"),
                "filterType": f.get("filterType"),
                "column": column,
                "datasetId": dataset_id,
                "chartsInScope": f.get("chartsInScope", []),
                "cascadeParentIds": f.get("cascadeParentIds", []),
                "controlValues": f.get("controlValues", {}),
            })
        return json.dumps(summary, ensure_ascii=False, indent=2)

    @mcp.tool
    async def superset_dashboard_filter_add(
        dashboard_id: int,
        name: str,
        column: str,
        dataset_id: int,
        filter_type: str = "filter_select",
        multi_select: bool = True,
        search_all_options: bool = False,
        enable_empty_filter: bool = False,
        cascade_parent_id: str | None = None,
    ) -> str:
        """Добавить native-фильтр на дашборд с правильными defaults.

        Автоматически заполняет chartsInScope всеми чартами дашборда,
        формирует корректные scope, defaultDataMask, cascadeParentIds.
        ID фильтра генерируется в формате NATIVE_FILTER-<uuid> — это ОБЯЗАТЕЛЬНО
        для Superset 6.0.1 (кастомные ID фронтенд молча игнорирует).

        Args:
            dashboard_id: ID дашборда.
            name: Отображаемое название фильтра (напр. "ФИО").
            column: Имя колонки датасета для фильтрации (напр. "full_name").
            dataset_id: ID датасета, из которого берутся значения фильтра.
            filter_type: Тип фильтра: "filter_select", "filter_time", "filter_range".
            multi_select: Множественный выбор (по умолчанию True).
            search_all_options: Поиск по всем значениям, не только загруженным (для больших списков).
            enable_empty_filter: Пустой фильтр = фильтрация по NULL.
            cascade_parent_id: ID родительского фильтра для каскадной связи.
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata", "{}"))
        position = json.loads(result.get("position_json", "{}"))

        chart_ids = _extract_chart_ids(position)
        filter_id = f"NATIVE_FILTER-{uuid.uuid4()}"

        new_filter = {
            "id": filter_id,
            "name": name,
            "filterType": filter_type,
            "type": "NATIVE_FILTER",
            "targets": [{"datasetId": dataset_id, "column": {"name": column}}],
            "controlValues": {
                "enableEmptyFilter": enable_empty_filter,
                "multiSelect": multi_select,
                "searchAllOptions": search_all_options,
                "inverseSelection": False,
                "defaultToFirstItem": False,
            },
            "defaultDataMask": {
                "extraFormData": {},
                "filterState": {},
                "ownState": {},
            },
            "cascadeParentIds": [cascade_parent_id] if cascade_parent_id else [],
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "chartsInScope": chart_ids,
            "tabsInScope": [],
        }

        filters = metadata.get("native_filter_configuration", [])
        filters.append(new_filter)
        metadata["native_filter_configuration"] = filters
        metadata["show_native_filters"] = True

        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={
            "json_metadata": json.dumps(metadata, ensure_ascii=False),
        })

        # === Автоматика: настроить датасеты и чарты для работы фильтра ===
        response = {
            "status": "ok",
            "filter_id": filter_id,
            "chartsInScope": chart_ids,
        }

        # 1. always_filter_main_dttm на всех датасетах
        datasets_auto = await _ensure_datasets_filter_ready(
            client, dashboard_id
        )
        if datasets_auto:
            response["_auto_datasets_updated"] = datasets_auto

        # 2. granularity_sqla на чартах + проверка совместимости колонок
        charts_auto = await _auto_fix_charts_for_filter(
            client, dashboard_id, column, filter_type
        )
        if charts_auto["charts_updated"]:
            response["_auto_charts_updated"] = charts_auto["charts_updated"]
        if charts_auto["column_warnings"]:
            response["_auto_column_warnings"] = charts_auto["column_warnings"]
        if charts_auto["warnings"]:
            response["_auto_warnings"] = charts_auto["warnings"]

        return json.dumps(response, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_filter_update(
        dashboard_id: int,
        filter_id: str,
        name: str | None = None,
        column: str | None = None,
        multi_select: bool | None = None,
        search_all_options: bool | None = None,
        enable_empty_filter: bool | None = None,
        cascade_parent_id: str | None = None,
    ) -> str:
        """Обновить native-фильтр дашборда по ID. Передавайте только изменяемые поля.

        Args:
            dashboard_id: ID дашборда.
            filter_id: ID фильтра (формат "NATIVE_FILTER-<uuid>", напр. "NATIVE_FILTER-a2b79191-9728-40b5-b5ba-fe329a674bf9").
            name: Новое название фильтра.
            column: Новая колонка для фильтрации.
            multi_select: Множественный выбор.
            search_all_options: Поиск по всем значениям.
            enable_empty_filter: Пустой фильтр = NULL.
            cascade_parent_id: ID родительского фильтра (None — убрать каскад).
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata", "{}"))
        filters = metadata.get("native_filter_configuration", [])

        target = None
        for f in filters:
            if f.get("id") == filter_id:
                target = f
                break

        if not target:
            return json.dumps(
                {"status": "error", "message": f"Фильтр {filter_id} не найден"},
                ensure_ascii=False,
            )

        if name is not None:
            target["name"] = name
        if column is not None and target.get("targets"):
            target["targets"][0]["column"]["name"] = column
        cv = target.get("controlValues", {})
        if multi_select is not None:
            cv["multiSelect"] = multi_select
        if search_all_options is not None:
            cv["searchAllOptions"] = search_all_options
        if enable_empty_filter is not None:
            cv["enableEmptyFilter"] = enable_empty_filter
        target["controlValues"] = cv
        if cascade_parent_id is not None:
            target["cascadeParentIds"] = [cascade_parent_id] if cascade_parent_id else []

        metadata["native_filter_configuration"] = filters
        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={
            "json_metadata": json.dumps(metadata, ensure_ascii=False),
        })
        return json.dumps({"status": "ok", "filter_id": filter_id}, ensure_ascii=False)

    @mcp.tool
    async def superset_dashboard_filter_delete(
        dashboard_id: int,
        filter_id: str,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить native-фильтр с дашборда по ID.

        Args:
            dashboard_id: ID дашборда.
            filter_id: ID фильтра для удаления (формат "NATIVE_FILTER-<uuid>").
            confirm_delete: Подтверждение удаления фильтра (ОБЯЗАТЕЛЬНО).
        """
        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata", "{}"))
        filters = metadata.get("native_filter_configuration", [])

        target = None
        for f in filters:
            if f.get("id") == filter_id:
                target = f
                break

        if not target:
            return json.dumps(
                {"status": "error", "message": f"Фильтр {filter_id} не найден"},
                ensure_ascii=False,
            )

        if not confirm_delete:
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: удаление фильтра '{target.get('name', '?')}' "
                    f"(ID={filter_id}) с дашборда {dashboard_id}. "
                    f"Всего фильтров на дашборде: {len(filters)}. "
                    f"Передайте confirm_delete=True для подтверждения."
                )
            }, ensure_ascii=False)

        new_filters = [f for f in filters if f.get("id") != filter_id]
        metadata["native_filter_configuration"] = new_filters
        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={
            "json_metadata": json.dumps(metadata, ensure_ascii=False),
        })
        return json.dumps(
            {"status": "ok", "deleted": filter_id, "remaining": len(new_filters)},
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_dashboard_filter_reset(
        dashboard_id: int,
        dataset_id: int,
        filters_json: str,
        confirm_reset: bool = False,
    ) -> str:
        """Пересоздать ВСЕ native-фильтры дашборда с правильными defaults.

        Удаляет все текущие фильтры и создаёт новые по списку.
        Автоматически заполняет chartsInScope, scope, defaultDataMask, cascadeParentIds.

        КРИТИЧНО: все текущие фильтры будут УДАЛЕНЫ и заменены новыми.

        Args:
            dashboard_id: ID дашборда.
            dataset_id: ID датасета для всех фильтров.
            filters_json: JSON-массив описаний фильтров. Каждый элемент:
            confirm_reset: Подтверждение сброса фильтров (ОБЯЗАТЕЛЬНО).
                {
                    "name": "ФИО",
                    "column": "full_name",
                    "type": "filter_select",       // filter_select | filter_time | filter_range
                    "multi_select": true,           // необязательно, default true
                    "search_all_options": false,     // необязательно, default false
                    "enable_empty_filter": false,    // необязательно, default false
                    "cascade_parent_id": null        // необязательно, ID родительского фильтра
                }
        """
        if not confirm_reset:
            # Показываем текущие фильтры для информированного решения
            dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
            result = dashboard.get("result", {})
            metadata = json.loads(result.get("json_metadata", "{}"))
            current_filters = metadata.get("native_filter_configuration", [])
            current_names = [f.get("name", "?") for f in current_filters]
            return json.dumps({
                "error": (
                    f"ОТКЛОНЕНО: filter_reset удалит {len(current_filters)} "
                    f"текущих фильтров: {current_names} и заменит новыми. "
                    f"Передайте confirm_reset=True для подтверждения."
                )
            }, ensure_ascii=False)

        dashboard = await client.get(f"/api/v1/dashboard/{dashboard_id}")
        result = dashboard.get("result", {})
        metadata = json.loads(result.get("json_metadata", "{}"))
        position = json.loads(result.get("position_json", "{}"))

        chart_ids = _extract_chart_ids(position)
        filter_defs = json.loads(filters_json)

        new_filters = []
        for fd in filter_defs:
            filter_id = f"NATIVE_FILTER-{uuid.uuid4()}"
            filter_type = fd.get("type", "filter_select")

            f = {
                "id": filter_id,
                "name": fd["name"],
                "filterType": filter_type,
                "type": "NATIVE_FILTER",
                "targets": [{"datasetId": dataset_id, "column": {"name": fd["column"]}}],
                "controlValues": {
                    "enableEmptyFilter": fd.get("enable_empty_filter", False),
                    "multiSelect": fd.get("multi_select", True),
                    "searchAllOptions": fd.get("search_all_options", False),
                    "inverseSelection": False,
                    "defaultToFirstItem": False,
                },
                "defaultDataMask": {
                    "extraFormData": {},
                    "filterState": {},
                    "ownState": {},
                },
                "cascadeParentIds": (
                    [fd["cascade_parent_id"]] if fd.get("cascade_parent_id") else []
                ),
                "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
                "chartsInScope": chart_ids,
                "tabsInScope": [],
            }
            new_filters.append(f)

        metadata["native_filter_configuration"] = new_filters
        metadata["show_native_filters"] = True
        metadata["filter_bar_orientation"] = "VERTICAL"
        metadata["cross_filters_enabled"] = True
        metadata["filter_scopes"] = {}

        await client.put(f"/api/v1/dashboard/{dashboard_id}", json_data={
            "json_metadata": json.dumps(metadata, ensure_ascii=False),
        })

        response = {
            "status": "ok",
            "filters_created": len(new_filters),
            "chartsInScope": chart_ids,
            "filter_ids": [f["id"] for f in new_filters],
        }

        # === Автоматика: настроить датасеты и чарты для работы фильтров ===
        # 1. always_filter_main_dttm на всех датасетах
        datasets_auto = await _ensure_datasets_filter_ready(
            client, dashboard_id
        )
        if datasets_auto:
            response["_auto_datasets_updated"] = datasets_auto

        # 2. granularity_sqla + проверка колонок для ВСЕХ фильтров
        # Берём первый фильтр для auto_fix (granularity_sqla из time или main_dttm_col)
        first_fd = filter_defs[0] if filter_defs else {}
        first_type = first_fd.get("type", "filter_select")
        first_col = first_fd.get("column", "")
        if first_col:
            charts_auto = await _auto_fix_charts_for_filter(
                client, dashboard_id, first_col, first_type
            )
            if charts_auto["charts_updated"]:
                response["_auto_charts_updated"] = charts_auto["charts_updated"]
            if charts_auto["column_warnings"]:
                response["_auto_column_warnings"] = charts_auto[
                    "column_warnings"
                ]
            if charts_auto["warnings"]:
                response["_auto_warnings"] = charts_auto["warnings"]

        return json.dumps(response, ensure_ascii=False, indent=2)
