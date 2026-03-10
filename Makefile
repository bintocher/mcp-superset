.PHONY: run

run:
	@lsof -ti tcp:8001 2>/dev/null | xargs kill -9 2>/dev/null; sleep 0.3; uv run python -m superset_mcp
