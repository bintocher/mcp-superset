"""Инструменты для системных операций: отчёты, аннотации, логи, меню, assets."""

import base64
import json


def register_system_tools(mcp):
    from superset_mcp.server import superset_client as client

    # === Reports / Alerts ===

    @mcp.tool
    async def superset_report_list(
        page: int = 0,
        page_size: int = 25,
        q: str | None = None,
        get_all: bool = False,
    ) -> str:
        """Получить список отчётов и алертов Superset.

        Отчёты — периодическая отправка скриншотов дашбордов/графиков.
        Алерты — уведомления при выполнении SQL-условия.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По названию: (filters:!((col:name,opr:ct,value:поиск)))
                - По типу: (filters:!((col:type,opr:eq,value:Report)))
                - Активные: (filters:!((col:active,opr:eq,value:!t)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/report/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/report/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_get(report_id: int) -> str:
        """Получить детальную информацию об отчёте/алерте по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите superset_report_list.

        Args:
            report_id: ID отчёта (целое число из результата report_list).
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
        """Создать отчёт (периодическая рассылка) или алерт (по SQL-условию).

        Для Report: укажите dashboard или chart — Superset будет отправлять скриншот по расписанию.
        Для Alert: укажите database и sql — Superset проверяет условие и уведомляет при срабатывании.

        Args:
            name: Название отчёта/алерта.
            crontab: Cron-расписание. Примеры:
                - "0 9 * * *" — каждый день в 9:00
                - "0 9 * * 1" — каждый понедельник в 9:00
                - "0 */6 * * *" — каждые 6 часов
            report_type: Тип: "Report" (рассылка, по умолчанию) или "Alert" (по условию).
            dashboard: ID дашборда для скриншота (для Report).
            chart: ID графика для скриншота (для Report).
            database: ID подключения к БД (для Alert — SQL-условие).
            sql: SQL-запрос для проверки условия (для Alert).
                Алерт срабатывает, если запрос возвращает непустой результат.
            recipients: JSON-строка со списком получателей. Формат:
                [{"type": "Email", "recipient_config_json": {"target": "user@example.com"}}]
            active: Активен ли (по умолчанию True).
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
            payload["recipients"] = json.loads(recipients)
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
        """Обновить отчёт/алерт. Передавайте только изменяемые поля.

        Args:
            report_id: ID отчёта для обновления.
            name: Новое название.
            crontab: Новое cron-расписание (напр. "0 9 * * *").
            active: Включить/выключить отчёт.
            recipients: JSON-строка с новым списком получателей (ЗАМЕНЯЕТ всех текущих).
        """
        payload = {}
        if name is not None:
            payload["name"] = name
        if crontab is not None:
            payload["crontab"] = crontab
        if active is not None:
            payload["active"] = active
        if recipients is not None:
            payload["recipients"] = json.loads(recipients)
        result = await client.put(f"/api/v1/report/{report_id}", json_data=payload)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_report_delete(
        report_id: int,
        confirm_delete: bool = False,
    ) -> str:
        """Удалить отчёт/алерт. Рассылка будет остановлена.

        Args:
            report_id: ID отчёта для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
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
                        f"ОТКЛОНЕНО: удаление {rtype} '{name}' "
                        f"(ID={report_id}, active={active}). "
                        f"Передайте confirm_delete=True для подтверждения."
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
        """Получить список слоёв аннотаций.

        Слой аннотаций — контейнер для аннотаций (событий на временной шкале),
        которые можно наложить на графики.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            result = await client.get_all("/api/v1/annotation_layer/")
        else:
            params = {"page": page, "page_size": page_size}
            result = await client.get("/api/v1/annotation_layer/", params=params)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_list(
        annotation_layer_id: int,
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """Получить список аннотаций в указанном слое.

        Args:
            annotation_layer_id: ID слоя аннотаций (из annotation_layer_list).
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            result = await client.get_all(
                f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
            )
        else:
            params = {"page": page, "page_size": page_size}
            result = await client.get(
                f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/",
                params=params,
            )
        return json.dumps(result, ensure_ascii=False)

    # === Activity & Logs ===

    @mcp.tool
    async def superset_recent_activity(
        page: int = 0,
        page_size: int = 25,
        get_all: bool = False,
    ) -> str:
        """Получить недавнюю активность текущего пользователя (просмотры, редактирования).

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            result = await client.get_all("/api/v1/log/recent_activity/")
        else:
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
        """Получить журнал аудита действий всех пользователей Superset.

        Args:
            page: Номер страницы (начиная с 0).
            page_size: Количество записей на странице (макс. 100).
            q: RISON-фильтр для поиска. Примеры:
                - По пользователю: (filters:!((col:user,opr:rel_o_m,value:1)))
                - По действию: (filters:!((col:action,opr:ct,value:explore)))
            get_all: Получить ВСЕ записи с автоматической пагинацией (игнорирует page/page_size).
        """
        if get_all:
            params = {}
            if q:
                params["q"] = q
            result = await client.get_all("/api/v1/log/", params=params)
        else:
            params = {"page": page, "page_size": page_size}
            if q:
                params["q"] = q
            result = await client.get("/api/v1/log/", params=params)
        return json.dumps(result, ensure_ascii=False)

    # === Menu & System ===

    @mcp.tool
    async def superset_get_menu() -> str:
        """Получить структуру навигационного меню Superset.

        Полезно для понимания доступных разделов и прав текущего пользователя.
        """
        result = await client.get("/api/v1/menu/")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_get_base_url() -> str:
        """Получить базовый URL настроенного Superset-инстанса.

        Возвращает URL, используемый MCP-сервером для подключения к Superset.
        """
        from superset_mcp.server import SUPERSET_BASE_URL

        return json.dumps({"base_url": SUPERSET_BASE_URL}, ensure_ascii=False)

    # === Annotation Layer CRUD ===

    @mcp.tool
    async def superset_annotation_layer_create(
        name: str,
        descr: str | None = None,
    ) -> str:
        """Создать новый слой аннотаций.

        Слой — контейнер для аннотаций, которые можно наложить на временные графики.

        Args:
            name: Название слоя.
            descr: Описание слоя (опционально).
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
        """Получить информацию о слое аннотаций по ID.

        ВАЖНО: если ID неизвестен, сначала вызовите annotation_layer_list.

        Args:
            annotation_layer_id: ID слоя (из annotation_layer_list).
        """
        result = await client.get(f"/api/v1/annotation_layer/{annotation_layer_id}")
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool
    async def superset_annotation_layer_update(
        annotation_layer_id: int,
        name: str | None = None,
        descr: str | None = None,
    ) -> str:
        """Обновить слой аннотаций. Передавайте только изменяемые поля.

        Args:
            annotation_layer_id: ID слоя для обновления.
            name: Новое название слоя.
            descr: Новое описание слоя.
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
        """Удалить слой аннотаций вместе со всеми аннотациями внутри.

        КРИТИЧНО: удаляет слой И все аннотации в нём безвозвратно.

        Args:
            annotation_layer_id: ID слоя для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
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
                        f"ОТКЛОНЕНО: удаление слоя аннотаций '{name}' "
                        f"(ID={annotation_layer_id}) вместе с {ann_count} аннотациями. "
                        f"Передайте confirm_delete=True для подтверждения."
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
        """Создать аннотацию (событие на временной шкале) в указанном слое.

        Аннотации отображаются как вертикальные линии или области на временных графиках.

        Args:
            annotation_layer_id: ID слоя аннотаций (из annotation_layer_list).
            short_descr: Краткое описание события (отображается на графике).
            start_dttm: Дата/время начала в ISO-формате. Пример: "2024-01-01T00:00:00"
            end_dttm: Дата/время окончания в ISO-формате. Пример: "2024-01-01T23:59:59"
                Для точечного события start_dttm = end_dttm.
            long_descr: Подробное описание события (опционально).
            json_metadata: JSON-строка с дополнительными метаданными (опционально).
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
        """Получить аннотацию по ID.

        Args:
            annotation_layer_id: ID слоя аннотаций.
            annotation_id: ID аннотации (из annotation_list).
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
        """Обновить аннотацию. Передавайте только изменяемые поля.

        Args:
            annotation_layer_id: ID слоя аннотаций.
            annotation_id: ID аннотации для обновления.
            short_descr: Новое краткое описание.
            start_dttm: Новая дата начала (ISO-формат: "2024-01-01T00:00:00").
            end_dttm: Новая дата окончания (ISO-формат).
            long_descr: Новое подробное описание.
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
        """Удалить аннотацию из слоя.

        Args:
            annotation_layer_id: ID слоя аннотаций.
            annotation_id: ID аннотации для удаления.
            confirm_delete: Подтверждение удаления (ОБЯЗАТЕЛЬНО).
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
                        f"ОТКЛОНЕНО: удаление аннотации '{descr}' "
                        f"(ID={annotation_id}) из слоя {annotation_layer_id}. "
                        f"Передайте confirm_delete=True для подтверждения."
                    )
                },
                ensure_ascii=False,
            )

        result = await client.delete(f"/api/v1/annotation_layer/{annotation_layer_id}/annotation/{annotation_id}")
        return json.dumps(result, ensure_ascii=False)

    # === Assets Export/Import ===

    @mcp.tool
    async def superset_assets_export() -> str:
        """Экспортировать ВСЕ ассеты Superset в один ZIP-файл.

        Включает: дашборды, графики, датасеты, подключения к БД (без паролей).
        Полезно для бэкапа или миграции между инстансами.

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
        """Импортировать ассеты Superset из ZIP-файла (созданного через assets_export).

        КРИТИЧНО: overwrite=True перезаписывает ВСЕ совпадающие объекты
        (дашборды, чарты, датасеты, БД). Это необратимо.

        Args:
            file_path: Абсолютный путь к ZIP-файлу на диске.
            overwrite: Перезаписать существующие объекты с такими же UUID (по умолчанию False).
            confirm_overwrite: Подтверждение перезаписи (ОБЯЗАТЕЛЬНО при overwrite=True).
        """
        if overwrite and not confirm_overwrite:
            return json.dumps(
                {
                    "error": (
                        "ОТКЛОНЕНО: overwrite=True без confirm_overwrite=True. "
                        "assets_import с overwrite=True перезаписывает ВСЕ совпадающие "
                        "объекты (дашборды, чарты, датасеты, подключения к БД). "
                        "Это может откатить весь Superset к состоянию из ZIP-файла. "
                        "Передайте confirm_overwrite=True для подтверждения."
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
