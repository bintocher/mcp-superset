# superset-mcp

[![PyPI version](https://img.shields.io/pypi/v/superset-mcp.svg)](https://pypi.org/project/superset-mcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/bintocher/superset-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/bintocher/superset-mcp/actions/workflows/ci.yml)

[English](README.md) | **Русский**

Полнофункциональный [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) сервер для [Apache Superset](https://superset.apache.org/). Предоставляет AI-ассистентам (Claude, GPT и др.) полный контроль над инстансом Superset — дашборды, графики, датасеты, SQL Lab, пользователи, роли, RLS и многое другое — через 128+ инструментов.

## Возможности

- **128+ MCP-инструментов**, покрывающих полный REST API Superset
- **Управление дашбордами** — CRUD, копирование, публикация, экспорт/импорт, встраивание, нативные фильтры
- **Управление графиками** — CRUD, копирование, получение данных, экспорт/импорт, прогрев кэша
- **Управление базами данных** — CRUD, проверка подключения, интроспекция схем/таблиц, валидация SQL
- **Управление датасетами** — CRUD, дублирование, обновление схемы, экспорт/импорт
- **SQL Lab** — выполнение запросов, форматирование, оценка стоимости, экспорт результатов
- **Безопасность** — пользователи, роли, права, Row Level Security (RLS), группы
- **Автоматизация доступа** — grant/revoke с автоматической синхронизацией datasource_access
- **Аудит** — матрица прав доступа (пользователь × дашборды × датасеты × RLS)
- **Теги, отчёты, аннотации, сохранённые запросы** — полный CRUD
- **Экспорт/импорт ассетов** — полный бэкап и восстановление инстанса
- **Встроенная защита** — подтверждения для деструктивных операций, блокировка DDL/DML в SQL Lab
- **JWT-аутентификация** с автоматическим обновлением токенов и CSRF
- **Транспорты**: Streamable HTTP, SSE, stdio

## Быстрый старт

### Установка

```bash
# Из PyPI
pip install superset-mcp

# Или через uv (рекомендуется)
uv pip install superset-mcp
```

### Конфигурация

Создайте файл `.env` или установите переменные окружения:

```env
# Обязательные
SUPERSET_BASE_URL=https://superset.example.com
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=your_password

# Необязательные
SUPERSET_AUTH_PROVIDER=db          # db (по умолчанию) или ldap
SUPERSET_MCP_HOST=127.0.0.1       # Адрес сервера (по умолчанию: 127.0.0.1)
SUPERSET_MCP_PORT=8001             # Порт сервера (по умолчанию: 8001)
SUPERSET_MCP_TRANSPORT=streamable-http  # streamable-http (по умолчанию), sse или stdio
```

### Запуск

```bash
# Через CLI (установленный из pip)
superset-mcp

# Через Python-модуль
python -m superset_mcp

# С пользовательскими параметрами
superset-mcp --host 0.0.0.0 --port 9000 --transport sse

# С указанием .env файла
superset-mcp --env-file /path/to/.env

# Через stdio (для прямого подключения MCP-клиента)
superset-mcp --transport stdio
```

### Параметры CLI

| Параметр | По умолчанию | Переменная окружения | Описание |
|----------|-------------|---------------------|----------|
| `--host` | `127.0.0.1` | `SUPERSET_MCP_HOST` | Адрес привязки сервера |
| `--port` | `8001` | `SUPERSET_MCP_PORT` | Порт сервера |
| `--transport` | `streamable-http` | `SUPERSET_MCP_TRANSPORT` | Транспорт: `streamable-http`, `sse`, `stdio` |
| `--env-file` | авто | — | Путь к `.env` файлу |
| `--version` | — | — | Показать версию и выйти |

### Подключение к MCP-клиентам

#### Claude Code

Добавьте в `.mcp.json`:

```json
{
  "mcpServers": {
    "superset": {
      "type": "http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

#### Claude Desktop

Добавьте в `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "superset": {
      "command": "superset-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "SUPERSET_BASE_URL": "https://superset.example.com",
        "SUPERSET_USERNAME": "admin",
        "SUPERSET_PASSWORD": "your_password"
      }
    }
  }
}
```

#### Другие MCP-клиенты

Любой MCP-совместимый клиент может подключиться через:
- **Streamable HTTP**: `http://<host>:<port>/mcp`
- **SSE**: `http://<host>:<port>/sse`
- **stdio**: пайп к `superset-mcp --transport stdio`

## Доступные инструменты (128+)

