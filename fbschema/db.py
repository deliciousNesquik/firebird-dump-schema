"""Подключение к Firebird и политика транзакций.

Единственное место, где живёт обязательное правило инфраструктуры:
любая транзакция должна быть read-committed + record-version + NO WAIT —
режим WAIT может «подвесить» процесс на конфликте блокировок.

Schema из firebird-lib читает метаданные в собственной внутренней транзакции,
создаваемой в Schema.bind() как:
    tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=READ)
что использует дефолт драйвера lock_timeout=-1 (== isc_tpb_wait). Оборачиваем
символ `tpb`, который резолвит модуль schema, чтобы эта транзакция всегда
строилась с lock_timeout=0 (== isc_tpb_nowait), сохраняя isolation и режим
доступа.
"""

from __future__ import annotations

import firebird.lib.schema as _fb_schema
from firebird.driver import TraAccessMode, connect
from firebird.driver import tpb as _driver_tpb

from .config import Config


def _nowait_tpb(isolation, lock_timeout: int = -1, access_mode=TraAccessMode.WRITE) -> bytes:  # noqa: ANN001
    return _driver_tpb(isolation, lock_timeout=0, access_mode=access_mode)


_fb_schema.tpb = _nowait_tpb


def open_connection(cfg: Config):  # noqa: ANN201
    return connect(cfg.database, user=cfg.user, password=cfg.password, charset=cfg.charset)


def dialect(con) -> int:  # noqa: ANN001
    try:
        return int(getattr(con.info, "sql_dialect", 3))
    except Exception:  # noqa: BLE001
        return 3
