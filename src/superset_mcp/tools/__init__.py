"""Регистрация всех инструментов MCP-сервера."""

from superset_mcp.tools.audit import register_audit_tools
from superset_mcp.tools.charts import register_chart_tools
from superset_mcp.tools.dashboards import register_dashboard_tools
from superset_mcp.tools.databases import register_database_tools
from superset_mcp.tools.datasets import register_dataset_tools
from superset_mcp.tools.groups import register_group_tools
from superset_mcp.tools.queries import register_query_tools
from superset_mcp.tools.security import register_security_tools
from superset_mcp.tools.system import register_system_tools
from superset_mcp.tools.tags import register_tag_tools


def register_all_tools(mcp):
    """Регистрирует все группы инструментов в MCP-сервере."""
    register_dashboard_tools(mcp)
    register_chart_tools(mcp)
    register_database_tools(mcp)
    register_dataset_tools(mcp)
    register_query_tools(mcp)
    register_security_tools(mcp)
    register_tag_tools(mcp)
    register_system_tools(mcp)
    register_group_tools(mcp)
    register_audit_tools(mcp)