### Дашборды (15 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_dashboard_list` | Список дашбордов с фильтрацией и пагинацией |
| `superset_dashboard_get` | Получить дашборд по ID |
| `superset_dashboard_create` | Создать новый дашборд |
| `superset_dashboard_update` | Обновить свойства дашборда |
| `superset_dashboard_delete` | Удалить дашборд (требует подтверждения) |
| `superset_dashboard_copy` | Дублировать дашборд |
| `superset_dashboard_publish` | Опубликовать дашборд |
| `superset_dashboard_unpublish` | Снять публикацию дашборда |
| `superset_dashboard_charts` | Список графиков в дашборде |
| `superset_dashboard_datasets` | Список датасетов дашборда |
| `superset_dashboard_export` | Экспортировать дашборд (ZIP, base64) |
| `superset_dashboard_import` | Импортировать дашборд из ZIP |
| `superset_dashboard_embedded_get` | Получить конфигурацию встраивания |
| `superset_dashboard_embedded_set` | Включить режим встраивания |
| `superset_dashboard_embedded_delete` | Выключить режим встраивания |

### Фильтры дашбордов (5 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_dashboard_filter_list` | Список нативных фильтров дашборда |
| `superset_dashboard_filter_add` | Добавить нативный фильтр (авто-генерация ID) |
| `superset_dashboard_filter_update` | Обновить существующий фильтр |
| `superset_dashboard_filter_delete` | Удалить фильтр (требует подтверждения) |
| `superset_dashboard_filter_reset` | Удалить все фильтры (требует подтверждения) |

### Графики (11 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_chart_list` | Список графиков с фильтрацией |
| `superset_chart_get` | Получить график по ID |
| `superset_chart_create` | Создать новый график |
| `superset_chart_update` | Обновить свойства графика |
| `superset_chart_delete` | Удалить график (требует подтверждения) |
| `superset_chart_copy` | Дублировать график |
| `superset_chart_data` | Выполнить запрос графика и получить данные |
| `superset_chart_get_data` | Получить данные сохранённого графика |
| `superset_chart_export` | Экспортировать график (ZIP, base64) |
| `superset_chart_import` | Импортировать график из ZIP |
| `superset_chart_cache_warmup` | Прогреть кэш графика |

### Базы данных (18 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_database_list` | Список подключений к БД |
| `superset_database_get` | Получить детали подключения |
| `superset_database_create` | Зарегистрировать новое подключение |
| `superset_database_update` | Обновить настройки подключения |
| `superset_database_delete` | Удалить подключение (требует подтверждения) |
| `superset_database_test_connection` | Проверить связь с БД |
| `superset_database_schemas` | Список схем в БД |
| `superset_database_tables` | Список таблиц в схеме |
| `superset_database_catalogs` | Список каталогов |
| `superset_database_connection_info` | Информация о строке подключения |
| `superset_database_function_names` | Список доступных SQL-функций |
| `superset_database_related_objects` | Найти графики/датасеты, использующие эту БД |
| `superset_database_validate_sql` | Валидация синтаксиса SQL |
| `superset_database_validate_parameters` | Валидация параметров подключения |
| `superset_database_select_star` | Сгенерировать SELECT * для таблицы |
| `superset_database_table_metadata` | Метаданные колонок и индексов таблицы |
| `superset_database_export` | Экспортировать конфигурацию БД |
| `superset_database_available_engines` | Список поддерживаемых СУБД |

### Датасеты (11 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_dataset_list` | Список датасетов с фильтрацией |
| `superset_dataset_get` | Получить детали датасета (колонки, метрики) |
| `superset_dataset_create` | Создать датасет из таблицы или SQL-запроса |
| `superset_dataset_update` | Обновить свойства датасета |
| `superset_dataset_delete` | Удалить датасет (требует подтверждения) |
| `superset_dataset_duplicate` | Дублировать датасет |
| `superset_dataset_refresh_schema` | Обновить колонки из источника |
| `superset_dataset_related_objects` | Найти графики, использующие датасет |
| `superset_dataset_export` | Экспортировать датасет (ZIP) |
| `superset_dataset_import` | Импортировать датасет из ZIP |
| `superset_dataset_get_or_create` | Получить существующий или создать новый |

### SQL Lab и запросы (13 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_sqllab_execute` | Выполнить SQL-запрос (только SELECT) |
| `superset_sqllab_format_sql` | Форматировать SQL |
| `superset_sqllab_results` | Получить результаты выполненного запроса |
| `superset_sqllab_estimate_cost` | Оценить стоимость выполнения запроса |
| `superset_sqllab_export_csv` | Экспортировать результаты в CSV |
| `superset_query_list` | Список выполненных запросов |
| `superset_query_get` | Получить детали и результаты запроса |
| `superset_query_stop` | Остановить выполняющийся запрос |
| `superset_saved_query_list` | Список сохранённых запросов |
| `superset_saved_query_create` | Сохранить новый запрос |
| `superset_saved_query_get` | Получить сохранённый запрос |
| `superset_saved_query_update` | Обновить сохранённый запрос |
| `superset_saved_query_delete` | Удалить сохранённый запрос (требует подтверждения) |

