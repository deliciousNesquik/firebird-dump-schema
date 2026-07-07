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

from typing import Any

import firebird.lib.schema as _fb_schema
from firebird.driver import TraAccessMode, connect, driver_config
from firebird.driver import tpb as _driver_tpb

from . import log
from .config import Config


def _nowait_tpb(isolation, lock_timeout: int = -1, access_mode=TraAccessMode.WRITE) -> bytes:  # noqa: ANN001
    return _driver_tpb(isolation, lock_timeout=0, access_mode=access_mode)


_fb_schema.tpb = _nowait_tpb

# Материализуем метаданные-BLOB'ы целиком (не отдавать потоком BlobReader):
# firebird-lib при сборке DDL конкатенирует исходник как строку, а большой
# (>64 КБ по умолчанию) исходник процедуры/триггера возвращается BlobReader'ом и
# get_sql_for падает «can only concatenate str (not BlobReader)». Порог с запасом.
driver_config.stream_blob_threshold.value = 256 * 1024 * 1024


def open_connection(cfg: Config, charset: str | None = None):  # noqa: ANN201
    return connect(cfg.database, user=cfg.user, password=cfg.password,
                   charset=charset or cfg.charset)


# Коллекции firebird-lib Schema, которые fbschema обходит. У legacy-БД метаданные
# бывают в СМЕШАННЫХ кодировках: часть — сырые WIN1251-байты (читаются только под
# WIN1251), часть — Unicode-символы вне WIN1251 (читаются только под UTF8). Одна
# кодировка соединения обе стороны не покрывает, а firebird-lib грузит коллекцию
# целиком одним запросом — один «плохой» объект рушит всю коллекцию.
_COLLECTIONS = frozenset({
    "collations", "character_sets", "domains", "generators", "exceptions",
    "functions", "procedures", "triggers", "views", "tables", "indices",
    "roles", "packages", "privileges", "dependencies", "constraints",
})


def _fallback_charset(charset: str) -> str:
    """Противоположная кодировка для дочитывания непрочитавшихся коллекций."""
    return "WIN1251" if charset.strip().upper().replace("-", "") == "UTF8" else "UTF8"


class ResilientSchema:
    """Обёртка над firebird-lib Schema: коллекцию, которая не прочиталась на
    основном соединении (Cannot transliterate / UnicodeDecodeError из-за смешанных
    кодировок метаданных), дочитывает через запасное соединение с другой кодировкой.
    Запасное соединение открывается ЛЕНИВО — только если основное реально упало,
    поэтому для нормальных БД поведение не меняется."""

    def __init__(self, primary: Any, fallback_factory, fallback_charset: str) -> None:  # noqa: ANN001
        self._primary = primary
        self._fallback_factory = fallback_factory
        self._fallback_charset = fallback_charset
        self._fallback_con = None
        self._fallback_schema = None
        self._cache: dict[str, list] = {}

    def _fb(self) -> Any:
        if self._fallback_schema is None:
            self._fallback_con = self._fallback_factory()
            self._fallback_schema = self._fallback_con.schema
        return self._fallback_schema

    def _collection(self, name: str) -> list:
        if name in self._cache:
            return self._cache[name]
        try:
            coll = list(getattr(self._primary, name))
        except Exception as exc:  # noqa: BLE001 — транслитерация/декод и пр.
            try:
                coll = list(getattr(self._fb(), name))
            except Exception:  # noqa: BLE001 — запасное тоже не смогло → отдаём исходную ошибку
                raise exc
            log.warning(
                f"Коллекция '{name}' не прочиталась основным соединением "
                f"({type(exc).__name__}: {exc}); прочитана через запасное "
                f"соединение ({self._fallback_charset})"
            )
        self._cache[name] = coll
        return coll

    def __getattr__(self, name: str) -> Any:
        # Вызывается только для отсутствующих на экземпляре атрибутов: коллекции
        # перехватываем и делаем устойчивыми, всё прочее делегируем основной схеме.
        if name in _COLLECTIONS:
            return self._collection(name)
        return getattr(self._primary, name)

    def close_fallback(self) -> None:
        if self._fallback_con is not None:
            try:
                self._fallback_con.close()
            except Exception as exc:  # noqa: BLE001
                log.debug(f"Не удалось закрыть запасное соединение: {exc}")
            self._fallback_con = None
            self._fallback_schema = None


def resilient_schema(cfg: Config, con: Any) -> ResilientSchema:  # noqa: ANN001
    fb = _fallback_charset(cfg.charset)
    return ResilientSchema(con.schema, lambda: open_connection(cfg, fb), fb)


def dialect(con) -> int:  # noqa: ANN001
    try:
        return int(getattr(con.info, "sql_dialect", 3))
    except Exception:  # noqa: BLE001
        return 3
