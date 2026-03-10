# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2026-03-11

### Added

- Official MCP Registry support (`server.json`, `mcp-name` verification tag)
- Glama.ai listing: https://glama.ai/mcp/servers/bintocher/mcp-superset
- Smithery configuration (`smithery.yaml`)
- Promotion materials (`PROMOTION.md`)

## [0.2.2] - 2025-03-11

### Changed

- Updated GitHub Actions to latest versions via Dependabot:
  - `actions/upload-artifact` v6 → v7
  - `actions/download-artifact` v6 → v8
  - `github/codeql-action` v3 → v4

## [0.2.1] - 2025-03-11

### Added

- Health check endpoint: `GET /health` returns server status, version, and Superset URL (no auth required)
- PEP 561 `py.typed` marker for typed package support
- CONTRIBUTING.md with development setup and contribution guidelines
- SECURITY.md with responsible disclosure policy
- GitHub issue templates (bug report, feature request) and PR template
- Dependabot configuration for automated dependency updates (pip + GitHub Actions)
- Pre-commit hooks configuration (ruff, trailing whitespace, YAML check)
- CodeQL security scanning workflow

### Changed

- All comments, docstrings, and error messages translated to English
- Google-style docstrings added to all public functions and methods

## [0.2.0] - 2025-03-11

### Changed

- Renamed Python package from `superset_mcp` to `mcp_superset` for consistency with PyPI name `mcp-superset`
- Import is now `import mcp_superset` (was `import superset_mcp`)
- CLI entry point: `python -m mcp_superset` (was `python -m superset_mcp`)

## [0.1.0] - 2025-03-10

### Added

- Initial release
- 128+ MCP tools covering complete Apache Superset 6.0.1 REST API
- Dashboard management: CRUD, copy, publish/unpublish, export/import, embedded mode
- Chart management: CRUD, copy, data retrieval, export/import, cache warmup
- Database management: CRUD, connection testing, schema/table introspection
- Dataset management: CRUD, duplicate, schema refresh, export/import
- SQL Lab: query execution, formatting, results retrieval, cost estimation
- Saved queries: full CRUD
- Security: user/role management, permissions, RLS (Row Level Security)
- Group management with role/user assignment
- Dashboard native filters: add, update, delete, reset
- Tag management with object binding
- Report scheduling and annotation layers
- Asset export/import (full instance backup/restore)
- Audit tool: comprehensive permissions matrix
- JWT authentication with automatic token refresh
- CSRF token handling for state-changing operations
- Built-in safety validations and confirmation flags for destructive operations
- Automatic datasource_access synchronization
- DDL/DML blocking in SQL Lab
- Streamable HTTP transport (stateless mode)
- CLI with configurable host/port
- Environment variable and `.env` file configuration
