"""Сторож таймаута на чтение метаданных — защита от бесконечного зависания.

Значение <= 0 отключает его. SIGALRM есть только на POSIX; на других
платформах — заглушка.
"""

from __future__ import annotations

import signal
from contextlib import contextmanager
from typing import Iterator

from . import log


@contextmanager
def limit(seconds: int) -> Iterator[None]:
    if seconds <= 0 or not hasattr(signal, "SIGALRM"):
        if seconds <= 0:
            log.debug("Таймаут отключён (ISQL_TIMEOUT <= 0).")
        yield
        return

    def _handler(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"Выгрузка схемы превысила таймаут {seconds} с")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
