"""Резолв имён объектов в точечном режиме.

Чистый модуль (без ФС): по списку имён и опциональному типу находит объекты
схемы. Имена в Firebird нормализуются в верхний регистр (кроме идентификаторов
в кавычках), поэтому сопоставление регистронезависимое. Без `--type` имя,
совпавшее в нескольких категориях, даёт несколько совпадений — это намеренно.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from firebird.lib.schema import Schema

from . import log
from .categories import CATEGORY_BY_ALIAS, CATEGORY_ORDER, SELECTABLE, Category


@dataclass(frozen=True)
class Resolved:
    matches: list[tuple[Category, Any]]   # порядок CATEGORIES, дедуп по (key, name)
    missing: list[str]                    # запрошенные имена без совпадений


def resolve(schema: Schema, names: list[str], type_alias: str | None = None) -> Resolved:
    cats = [CATEGORY_BY_ALIAS[type_alias]] if type_alias else list(SELECTABLE)
    # Материализуем коллекции один раз (по одной на категорию-кандидата).
    cat_objects = [(c, list(c.objects(schema))) for c in cats]

    matches: list[tuple[Category, Any]] = []
    missing: list[str] = []
    seen: set[tuple[str, str]] = set()

    for name in names:
        target = name.strip()
        upper = target.upper()
        per_name: list[tuple[Category, Any]] = []
        for cat, objs in cat_objects:
            for obj in objs:
                obj_name = cat.name_of(obj)
                if obj_name == target or obj_name.upper() == upper:
                    key = (cat.key, obj_name)
                    if key not in seen:
                        seen.add(key)
                        per_name.append((cat, obj))
        if not per_name:
            missing.append(name)
        else:
            if len({c.key for c, _ in per_name}) > 1:
                cats_hit = ", ".join(sorted(c.key for c, _ in per_name))
                log.info(f"Имя {target!r} совпало в нескольких категориях: {cats_hit}")
            matches.extend(per_name)

    matches.sort(key=lambda cm: (CATEGORY_ORDER.get(cm[0].key, 999), cm[0].name_of(cm[1])))
    return Resolved(matches=matches, missing=missing)


def expand_deps(schema: Schema, seeds: list[tuple[Category, Any]]) -> list[tuple[Category, Any]]:
    """Seam для --with-deps (пока не реализовано).

    Позже: обход RDB$DEPENDENCIES, карта RDB$OBJECT_TYPE -> Category
    (зависит от версии FB), транзитивное замыкание с защитой от циклов.
    """
    raise NotImplementedError("--with-deps пока не реализован")
