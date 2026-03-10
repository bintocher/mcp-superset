"""Pydantic-модели для параметров и ответов MCP-инструментов."""

from pydantic import BaseModel, Field


# === Общие модели для фильтрации и пагинации ===

class ListParams(BaseModel):
    """Параметры пагинации и фильтрации для list-эндпоинтов."""
    page: int = Field(default=0, description="Номер страницы (начиная с 0)")
    page_size: int = Field(default=25, description="Размер страницы (макс. 100)")
    q: str | None = Field(default=None, description="JSON-фильтр в формате Superset RISON")


# === Dashboard ===

class DashboardCreate(BaseModel):
    dashboard_title: str = Field(description="Название дашборда")
    slug: str | None = Field(default=None, description="URL-slug")
    published: bool = Field(default=False, description="Опубликован ли дашборд")
    json_metadata: str | None = Field(default=None, description="JSON-метаданные")
    css: str | None = Field(default=None, description="Пользовательский CSS")
    position_json: str | None = Field(default=None, description="JSON-позиционирование виджетов")


class DashboardUpdate(BaseModel):
    dashboard_title: str | None = Field(default=None, description="Название дашборда")
    slug: str | None = Field(default=None, description="URL-slug")
    published: bool | None = Field(default=None, description="Опубликован ли дашборд")
    json_metadata: str | None = Field(default=None, description="JSON-метаданные")
    css: str | None = Field(default=None, description="Пользовательский CSS")


# === Chart ===

class ChartCreate(BaseModel):
    slice_name: str = Field(description="Название графика")
    viz_type: str = Field(description="Тип визуализации (table, bar, line, pie и т.д.)")
    datasource_id: int = Field(description="ID датасета")
    datasource_type: str = Field(default="table", description="Тип источника данных")
    params: str | None = Field(default=None, description="JSON-параметры визуализации")
    query_context: str | None = Field(default=None, description="JSON query context")
    dashboards: list[int] | None = Field(default=None, description="ID дашбордов для привязки")


class ChartUpdate(BaseModel):
    slice_name: str | None = Field(default=None, description="Название графика")
    viz_type: str | None = Field(default=None, description="Тип визуализации")
    params: str | None = Field(default=None, description="JSON-параметры визуализации")
    query_context: str | None = Field(default=None, description="JSON query context")
    dashboards: list[int] | None = Field(default=None, description="ID дашбордов для привязки")


# === Database ===

class DatabaseCreate(BaseModel):
    database_name: str = Field(description="Название подключения")
    sqlalchemy_uri: str = Field(description="SQLAlchemy URI строка подключения")
    expose_in_sqllab: bool = Field(default=True, description="Доступна ли в SQL Lab")
    allow_ctas: bool = Field(default=False, description="Разрешить CREATE TABLE AS")
    allow_cvas: bool = Field(default=False, description="Разрешить CREATE VIEW AS")
    allow_dml: bool = Field(default=False, description="Разрешить DML-операции")
    allow_run_async: bool = Field(default=False, description="Разрешить асинхронные запросы")
    extra: str | None = Field(default=None, description="JSON дополнительных настроек")


class DatabaseUpdate(BaseModel):
    database_name: str | None = Field(default=None, description="Название подключения")
    sqlalchemy_uri: str | None = Field(default=None, description="SQLAlchemy URI")
    expose_in_sqllab: bool | None = Field(default=None, description="Доступна ли в SQL Lab")
    allow_ctas: bool | None = Field(default=None, description="Разрешить CREATE TABLE AS")
    allow_cvas: bool | None = Field(default=None, description="Разрешить CREATE VIEW AS")
    allow_dml: bool | None = Field(default=None, description="Разрешить DML-операции")
    extra: str | None = Field(default=None, description="JSON дополнительных настроек")


# === Dataset ===

class DatasetCreate(BaseModel):
    table_name: str = Field(description="Название таблицы/вью")
    database: int = Field(description="ID подключения к БД")
    schema_name: str | None = Field(default=None, description="Схема (если не default)")
    sql: str | None = Field(default=None, description="SQL-запрос для виртуального датасета")


