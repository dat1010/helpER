from collections import defaultdict
from threading import Lock
from typing import Dict


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counts = defaultdict(int)

    def inc(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[key] += amount

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counts)
