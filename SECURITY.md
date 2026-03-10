# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | Yes       |
| < 0.2   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Email** [bintocher@gmail.com](mailto:bintocher@gmail.com) with the following details:
   - Description of the vulnerability
   - Steps to reproduce
   - Impact assessment (what an attacker could achieve)
2. **Do NOT** open a public GitHub issue for security vulnerabilities.
3. You can expect an initial response within **48 hours**.
4. We will work with you to understand the issue and coordinate a fix before any public disclosure.

## Security Considerations

**Credential handling.** The MCP server authenticates to Apache Superset using JWT tokens. Always store credentials in `.env` files and never commit them to version control. The `.env` file is listed in `.gitignore` by default.

**Built-in safety mechanisms.** The server includes several protections against accidental or malicious operations:

- DDL/DML blocking in SQL Lab (DROP, DELETE, UPDATE, INSERT, TRUNCATE, ALTER, CREATE, GRANT, REVOKE)
- SQL comment stripping before validation to prevent bypass via `--` or `/* */`
- Confirmation flags (`confirm_delete`, `confirm_overwrite`, etc.) required for all destructive operations
- Blocked deletion of system roles and the active service account

**Network binding.** In production, run the MCP server on localhost only (default: `127.0.0.1:8001`). Do not expose the server to external networks, as it provides full administrative access to your Superset instance.
