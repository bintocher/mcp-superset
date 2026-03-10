"""Инструменты для управления графиками (charts) Superset."""

import base64
import json
import re

from superset_mcp.tools.helpers import auto_sync_chart_dashboards

# Паттерны moment.js форматов дат, которые НЕ работают в Superset 6.x
# Superset использует D3 strftime (%Y-%m-%d), moment.js (YYYY-MM-DD) показывает литерал
_MOMENTJS_DATE_PATTERNS = re.compile(
    r'(?<![%\w])'  # не после % или буквы (исключить D3 форматы и слова)
    r'(?:'
    r'YYYY[-/.]MM[-/.]DD'  # YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    r'|DD[-/.]MM[-/.]YYYY'  # DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
    r'|MM[-/.]DD[-/.]YYYY'  # MM-DD-YYYY
    r'|YYYY[-/.]MM'          # YYYY-MM
    r'|MMM[\s]YYYY'          # MMM YYYY
    r'|DD[\s]MMM[\s]YYYY'    # DD MMM YYYY
    r'|HH:mm(?::ss)?'        # HH:mm, HH:mm:ss
    r')'
)

# Параметры params, в которых передаются форматы дат
_DATE_FORMAT_KEYS = {
    "table_timestamp_format", "x_axis_time_format", "tooltipTimeFormat",
    "y_axis_format", "header_timestamp_format",
}

# Legacy viz_type, удалённые из фронтенда Superset 5.0/6.x
# Фронтенд вернёт ошибку: "Item with key 'X' is not registered"
_DEPRECATED_VIZ_TYPES = {
    # Удалены в Superset 5.0 (авто-миграция через superset viz-migrations upgrade)
    "area": "echarts_area",
    "bar": "echarts_timeseries_bar",
    "line": "echarts_timeseries_line (или echarts_timeseries_smooth для cardinal, echarts_timeseries_step для step)",
    "heatmap": "heatmap_v2",
    "histogram": "histogram_v2",
    "sankey": "sankey_v2",
    "sankey_loop": "нет замены (удалён без замены)",
    "event_flow": "нет замены (удалён без замены)",
    # Удалены в Superset 3.0/4.0
    "dist_bar": "echarts_timeseries_bar (с orientation: horizontal для горизонтального)",
    "dual_line": "mixed_timeseries (2 метрики с 2 осями Y)",
    "treemap": "treemap_v2",
    "sunburst": "sunburst_v2",
    "pivot_table": "pivot_table_v2",
    "line_multi": "mixed_timeseries",
    "filter_box": "Native Dashboard Filters (dashboard_filter_add)",
    # Удалены ранее
    "markup": "Dashboard Markdown component",
    "separator": "Dashboard Markdown component",
    "iframe": "Dashboard Markdown component",
}

# Актуальные viz_type в Superset 6.x (зарегистрированы в MainPreset.ts)
# Используется для валидации — если viz_type нет ни в актуальных, ни в deprecated,
# выдаём предупреждение (возможно опечатка)
_VALID_VIZ_TYPES = {
    # ECharts
    "big_number", "big_number_total", "pop_kpi",
    "box_plot", "bubble_v2", "echarts_area",
    "echarts_timeseries", "echarts_timeseries_bar",
    "echarts_timeseries_line", "echarts_timeseries_scatter",
    "echarts_timeseries_smooth", "echarts_timeseries_step",
    "funnel", "gantt_chart", "gauge_chart", "graph_chart",
    "heatmap_v2", "histogram_v2", "mixed_timeseries",
    "pie", "radar", "sankey_v2", "sunburst_v2",
    "tree_chart", "treemap_v2", "waterfall",
    # Таблицы
    "table", "pivot_table_v2", "ag-grid-table",
    # Шаблоны и текст
    "handlebars",
    # Карты
    "country_map", "world_map", "mapbox",
    # deck.gl
    "deck_arc", "deck_contour", "deck_geojson", "deck_grid",
    "deck_heatmap", "deck_hex", "deck_multi", "deck_path",
    "deck_polygon", "deck_scatter", "deck_screengrid",
    # Legacy (пока зарегистрированы, но могут быть удалены в будущем)
    "bubble", "bullet", "cal_heatmap", "chord", "compare",
    "horizon", "paired_ttest", "para", "partition",
    "rose", "time_pivot", "time_table", "word_cloud",
}


