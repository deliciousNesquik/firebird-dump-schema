"""Логирование: формат с отметкой времени, дублирование в персистентный
аудит-лог (audit_YYYYMMDD.log); ошибки — в stderr."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import TextIO

_audit: TextIO | None = None


def configure(base_dir: Path) -> None:
    """Открывает аудит-лог в указанной директории. Вызывать один раз в начале."""
    global _audit
    _audit = open(base_dir / f"audit_{datetime.now():%Y%m%d}.log", "a", encoding="utf-8")


def _emit(level: str, msg: str, stream: TextIO) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {msg}"
    print(line, file=stream, flush=True)
    if _audit is not None:
        _audit.write(line + "\n")
        _audit.flush()


# Диагностические сообщения идут в stderr, чтобы stdout оставался чистыми
# данными (имена в --list, SQL в --stdout) — пригодно для пайпов и редиректа.
def info(msg: str) -> None:
    _emit("INFO", msg, sys.stderr)


def debug(msg: str) -> None:
    _emit("DEBUG", msg, sys.stderr)


def warning(msg: str) -> None:
    _emit("WARNING", msg, sys.stderr)


def error(msg: str) -> None:
    _emit("ERROR", msg, sys.stderr)
