"""Базовые типы данных, общие для всех модулей.

``Artifact`` — единица вывода, развязывающая «какой объект какой SQL порождает»
(экстракторы) от «как это пишется в файлы» (writer). ``Context`` — то, что
получает каждый экстрактор: связанная схема и SQL-диалект соединения.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from firebird.lib.schema import Schema


@dataclass(frozen=True)
class Artifact:
    """Одна SQL-инструкция, адресованная конкретному файлу вывода."""

    path: str   # относительный путь, напр. "04_TABLES/ACCOUNT.sql"
    sql: str    # одна инструкция без терминатора
    psql: bool = False  # True -> обернуть в SET TERM ^ ; ... ^


@dataclass(frozen=True)
class Context:
    """Вход экстрактора: связанная схема + диалект соединения."""

    schema: "Schema"
    dialect: int


# Нумерованное дерево категорий. Создаётся целиком (даже пустые директории),
# чтобы структура была предсказуемой.
SUBDIRS = (
    "01_EXTERNAL_FUNCTIONS",
    "02_GENERATORS",
    "03_DOMAINS",
    "04_TABLES",
    "05_VIEWS",
    "06_EXCEPTIONS",
    "07_FUNCTIONS",
    "08_PROCEDURES",
    "09_PACKAGES",
    "10_TRIGGERS",
    "11_ROLES",
    "12_GRANTS",
    "13_COMMENTS",
)
