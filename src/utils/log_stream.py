"""Pipeline logger that writes to stdout and an optional asyncio queue."""

from __future__ import annotations

import sys
from datetime import datetime
from queue import Queue


class PipelineLogger:
    """Simple logger: timestamps each message, prints to stdout, and optionally
    pushes into a :class:`queue.Queue` (thread-safe, no asyncio dependency)."""

    def __init__(self, queue: Queue[str] | None = None) -> None:
        self._queue = queue

    def log(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        print(line, flush=True)
        if self._queue is not None:
            self._queue.put_nowait(line)

    def done(self, report_dir: str) -> None:
        self.log(f"\u2705 Done! Report saved to {report_dir}")
        if self._queue is not None:
            self._queue.put_nowait(f"__DONE__{report_dir}")

    def error(self, message: str) -> None:
        self.log(f"\u274C Error: {message}")
        if self._queue is not None:
            self._queue.put_nowait(f"__ERROR__{message}")

    def finish(self) -> None:
        """Signal that no more messages will come."""
        if self._queue is not None:
            self._queue.put_nowait("__END__")
