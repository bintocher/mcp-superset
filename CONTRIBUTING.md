# Contributing to mcp-superset

Thank you for your interest in contributing to mcp-superset! This project provides an MCP (Model Context Protocol) server for managing Apache Superset instances through AI assistants. Contributions of all kinds are welcome -- bug reports, feature requests, documentation improvements, and code changes.

## Development Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/bintocher/mcp-superset.git
   cd mcp-superset
   ```

2. **Create a virtual environment and install dependencies:**

   ```bash
   uv venv
   uv pip install -e ".[dev]"
   ```

3. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` with your Superset instance credentials:

   ```env
   SUPERSET_BASE_URL=http://localhost:8088
   SUPERSET_USERNAME=admin
   SUPERSET_PASSWORD=admin
   SUPERSET_AUTH_PROVIDER=db
   ```

## Running Locally

Start the MCP server using either of these methods:

```bash
# Using the installed entry point
uv run mcp-superset

# Using the module directly
uv run python -m mcp_superset
```

The server starts on `http://localhost:8001/mcp` (Streamable HTTP transport via FastMCP).

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting with the following configuration:

- Line length: 120
- Target: Python 3.12
- Lint rules: `E`, `F`, `I`, `UP`

Run checks before submitting changes:

```bash
# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# Type checking (optional but appreciated)
uv run mypy src/
```

## Adding New Tools

Tools are organized by domain in `src/mcp_superset/tools/`. Each module follows the same pattern:

1. **Choose the appropriate module** (or create a new one if the domain is distinct):
   - `dashboards.py` -- dashboard operations
   - `charts.py` -- chart operations
   - `databases.py` -- database connections
   - `datasets.py` -- dataset management
   - `queries.py` -- SQL Lab and saved queries
   - `security.py` -- users, roles, permissions, RLS
   - `groups.py` -- group management
   - `tags.py` -- tag operations
   - `audit.py` -- audit and access matrix
   - `system.py` -- reports, annotations, logs, assets

2. **Define your tool function** inside the `register_*_tools(mcp)` function, using the `@mcp.tool` decorator:

   ```python
   def register_example_tools(mcp):
       from mcp_superset.server import superset_client as client

       @mcp.tool
       async def superset_example_action(
           id: int,
           name: str | None = None,
       ) -> str:
           """Short description of what this tool does.

           Longer explanation if needed, including important caveats
           or Superset API quirks.

           Args:
               id: The resource ID.
               name: Optional name filter.
           """
           result = await client.get(f"/api/v1/example/{id}")
           return json.dumps(result, ensure_ascii=False)
   ```

3. **Register the module** in `src/mcp_superset/tools/__init__.py` by importing and calling your `register_*_tools` function inside `register_all_tools()`.

4. **Follow existing conventions:**
   - Prefix all tool function names with `superset_`.
   - Use type annotations for all parameters.
   - Write comprehensive docstrings (they become tool descriptions for AI assistants).
   - Add safety guards (`confirm_delete`, `confirm_*`) for destructive operations.
   - Return JSON strings via `json.dumps(result, ensure_ascii=False)`.

## Pull Request Process

1. **Fork the repository** and create a feature branch from `main`:

   ```bash
   git checkout -b feat/add-new-tool
   ```

2. **Use conventional commit messages:**
   - `feat: add chart annotation tool`
   - `fix: handle empty RISON response in dataset list`
   - `docs: update tool count in README`
   - `refactor: extract pagination logic to helper`

3. **Ensure all checks pass:**

   ```bash
   uv run ruff check src/
   uv run ruff format --check src/
   ```

4. **Open a pull request** with a clear description:
   - What the change does and why.
   - Any Superset API quirks encountered.
   - How you tested the change (Superset version, scenario).

5. **Keep PRs focused** -- one feature or fix per pull request.

## Reporting Issues

Use [GitHub Issues](https://github.com/bintocher/mcp-superset/issues) to report bugs or request features. Please include:

- **Superset version** (e.g., 4.1.1, 6.0.1)
- **Python version** (3.12+)
- **mcp-superset version** (`uv pip show mcp-superset`)
- **Steps to reproduce** the issue
- **Expected vs. actual behavior**
- **Error messages or logs** (if applicable)

## Code of Conduct

All participants are expected to treat each other with respect and professionalism. Harassment, discrimination, and disruptive behavior will not be tolerated. Be constructive in code reviews, patient with newcomers, and open to different perspectives.

## License

By contributing to mcp-superset, you agree that your contributions will be licensed under the [MIT License](LICENSE).