def _validate_chart_params(params_str: str | None, viz_type: str | None = None) -> str | None:
    """Проверить params и viz_type на типичные ошибки. Возвращает текст ошибки или None."""
    errors = []

    # Проверка deprecated viz_type
    vt = viz_type
    if vt is None and params_str:
        try:
            vt = json.loads(params_str).get("viz_type")
        except (json.JSONDecodeError, AttributeError):
            pass
    if vt and vt in _DEPRECATED_VIZ_TYPES:
        replacement = _DEPRECATED_VIZ_TYPES[vt]
        errors.append(
            f"viz_type '{vt}' удалён из Superset 6.x (ошибка 'Item with key \"{vt}\" "
            f"is not registered'). Используйте: {replacement}"
        )
    elif vt and vt not in _VALID_VIZ_TYPES:
        errors.append(
            f"viz_type '{vt}' не найден в списке актуальных типов Superset 6.x. "
            f"Возможно опечатка. Доступные типы: "
            + ", ".join(sorted(_VALID_VIZ_TYPES))
        )

    # Парсинг params для всех проверок ниже
    if params_str:
        try:
            params_dict = json.loads(params_str)
        except json.JSONDecodeError:
            params_dict = {}
    else:
        params_dict = {}

    # Проверка granularity_sqla — ОБЯЗАТЕЛЕН для работы фильтров дашборда
    if params_str and not params_dict.get("granularity_sqla"):
        errors.append(
            "params не содержит 'granularity_sqla' — БЕЗ этого параметра "
            "фильтры дашборда (time range, native filters) НЕ будут работать "
            "для этого чарта. SQL будет генерироваться без WHERE по дате. "
            "Добавьте granularity_sqla с названием временной колонки датасета "
            "(напр. \"granularity_sqla\": \"call_date\"). "
            "Узнать колонку: dataset_get → main_dttm_col или columns[].is_dttm=true"
        )

    # Проверка moment.js форматов в params
    if params_str:
        for key in _DATE_FORMAT_KEYS:
            value = params_dict.get(key)
            if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                errors.append(
                    f"Параметр '{key}' содержит moment.js формат '{value}' — "
                    f"Superset 6.x покажет его как ЛИТЕРАЛЬНЫЙ ТЕКСТ! "
                    f"Используйте D3 strftime: "
                    f'"%Y-%m-%d" (дата), "%Y-%m-%d %H:%M" (дата+время), '
                    f'"%d.%m.%Y" (русский), "%Y-%m" (год-месяц), "%Y" (год)'
                )

        # Проверка moment.js формата в query_context form_data
        form_data = params_dict.get("form_data", {})
        if isinstance(form_data, str):
            try:
                form_data = json.loads(form_data)
            except json.JSONDecodeError:
                form_data = {}
        if isinstance(form_data, dict):
            for key in _DATE_FORMAT_KEYS:
                value = form_data.get(key)
                if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                    errors.append(
                        f"form_data.'{key}' содержит moment.js формат '{value}' — "
                        f"замените на D3 strftime (напр. \"%Y-%m-%d\")"
                    )

    if errors:
        return "ОТКЛОНЕНО:\n" + "\n".join(f"• {e}" for e in errors)
    return None


def _validate_query_context(query_context_str: str | None) -> str | None:
    """Проверить query_context на moment.js форматы."""
    if not query_context_str:
        return None
    try:
        qc = json.loads(query_context_str)
    except json.JSONDecodeError:
        return None

    errors = []
    # Проверяем form_data внутри query_context
    form_data = qc.get("form_data", {})
    if isinstance(form_data, str):
        try:
            form_data = json.loads(form_data)
        except json.JSONDecodeError:
            form_data = {}
    if isinstance(form_data, dict):
        for key in _DATE_FORMAT_KEYS:
            value = form_data.get(key)
            if isinstance(value, str) and _MOMENTJS_DATE_PATTERNS.search(value):
                errors.append(
                    f"query_context.form_data.'{key}' содержит moment.js формат "
                    f"'{value}' — замените на D3 strftime (напр. \"%Y-%m-%d\")"
                )

    if errors:
        return "ОТКЛОНЕНО:\n" + "\n".join(f"• {e}" for e in errors)
    return None