class DatasetUpdate(BaseModel):
    table_name: str | None = Field(default=None, description="Название таблицы/вью")
    sql: str | None = Field(default=None, description="SQL-запрос для виртуального датасета")
    description: str | None = Field(default=None, description="Описание датасета")
    columns: list[dict] | None = Field(default=None, description="Колонки датасета")
    metrics: list[dict] | None = Field(default=None, description="Метрики датасета")


# === SQL Lab ===

class SQLQuery(BaseModel):
    database_id: int = Field(description="ID подключения к БД")
    sql: str = Field(description="SQL-запрос")
    schema: str | None = Field(default=None, description="Схема для выполнения")
    catalog: str | None = Field(default=None, description="Каталог для выполнения")
    tab_name: str | None = Field(default=None, description="Название вкладки в SQL Lab")
    template_params: str | None = Field(default=None, description="JSON-параметры шаблона Jinja")


class SavedQueryCreate(BaseModel):
    label: str = Field(description="Название сохранённого запроса")
    db_id: int = Field(description="ID подключения к БД")
    sql: str = Field(description="SQL-запрос")
    schema: str | None = Field(default=None, description="Схема")
    description: str | None = Field(default=None, description="Описание")


# === Security ===

class UserCreate(BaseModel):
    first_name: str = Field(description="Имя")
    last_name: str = Field(description="Фамилия")
    username: str = Field(description="Логин")
    email: str = Field(description="Email")
    password: str = Field(description="Пароль")
    roles: list[int] | None = Field(default=None, description="ID ролей")
    active: bool = Field(default=True, description="Активен ли пользователь")


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, description="Имя")
    last_name: str | None = Field(default=None, description="Фамилия")
    email: str | None = Field(default=None, description="Email")
    roles: list[int] | None = Field(default=None, description="ID ролей")
    active: bool | None = Field(default=None, description="Активен ли пользователь")


class RoleCreate(BaseModel):
    name: str = Field(description="Название роли")


class RoleUpdate(BaseModel):
    name: str = Field(description="Новое название роли")


class RLSRuleCreate(BaseModel):
    name: str = Field(description="Название правила RLS")
    filter_type: str = Field(default="Regular", description="Тип фильтра: Regular или Base")
    clause: str = Field(description="SQL-условие (WHERE clause)")
    tables: list[int] = Field(description="ID датасетов для применения")
    roles: list[int] = Field(description="ID ролей для применения")
    group_key: str | None = Field(default=None, description="Ключ группировки")
    description: str | None = Field(default=None, description="Описание правила")


class RLSRuleUpdate(BaseModel):
    name: str | None = Field(default=None, description="Название правила RLS")
    filter_type: str | None = Field(default=None, description="Тип фильтра")
    clause: str | None = Field(default=None, description="SQL-условие")
    tables: list[int] | None = Field(default=None, description="ID датасетов")
    roles: list[int] | None = Field(default=None, description="ID ролей")
    group_key: str | None = Field(default=None, description="Ключ группировки")
    description: str | None = Field(default=None, description="Описание")


# === Reports ===

class ReportCreate(BaseModel):
    name: str = Field(description="Название отчёта/алерта")
    type: str = Field(default="Report", description="Тип: Report или Alert")
    crontab: str = Field(description="Cron-расписание (напр. '0 9 * * *')")
    dashboard: int | None = Field(default=None, description="ID дашборда")
    chart: int | None = Field(default=None, description="ID графика")
    database: int | None = Field(default=None, description="ID БД (для Alert)")
    sql: str | None = Field(default=None, description="SQL-запрос (для Alert)")
    recipients: list[dict] | None = Field(default=None, description="Получатели")
    active: bool = Field(default=True, description="Активен ли")


class ReportUpdate(BaseModel):
    name: str | None = Field(default=None, description="Название")
    crontab: str | None = Field(default=None, description="Cron-расписание")
    active: bool | None = Field(default=None, description="Активен ли")
    recipients: list[dict] | None = Field(default=None, description="Получатели")