### Безопасность и контроль доступа (22 инструмента)

| Инструмент | Описание |
|------------|----------|
| `superset_get_current_user` | Информация о текущем пользователе |
| `superset_get_current_user_roles` | Роли текущего пользователя |
| `superset_user_list` | Список пользователей с фильтрацией |
| `superset_user_get` | Получить детали пользователя |
| `superset_user_create` | Создать нового пользователя |
| `superset_user_update` | Обновить свойства пользователя |
| `superset_user_delete` | Удалить пользователя (требует подтверждения) |
| `superset_role_list` | Список ролей |
| `superset_role_get` | Получить детали роли |
| `superset_role_create` | Создать новую роль |
| `superset_role_update` | Обновить имя/описание роли |
| `superset_role_delete` | Удалить роль (требует подтверждения, блокирует системные) |
| `superset_permission_list` | Список всех доступных прав |
| `superset_role_permissions_get` | Получить права роли |
| `superset_role_permission_add` | Установить права роли (полная замена, требует подтверждения) |
| `superset_dashboard_grant_role_access` | Выдать роли доступ к дашборду и его датасетам |
| `superset_dashboard_revoke_role_access` | Отозвать доступ роли к датасетам дашборда |
| `superset_rls_list` | Список RLS-правил |
| `superset_rls_get` | Получить детали RLS-правила |
| `superset_rls_create` | Создать RLS-правило |
| `superset_rls_update` | Обновить RLS-правило (требует roles и tables одновременно) |
| `superset_rls_delete` | Удалить RLS-правило (требует подтверждения) |

### Группы (9 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_group_list` | Список групп |
| `superset_group_get` | Получить детали группы |
| `superset_group_create` | Создать новую группу |
| `superset_group_update` | Обновить название группы |
| `superset_group_delete` | Удалить группу |
| `superset_group_add_users` | Добавить пользователей в группу |
| `superset_group_remove_users` | Удалить пользователей из группы |
| `superset_group_add_roles` | Добавить роли в группу |
| `superset_group_remove_roles` | Удалить роли из группы |

### Теги (7 инструментов)

| Инструмент | Описание |
|------------|----------|
| `superset_tag_list` | Список тегов |
| `superset_tag_get` | Получить детали тега |
| `superset_tag_create` | Создать тег (опционально привязать к объектам) |
| `superset_tag_update` | Обновить тег |
| `superset_tag_delete` | Удалить тег (требует подтверждения) |
| `superset_tag_get_objects` | Список объектов, привязанных к тегу |
| `superset_tag_bulk_create` | Создать несколько тегов |

### Система и отчёты (21 инструмент)

| Инструмент | Описание |
|------------|----------|
| `superset_report_list` | Список расписаний отчётов |
| `superset_report_get` | Получить детали отчёта |
| `superset_report_create` | Создать расписание отчёта |
| `superset_report_update` | Обновить отчёт |
| `superset_report_delete` | Удалить отчёт (требует подтверждения) |
| `superset_annotation_layer_list` | Список слоёв аннотаций |
| `superset_annotation_layer_get` | Получить детали слоя |
| `superset_annotation_layer_create` | Создать слой аннотаций |
| `superset_annotation_layer_update` | Обновить слой аннотаций |
| `superset_annotation_layer_delete` | Удалить слой (требует подтверждения) |
| `superset_annotation_list` | Список аннотаций в слое |
| `superset_annotation_get` | Получить детали аннотации |
| `superset_annotation_create` | Создать аннотацию |
| `superset_annotation_update` | Обновить аннотацию |
| `superset_annotation_delete` | Удалить аннотацию (требует подтверждения) |
| `superset_recent_activity` | Недавняя активность пользователей |
| `superset_log_list` | Журнал аудита |
| `superset_get_menu` | Структура меню Superset |
| `superset_get_base_url` | Настроенный базовый URL Superset |
| `superset_assets_export` | Экспортировать все ассеты Superset (ZIP) |
| `superset_assets_import` | Импортировать ассеты из ZIP |

### Аудит (1 инструмент)

| Инструмент | Описание |
|------------|----------|
| `superset_permissions_audit` | Генерация матрицы прав доступа |

## Механизмы защиты

Сервер включает обширную встроенную защиту от случайной потери данных.

### Флаги подтверждения

Деструктивные операции требуют явного подтверждения:

