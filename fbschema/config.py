"""Загрузка и валидация конфигурации из .env-файла."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

REQUIRED_VARS = ("ISC_USER", "ISC_PASSWORD", "FB_DATABASE", "DUMP_DIR")

_FALSEY = {"0", "false", "no", "off", "none", ""}


class ConfigError(Exception):
    """Некорректная или неполная конфигурация."""


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in _FALSEY


@dataclass(frozen=True)
class Config:
    user: str
    password: str
    database: str
    dump_dir: Path
    timeout: int
    charset: str       # кодировка соединения (DB_CHARSET; для legacy-баз, напр. WIN1251)
    audit_log: bool    # писать ли audit_YYYYMMDD.log (AUDIT_LOG; по умолчанию да)
    source: Path       # путь к использованному .env (для логов)


def load(path: str, base_dir: Path) -> Config:
    """Читает .env по пути `path` (относительный — от `base_dir`), валидирует
    обязательные переменные и приводит пути к абсолютным."""
    cfg_path = Path(path)
    if not cfg_path.is_absolute():
        cfg_path = base_dir / cfg_path
    if not cfg_path.is_file():
        raise ConfigError(f"Файл конфигурации {cfg_path} не найден")

    values = {k: v for k, v in dotenv_values(cfg_path).items() if v is not None}

    missing = [v for v in REQUIRED_VARS if not values.get(v)]
    if missing:
        raise ConfigError(
            f"В {cfg_path} не определены переменные: {', '.join(missing)}"
        )

    dump_dir = Path(values["DUMP_DIR"])
    if not dump_dir.is_absolute():
        dump_dir = base_dir / dump_dir

    try:
        timeout = int(values.get("ISQL_TIMEOUT", "0") or "0")
    except ValueError as exc:
        raise ConfigError("ISQL_TIMEOUT должно быть целым числом") from exc

    return Config(
        user=values["ISC_USER"],
        password=values["ISC_PASSWORD"],
        database=values["FB_DATABASE"],
        dump_dir=dump_dir,
        timeout=timeout,
        charset=values.get("DB_CHARSET", "UTF8") or "UTF8",
        audit_log=_as_bool(values.get("AUDIT_LOG"), default=True),
        source=cfg_path,
    )
