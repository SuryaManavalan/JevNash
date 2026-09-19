"""Event bus. Everything the harness does is emitted here; the dashboard is just a subscriber."""

from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path
from typing import Any


class Bus:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.subscribers: list[queue.Queue] = []
        self.backlog: list[str] = []
        self.file = None
        self.shot: bytes | None = None  # latest browser frame, served at /shot.jpg

    def open(self, run_dir: Path) -> None:
        self.file = (run_dir / "events.jsonl").open("a")

    def emit(self, type: str, **data: Any) -> None:
        line = json.dumps({"type": type, "t": time.time(), **data}, default=str)
        with self.lock:
            self.backlog = (self.backlog + [line])[-400:]
            if self.file:
                self.file.write(line + "\n")
                self.file.flush()
            for q in self.subscribers:
                q.put(line)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            for line in self.backlog:
                q.put(line)
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)


bus = Bus()