| Операция | Требуемый флаг | Что показывает |
|----------|---------------|----------------|
| Удаление дашборда | `confirm_delete=True` | Название, slug, количество графиков |
| Удаление графика | `confirm_delete=True` | Привязанные дашборды |
| Удаление датасета | `confirm_delete=True` | Затронутые графики и дашборды |
| Удаление БД | `confirm_delete=True` | Затронутые датасеты, графики |
| Удаление RLS | `confirm_delete=True` | Clause, роли, датасеты |
| Удаление роли | `confirm_delete=True` | Блокирует системные роли |
| Удаление пользователя | `confirm_delete=True` | Блокирует удаление сервисного аккаунта |
| Обновление params графика | `confirm_params_replace=True` | — |
| Обновление columns датасета | `confirm_columns_replace=True` | — |
| Изменение URI БД | `confirm_uri_change=True` | Затронутые графики/дашборды |
| Обновление ролей пользователя | `confirm_roles_replace=True` | Текущие роли |
| Установка прав роли | `confirm_full_replace=True` | — |
| Выдача доступа к дашборду | `confirm_grant=True` | Результат dry-run |
| Отзыв доступа к дашборду | `confirm_revoke=True` | Результат dry-run |

### Автоматическая защита

- **Блокировка DDL/DML** — SQL Lab отклоняет `DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`
- **Защита системных ролей** — нельзя удалить Admin, Alpha, Gamma, Public
- **Защита сервисного аккаунта** — нельзя удалить MCP-пользователя
- **Безопасность RLS** — `rls_update` требует одновременно `roles` и `tables`
- **ID нативных фильтров** — автоматически генерируются в формате `NATIVE_FILTER-<uuid>`
- **Валидация графиков** — отклоняет графики без `granularity_sqla`
- **Авто-синхронизация** — права `datasource_access` автоматически синхронизируются при изменении ролей дашборда

## Архитектура

```
superset-mcp/
├── pyproject.toml              # Конфигурация пакета
├── .env.example                # Шаблон переменных окружения
├── LICENSE                     # Лицензия MIT
├── README.md                   # Документация (English)
├── README_RU.md                # Документация (Русский)
├── CHANGELOG.md                # История версий
└── src/superset_mcp/
    ├── __init__.py             # Инициализация с __version__
    ├── __main__.py             # CLI с argparse
    ├── server.py               # Настройка FastMCP-сервера
    ├── auth.py                 # JWT-аутентификация (login, refresh, CSRF)
    ├── client.py               # HTTP-клиент (авто-аутентификация, retry, RISON-пагинация)
    ├── models.py               # Pydantic-модели
    └── tools/
        ├── __init__.py         # register_all_tools()
        ├── helpers.py          # Авто-синхронизация datasource_access
        ├── dashboards.py       # Инструменты дашбордов + фильтров (20)
        ├── charts.py           # Инструменты графиков (11)
        ├── databases.py        # Инструменты БД (18)
        ├── datasets.py         # Инструменты датасетов (11)
        ├── queries.py          # SQL Lab + сохранённые запросы (13)
        ├── security.py         # Пользователи, роли, права, RLS (22)
        ├── groups.py           # Управление группами (9)
        ├── audit.py            # Аудит прав (1)
        ├── tags.py             # Инструменты тегов (7)
        └── system.py           # Отчёты, аннотации, логи, ассеты (21)
```

## Совместимость с Superset

- **Протестировано с**: Apache Superset 4.x, 5.x, 6.0.1
- **Аутентификация**: JWT (рекомендуется) — API Key (`sst_*`) не реализован в Superset
- **Требуемый пользователь**: роль Admin (для полного доступа к API)

### Рекомендуемая настройка Superset

Добавьте в `superset_config.py`:

```python
from datetime import timedelta

# Увеличить время жизни JWT-токена (по умолчанию 15 мин)
JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

# Максимальный размер страницы API
FAB_API_MAX_PAGE_SIZE = 100
```

## Разработка

### Настройка окружения

```bash
git clone https://github.com/bintocher/superset-mcp.git
cd superset-mcp

# Создать виртуальное окружение и установить в режиме разработки
uv venv
uv pip install -e ".[dev]"

# Скопировать и настроить .env
cp .env.example .env
# Отредактируйте .env с вашими данными Superset
```

### Локальный запуск

```bash
# Запуск из исходников
uv run python -m superset_mcp

# Или через CLI
uv run superset-mcp --port 8001
```

### Запуск тестов

```bash
uv run python test_all_tools.py
```

## Лицензия

[MIT](LICENSE) — Stanislav Chernov ([@bintocher](https://github.com/bintocher))
