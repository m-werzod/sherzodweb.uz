"""
Cross-platform launcher for the agents service.

On Windows the default ProactorEventLoop is incompatible with psycopg's
async driver (it relies on add_reader/add_writer, which ProactorEventLoop
omits). On Python 3.14+ the old `set_event_loop_policy` route is a no-op
warning, so we wire up a SelectorEventLoop explicitly via `Runner` and
hand it to uvicorn manually.

Run with:  uv run python run.py
"""
from __future__ import annotations

import asyncio
import os
import selectors
import sys


def _loop_factory():
    """Always returns a SelectorEventLoop. Identity on POSIX (where SELECT
    isn't the default, asyncio still happily accepts SelectorEventLoop)."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop(selectors.SelectSelector())
    return asyncio.new_event_loop()


def main() -> None:
    import uvicorn  # imported lazily so any asyncio import inside doesn't lock the policy

    config = uvicorn.Config(
        "app.main:app",
        host=os.getenv("AGENTS_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENTS_PORT", "8000")),
        reload=os.getenv("AGENTS_RELOAD", "0") == "1",
        log_level=os.getenv("AGENTS_LOG_LEVEL", "info"),
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    # Build the loop ourselves so we control which factory runs.
    with asyncio.Runner(loop_factory=_loop_factory) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
