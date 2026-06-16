"""Резолв имён объектов в точечном режиме.

Чистый модуль (без ФС): по списку имён и опциональному типу находит объекты
схемы. Имена в Firebird нормализуются в верхний регистр (кроме идентификаторов
в кавычках), поэтому сопоставление регистронезависимое. Без `--type` имя,
совпавшее в нескольких категориях, даёт несколько совпадений — это намеренно.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from firebird.lib.schema import (
    DatabaseException,
    Domain,
    Function,
    Index,
    Procedure,
    Role,
    Schema,
    Sequence,
    Table,
    TableColumn,
    Trigger,
    View,
    ViewColumn,
)

from . import log
from .categories import (
    CATEGORY_BY_ALIAS,
    CATEGORY_BY_KEY,
    CATEGORY_ORDER,
    SELECTABLE,
    Category,
    _is_sys,
)


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


def _category_of(obj: Any) -> tuple[Category, Any] | None:
    """Сопоставляет объект-зависимость (из Dependency.depended_on) с
    (Category, object). Колонка разворачивается в свою таблицу/представление.
    Системные, пакетные и непокрываемые объекты → None.

    Маппинг по классу объекта (а не по коду RDB$OBJECT_TYPE) важен для функций:
    и UDF, и PSQL-функции имеют один код типа 15, но это разные категории —
    различаем через is_external().
    """
    if isinstance(obj, TableColumn):
        obj = obj.table
    elif isinstance(obj, ViewColumn):
        obj = obj.view
    if obj is None or _is_sys(obj):
        return None

    if isinstance(obj, View):
        key = "view"
    elif isinstance(obj, Table):
        key = "table"
    elif isinstance(obj, Function):
        if obj.is_packaged():
            return None
        key = "external_function" if obj.is_external() else "function"
    elif isinstance(obj, Procedure):
        if obj.is_packaged():
            return None
        key = "procedure"
    elif isinstance(obj, Trigger):
        key = "trigger"
    elif isinstance(obj, Sequence):
        key = "generator"
    elif isinstance(obj, Domain):
        key = "domain"
    elif isinstance(obj, DatabaseException):
        key = "exception"
    elif isinstance(obj, Index):
        key = "index"
    elif isinstance(obj, Role):
        key = "role"
    else:
        return None

    cat = CATEGORY_BY_KEY.get(key)
    return (cat, obj) if cat is not None else None


def _domain_refs(obj: Any) -> list[Any]:
    """Домены, на которые ссылаются столбцы таблицы/представления или параметры
    процедуры/функции. Эту связь Firebird НЕ пишет в RDB$DEPENDENCIES, поэтому
    собираем её отдельно — иначе домены типов столбцов теряются. Системные
    (RDB$-генерированные для inline-типов) отсеются позже по is_sys_object."""
    items: list[Any] = []
    try:
        if isinstance(obj, (Table, View)):
            items = list(obj.columns)
        elif isinstance(obj, Procedure):
            items = list(obj.input_params) + list(obj.output_params)
        elif isinstance(obj, Function):
            items = list(obj.arguments)
    except Exception:  # noqa: BLE001
        return []
    domains = []
    for it in items:
        d = getattr(it, "domain", None)
        if d is not None:
            domains.append(d)
    return domains


def _depended_objects(obj: Any) -> list[Any]:
    """Все объекты, от которых зависит `obj`: явные из RDB$DEPENDENCIES плюс
    домены столбцов/параметров (которых там нет)."""
    targets: list[Any] = []
    try:
        for dep in obj.get_dependencies():
            try:
                if (t := dep.depended_on) is not None:
                    targets.append(t)
            except Exception:  # noqa: BLE001 — отдельная зависимость может не резолвиться
                continue
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Не удалось прочитать зависимости {getattr(obj, 'name', '?')}: {exc}")
    targets.extend(_domain_refs(obj))
    return targets


def expand_deps(schema: Schema, seeds: list[tuple[Category, Any]]) -> list[tuple[Category, Any]]:
    """Транзитивно собирает объекты, от которых зависят `seeds`, чтобы выгруженный
    набор был самодостаточным. Источники зависимостей: RDB$DEPENDENCIES
    (`SchemaItem.get_dependencies()`) плюс домены столбцов/параметров (их Firebird
    в RDB$DEPENDENCIES не фиксирует). Возвращает только дополнительные объекты
    (без самих seeds), в порядке CATEGORIES; защита от циклов — множество посещённых.
    """
    seen: set[tuple[str, str]] = {(c.key, c.name_of(o)) for c, o in seeds}
    extra: dict[tuple[str, str], tuple[Category, Any]] = {}

    queue: list[tuple[Category, Any]] = list(seeds)
    i = 0
    while i < len(queue):
        _, obj = queue[i]
        i += 1
        for target in _depended_objects(obj):
            mapped = _category_of(target)
            if mapped is None:
                continue
            mcat, mobj = mapped
            key = (mcat.key, mcat.name_of(mobj))
            if key in seen:
                continue
            seen.add(key)
            extra[key] = mapped
            queue.append(mapped)  # транзитивно

    result = list(extra.values())
    result.sort(key=lambda cm: (CATEGORY_ORDER.get(cm[0].key, 999), cm[0].name_of(cm[1])))
    return result
