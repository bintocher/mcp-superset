# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
