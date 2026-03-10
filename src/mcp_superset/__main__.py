"""Entry point: python -m mcp_superset or `mcp-superset` CLI."""

import argparse
import os

import uvicorn.config

# Override default uvicorn log config BEFORE importing FastMCP
_date_format = "%Y-%m-%d %H:%M:%S"
_log_format = "%(asctime)s.%(msecs)03d %(levelname)-5s %(message)s"

uvicorn.config.LOGGING_CONFIG["formatters"]["default"] = {
    "format": _log_format,
    "datefmt": _date_format,
}
uvicorn.config.LOGGING_CONFIG["formatters"]["access"] = {
    "()": "uvicorn.logging.AccessFormatter",
    "fmt": '%(asctime)s.%(msecs)03d INFO  %(client_addr)s - "%(request_line)s" %(status_code)s',
    "datefmt": _date_format,
}


def main():
    """Run the MCP server with CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="mcp-superset",
        description="MCP server for managing Apache Superset",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("SUPERSET_MCP_HOST", "127.0.0.1"),
        help="Host to bind the server (default: 127.0.0.1, env: SUPERSET_MCP_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SUPERSET_MCP_PORT", "8001")),
        help="Port to bind the server (default: 8001, env: SUPERSET_MCP_PORT)",
    )
    parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default=os.getenv("SUPERSET_MCP_TRANSPORT", "streamable-http"),
        help="MCP transport type (default: streamable-http, env: SUPERSET_MCP_TRANSPORT)",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Path to .env file (default: auto-detect from package directory)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.4",
    )

    args = parser.parse_args()

    # Override env file path if specified
    if args.env_file:
        os.environ["SUPERSET_MCP_ENV_FILE"] = args.env_file

    from mcp_superset.server import mcp

    kwargs = {"transport": args.transport}
    if args.transport != "stdio":
        kwargs["host"] = args.host
        kwargs["port"] = args.port
        kwargs["stateless_http"] = True

    mcp.run(**kwargs)


if __name__ == "__main__":
    main()
