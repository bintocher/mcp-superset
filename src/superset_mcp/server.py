"""MCP server entry point for Apache Superset."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

from superset_mcp.auth import AuthManager
from superset_mcp.client import SupersetClient
from superset_mcp.tools import register_all_tools

# Load .env — custom path via env var, or auto-detect from package directory
_custom_env = os.environ.get("SUPERSET_MCP_ENV_FILE")
if _custom_env:
    load_dotenv(Path(_custom_env))
else:
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(_env_path)

# Configuration
SUPERSET_BASE_URL = os.getenv("SUPERSET_BASE_URL", "")
SUPERSET_USERNAME = os.getenv("SUPERSET_USERNAME")
SUPERSET_PASSWORD = os.getenv("SUPERSET_PASSWORD")
SUPERSET_AUTH_PROVIDER = os.getenv("SUPERSET_AUTH_PROVIDER", "db")

if not SUPERSET_BASE_URL:
    raise ValueError("SUPERSET_BASE_URL is required. Set it in .env or environment variables.")
if not SUPERSET_USERNAME or not SUPERSET_PASSWORD:
    raise ValueError("SUPERSET_USERNAME and SUPERSET_PASSWORD are required. Set them in .env or environment variables.")

# Initialize client
auth_manager = AuthManager(
    base_url=SUPERSET_BASE_URL,
    username=SUPERSET_USERNAME,
    password=SUPERSET_PASSWORD,
    provider=SUPERSET_AUTH_PROVIDER,
)

superset_client = SupersetClient(auth_manager=auth_manager, base_url=SUPERSET_BASE_URL)

# Create MCP server
mcp = FastMCP(
    name="superset",
    instructions=(
        "MCP server for managing Apache Superset. "
        "Provides tools for dashboards, charts, databases, datasets, "
        "SQL queries, users, roles, permissions, and other Superset resources."
    ),
)

# Register all tools
register_all_tools(mcp)


if __name__ == "__main__":
    host = os.getenv("SUPERSET_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("SUPERSET_MCP_PORT", "8001"))
    mcp.run(transport="streamable-http", host=host, port=port, stateless_http=True)