def register_chart_tools(mcp):
    from superset_mcp.server import superset_client as client

    @mcp.tool
    async def superset_chart_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список графиков Superset с пагинацией.

        ВАЖНО: всегда вызывайте этот инструмент перед chart_get/chart_delete,
        чтобы узнать актуальные ID графиков.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:slice_name,opr:ct,value:поиск)))
                - По типу: (filters:!((col:viz_type,opr:eq,value:table)))
                - По датасету: (filters:!((col:datasource_id,opr:eq,value:1)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/chart/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/chart/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_get(chart_id: int) -> str:
        """Получить детальную информацию о графике по ID.

        Возвращает все настройки: viz_type, params, query_context, привязки к дашбордам.
        ВАЖНО: если ID неизвестен, сначала вызовите superset_chart_list.

        Args:
            chart_id: ID графика (целое число из результата chart_list).
        """
        result = await client.get(f"/api/v1/chart/{chart_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_create(
        slice_name: str,
        viz_type: str,
        datasource_id: int,
        datasource_type: str = "table",
        params: str | None = None,
        query_context: str | None = None,
        dashboards: list[int] | None = None,
    ) -> str:
        """Создать новый график (chart).

        Args:
            slice_name: Название графика (отображается в UI).
            viz_type: Тип визуализации (Superset 6.x). Основные типы:
                ECharts (рекомендуемые):
                - echarts_timeseries_bar — столбчатая/горизонтальная диаграмма
                - echarts_timeseries_line — линейный график
                - echarts_timeseries_smooth — сглаженная линия
                - echarts_timeseries_step — ступенчатая линия
                - echarts_timeseries_scatter — точечная диаграмма
                - echarts_area — площадная диаграмма
                - mixed_timeseries — несколько серий с 2 осями Y
                - pie — круговая диаграмма
                - funnel — воронка
                - gauge_chart — спидометр/шкала
                - radar — радарная диаграмма
                - graph_chart — граф/сеть
                - tree_chart — дерево
                - treemap_v2 — древовидная карта
                - sunburst_v2 — солнечная диаграмма
                - sankey_v2 — диаграмма Санкей
                - heatmap_v2 — тепловая карта
                - histogram_v2 — гистограмма
                - box_plot — ящик с усами
                - bubble_v2 — пузырьковая диаграмма
                - waterfall — водопадная диаграмма
                - gantt_chart — диаграмма Ганта
                KPI:
                - big_number_total — большое число (KPI)
                - big_number — KPI с трендом
                Таблицы:
                - table — таблица
                - pivot_table_v2 — сводная таблица
                Карты:
                - country_map — карта страны (ISO 3166-2 коды)
                - world_map — карта мира
                Другие:
                - word_cloud — облако слов
                - handlebars — кастомный шаблон
                DEPRECATED (НЕ ИСПОЛЬЗОВАТЬ — ошибка "not registered"):
                  dist_bar → echarts_timeseries_bar, bar → echarts_timeseries_bar,
                  area → echarts_area, line → echarts_timeseries_line,
                  heatmap → heatmap_v2, histogram → histogram_v2,
                  treemap → treemap_v2, sunburst → sunburst_v2,
                  sankey → sankey_v2, pivot_table → pivot_table_v2,
                  dual_line → mixed_timeseries, line_multi → mixed_timeseries
            datasource_id: ID датасета (из superset_dataset_list).
            datasource_type: Тип источника данных (по умолчанию "table" — датасет).
            params: JSON-строка с параметрами визуализации (зависят от viz_type).
                Определяют метрики, группировки, фильтры, цвета, подписи и т.д.

                ВАЖНО — числовые и временные форматы:
                  НЕ используйте SMART_NUMBER и SMART_DATE — они сокращают числа
                  (1.61k вместо 1610) и показывают литерал вместо даты.
                  Используйте конкретные форматы:
                  - y_axis_format: "d" (целые без запятых), ",d" (целые с запятыми), ",.2f" (дробные)
                  - number_format: ",d" (для pie chart)
                  - x_axis_time_format: "%b %Y" (ось X дат), "%Y-%m-%d" (ISO)
                  - tooltipTimeFormat: "%Y-%m-%d" или "%Y-%m" (tooltip дат)
                  - show_value: true (показать числа на столбцах bar chart)

                КРИТИЧНО — формат дат и времени в Superset 6.x:
                  Superset 6.x использует ТОЛЬКО D3 time format (strftime-синтаксис).
                  НЕ используйте moment.js формат (YYYY-MM-DD) — он будет показан
                  как литеральный текст "YYYY-MM-DD" вместо даты!
                  Правильные форматы (D3/strftime):
                  - "%Y-%m-%d"       → 2026-03-05 (дата ISO)
                  - "%Y-%m-%d %H:%M" → 2026-03-05 14:30 (дата + время)
                  - "%d.%m.%Y"       → 05.03.2026 (русский формат)
                  - "%b %Y"          → Mar 2026 (месяц + год)
                  - "%Y"             → 2026 (только год)
                  - "%Y-%m"          → 2026-03 (год-месяц)
                  НЕПРАВИЛЬНЫЕ форматы (moment.js — НЕ РАБОТАЮТ):
                  - "YYYY-MM-DD" — покажет литерал "YYYY-MM-DD"
                  - "DD.MM.YYYY" — покажет литерал "DD.MM.YYYY"
                  - "MMM YYYY"   — покажет литерал "MMM YYYY"
                  Параметры, принимающие формат дат:
                  - table_timestamp_format (таблицы)
                  - x_axis_time_format (ось X)
                  - tooltipTimeFormat (tooltip)
                  - y_axis_format (для big_number_total с датой в метрике)

                big_number_total (KPI-карточки) — ЭТАЛОННЫЕ параметры:
                  - header_font_size: 0.27 (размер ЦИФР, ~53px в контейнере 60px)
                  - subheader_font_size: 0.15 (размер НАДПИСИ/подзаголовка)
                  - y_axis_format: "d" (целые числа без запятых-разделителей)
                  ВАЖНО — скролл в KPI: контейнер big_number_total имеет фиксированную
                  высоту (обычно 60px при 2 клетках сетки). При слишком большом шрифте
                  появляется скролл. Виновники: font-size + line-height (1.1x) + margin-bottom
                  (8px по умолчанию). Если используете CSS дашборда для кастомного размера
                  шрифта — добавляйте `margin-bottom: 0 !important` к .header-line.
                  Формула: font_size * 1.1 + margin <= container_height (60px).
                  Рекомендуемый CSS: font-size 3.3rem (58px с line-height), margin-bottom: 0.

                country_map — обязательные параметры:
                  - select_country: "russia"
                  - entity: "<колонка с ISO 3166-2 кодами>"
                  - metric: {...}
                  Tooltip карты (класс .hover-popup) обрезается контейнером
                  .dashboard-chart (overflow:hidden). Фикс через CSS дашборда:
                  .dashboard-chart-id-{N} .dashboard-chart { overflow: visible !important; }
                  .hover-popup { z-index: 99999 !important; }

            query_context: JSON-строка с контекстом запроса.
                Необходим для работы chart_get_data. Обычно генерируется UI.
            dashboards: Список ID дашбордов, к которым привязать график.
        """
        # Валидация: deprecated viz_type и moment.js форматы
        validation_error = _validate_chart_params(params, viz_type)
        if validation_error:
            return json.dumps({"error": validation_error}, ensure_ascii=False)
        qc_error = _validate_query_context(query_context)
        if qc_error:
            return json.dumps({"error": qc_error}, ensure_ascii=False)

        payload = {
            "slice_name": slice_name,
            "viz_type": viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
        }
        if params is not None:
            payload["params"] = params
        if query_context is not None:
            payload["query_context"] = query_context
        if dashboards is not None:
            payload["dashboards"] = dashboards
        result = await client.post("/api/v1/chart/", json_data=payload)

        # Авто-синхронизация: добавляем datasource_access ролям дашбордов
        new_id = result.get("id")
        if new_id:
            sync = await auto_sync_chart_dashboards(
                client, chart_id=new_id, datasource_id=datasource_id
            )
            synced = [s for s in sync if s.get("synced_roles")]
            if synced:
                result["_auto_access_synced"] = synced

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_update(
        chart_id: int,
        slice_name: str | None = None,
        viz_type: str | None = None,
        params: str | None = None,
        query_context: str | None = None,
        dashboards: list[int] | None = None,
        confirm_params_replace: bool = False,
    ) -> str:
        """Обновить существующий график. Передавайте только изменяемые поля.

        Args:
            chart_id: ID графика для обновления.
            slice_name: Новое название.
            viz_type: Новый тип визуализации (см. chart_create для списка типов).
            params: Новые JSON-параметры визуализации (перезаписывают полностью).
                См. chart_create для справки по числовым/временным форматам.
                ВАЖНО: params перезаписывает ВСЕ параметры — сначала получите текущие
                через chart_get, измените нужные поля и передайте полный JSON.
                КРИТИЧНО: для дат используйте D3 strftime-формат ("%Y-%m-%d"),
                НЕ moment.js ("YYYY-MM-DD") — иначе будет показан литерал!
            query_context: Новый JSON query context (перезаписывает полностью).
                ВАЖНО: при изменении params нужно обновить и query_context,
                иначе чарт будет использовать старый контекст запроса.
            dashboards: Новый список ID дашбордов (ЗАМЕНЯЕТ все привязки).
            confirm_params_replace: Подтверждение замены params (ОБЯЗАТЕЛЬНО при params).
        """
        # Защита от частичного params
        if params is not None and not confirm_params_replace:
            return json.dumps({
                "error": (
                    "ОТКЛОНЕНО: params перезаписывает ВСЕ параметры чарта. "
                    "Если передать только изменяемый параметр (напр. {\"y_axis_format\": \"d\"}), "
                    "все остальные настройки (metrics, groupby, filters, цвета) будут УНИЧТОЖЕНЫ. "
                    "Сначала получите текущие через chart_get, измените нужные поля, "
                    "передайте ПОЛНЫЙ JSON с confirm_params_replace=True."
                )
            }, ensure_ascii=False)

        # Валидация: deprecated viz_type и moment.js форматы
        validation_error = _validate_chart_params(params, viz_type)
        if validation_error:
            return json.dumps({"error": validation_error}, ensure_ascii=False)
        qc_error = _validate_query_context(query_context)
        if qc_error:
            return json.dumps({"error": qc_error}, ensure_ascii=False)

        payload = {}
        if slice_name is not None:
            payload["slice_name"] = slice_name
        if viz_type is not None:
            payload["viz_type"] = viz_type
        if params is not None:
            payload["params"] = params
        if query_context is not None:
            payload["query_context"] = query_context
        if dashboards is not None:
            payload["dashboards"] = dashboards
        result = await client.put(f"/api/v1/chart/{chart_id}", json_data=payload)

        # Авто-синхронизация: при изменении dashboards или datasource
        if dashboards is not None:
            sync = await auto_sync_chart_dashboards(client, chart_id=chart_id)
            synced = [s for s in sync if s.get("synced_roles")]
            if synced:
                result["_auto_access_synced"] = synced

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_delete(
        chart_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить график по ID. График будет удалён со всех дашбордов.

        Args:
            chart_id: ID графика для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
        """
        if not confirm_delete:
            try:
                chart_info = await client.get(f"/api/v1/chart/{chart_id}")
                chart = chart_info.get("result", {})
                chart_name = chart.get("slice_name", "?")
                dashboards = chart.get("dashboards", [])
                dash_names = [
                    d.get("dashboard_title", f"ID={d.get('id')}")
                    for d in dashboards
                ]
            except Exception:
                chart_name = f"ID={chart_id}"
                dash_names = []
            msg = (
                f"ОТКЛОНЕНО: удаление чарта '{chart_name}' (ID={chart_id})"
            )
            if dash_names:
                msg += f", привязан к дашбордам: {dash_names}"
            msg += ". Передайте confirm_delete=True для подтверждения."
            return json.dumps({"error": msg}, ensure_ascii=False)

        result = await client.delete(f"/api/v1/chart/{chart_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_data(
        query_context: str,
    ) -> str:
        """Выполнить произвольный запрос к датасету и получить данные.

        Позволяет получить данные напрямую из датасета, без создания графика.
        Для получения данных существующего графика используйте chart_get_data.

        Args:
            query_context: JSON-строка с контекстом запроса. Формат:
                {
                    "datasource": {"id": <dataset_id>, "type": "table"},
                    "queries": [{
                        "columns": ["col1", "col2"],
                        "metrics": [{"label": "count", "expressionType": "SIMPLE",
                                     "aggregate": "COUNT", "column": {"column_name": "id"}}],
                        "filters": [{"col": "status", "op": "==", "val": "active"}],
                        "orderby": [["col1", true]],
                        "row_limit": 100,
                        "time_range": "Last 7 days"
                    }],
                    "result_format": "json",
                    "result_type": "full"
                }
                ВАЖНО: time_range указывается НА УРОВНЕ query, НЕ внутри extras.
                Допустимые time_range: "Last day", "Last week", "Last month",
                "Last year", "No filter", или "2024-01-01 : 2024-12-31".
        """
        payload = json.loads(query_context)
        result = await client.post("/api/v1/chart/data", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_get_data(chart_id: int) -> str:
        """Получить данные конкретного сохранённого графика по его ID.

        ВАЖНО: работает только если график был сохранён с query_context
        (обычно после открытия и сохранения через Superset UI). Если query_context
        отсутствует — используйте superset_chart_data с ручным формированием запроса.

        Args:
            chart_id: ID графика.
        """
        result = await client.get(f"/api/v1/chart/{chart_id}/data/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_export(
        chart_ids: str,
    ) -> str:
        """Экспортировать графики со всеми зависимостями (датасеты, БД) в ZIP.

        Результат — base64-кодированный ZIP-файл. Можно импортировать обратно
        через superset_chart_import.

        Args:
            chart_ids: ID графиков через запятую (напр. "1,2,3").

        Returns:
            JSON: {"format": "zip", "encoding": "base64", "data": "...", "size_bytes": N}
        """
        params = {"q": f"[{chart_ids}]"}
        raw = await client.get_raw("/api/v1/chart/export/", params=params)
        return json.dumps({
            "format": "zip",
            "encoding": "base64",
            "data": base64.b64encode(raw).decode(),
            "size_bytes": len(raw),
        }, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_import(
        file_path: str,
        overwrite: bool = False,
    ) -> str:
        """Импортировать графики из ZIP-файла (созданного через export).

        ZIP должен содержать YAML-файлы с конфигурацией графиков и зависимостей.

        Args:
            file_path: Абсолютный путь к ZIP-файлу на диске.
            overwrite: Перезаписать существующие объекты с такими же UUID (по умолчанию False).
        """
        with open(file_path, "rb") as f:
            files = {"formData": (file_path.split("/")[-1], f, "application/zip")}
            data = {"overwrite": "true" if overwrite else "false"}
            result = await client.post_form(
                "/api/v1/chart/import/", files=files, data=data,
            )
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_chart_copy(
        chart_id: int,
        slice_name: str,
        dashboards: list[int] | None = None,
    ) -> str:
        """Создать копию существующего графика с новым названием.

        Копирует все параметры визуализации, тип, датасет, query_context.
        Привязки к дашбордам НЕ копируются — указывайте новые через параметр dashboards.

        Args:
            chart_id: ID исходного графика для копирования.
            slice_name: Название новой копии.
            dashboards: Список ID дашбордов для привязки копии (опционально).
        """
        source = await client.get(f"/api/v1/chart/{chart_id}")
        chart = source.get("result", {})

        payload = {
            "slice_name": slice_name,
            "viz_type": chart.get("viz_type", "table"),
            "datasource_id": chart.get("datasource_id"),
            "datasource_type": chart.get("datasource_type", "table"),
        }
        if chart.get("params"):
            payload["params"] = chart["params"]
        if chart.get("query_context"):
            payload["query_context"] = chart["query_context"]
        if dashboards is not None:
            payload["dashboards"] = dashboards

        result = await client.post("/api/v1/chart/", json_data=payload)
        new_id = result.get("id")
        return json.dumps(
            {"status": "ok", "source_id": chart_id, "new_id": new_id, "slice_name": slice_name},
            ensure_ascii=False,
        )

    @mcp.tool
    async def superset_chart_cache_warmup(
        chart_id: int,
        dashboard_id: int | None = None,
    ) -> str:
        """Предзаполнить кеш графика (warm up cache).

        Полезно для ускорения загрузки часто используемых графиков.

        Args:
            chart_id: ID графика для предзагрузки.
            dashboard_id: ID дашборда для контекста фильтров (опционально).
        """
        payload = {"chart_id": chart_id}
        if dashboard_id is not None:
            payload["dashboard_id"] = dashboard_id
        result = await client.put(
            "/api/v1/chart/warm_up_cache", json_data=payload,
        )
        return json.dumps(result, ensure_ascii=False)
