"""Категории объектов схемы.

Каждая категория описывает один вид объектов: как достать коллекцию из схемы
(`objects`) и как превратить один объект в Artifact'ы DDL (`artifacts_for`).
Разделение «обойти коллекцию» и «DDL одного объекта» позволяет переиспользовать
вторую часть и в полном, и в точечном, и в list-режиме.

Порядок секций и действия `get_sql_for` повторяют `get_metadata_ddl` из
firebird-lib, поэтому вывод полон и учитывает зависимости.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Iterator

from firebird.lib.schema import Schema, get_grants

from .model import Artifact, Context
from .render import fname


def _is_sys(obj: Any) -> bool:
    flag = getattr(obj, "is_sys_object", None)
    return bool(flag()) if callable(flag) else False


@dataclass(frozen=True)
class Category:
    """Дескриптор одного вида объектов схемы."""

    key: str                                                     # "table"
    subdir: str                                                  # "04_TABLES"
    aliases: tuple[str, ...]                                      # значения --type
    objects: Callable[[Schema], Iterable[Any]]                   # коллекция (sys+вид отфильтрованы)
    artifacts_for: Callable[[Context, Any], Iterable[Artifact]]  # DDL одного объекта
    name_of: Callable[[Any], str] = field(default=lambda o: o.name)


# --------------------------------------------------------------------------
# objects(): коллекции с фильтрацией системных объектов и расщеплением по виду
# --------------------------------------------------------------------------
def _external_functions(s: Schema) -> Iterator[Any]:
    return (f for f in s.functions if f.is_external() and not _is_sys(f))


def _psql_functions(s: Schema) -> Iterator[Any]:
    return (f for f in s.functions if not f.is_external() and not f.is_packaged() and not _is_sys(f))


def _procedures(s: Schema) -> Iterator[Any]:
    return (p for p in s.procedures if not p.is_packaged() and not _is_sys(p))


def _indices(s: Schema) -> Iterator[Any]:
    return (i for i in s.indices if not i.is_enforcer() and not _is_sys(i))


def _plain(attr: str) -> Callable[[Schema], Iterator[Any]]:
    return lambda s: (o for o in getattr(s, attr) if not _is_sys(o))


# --------------------------------------------------------------------------
# artifacts_for(): DDL одного объекта
# --------------------------------------------------------------------------
def _af_external_function(ctx: Context, f: Any) -> Iterator[Artifact]:
    yield Artifact(f"01_EXTERNAL_FUNCTIONS/{fname(f.name)}", f.get_sql_for("declare"))


def _af_generator(ctx: Context, g: Any) -> Iterator[Artifact]:
    rel = f"02_GENERATORS/{fname(g.name)}"
    yield Artifact(rel, g.get_sql_for("create"))
    try:
        yield Artifact(rel, g.get_sql_for("alter", value=g.value))
    except Exception:  # noqa: BLE001 — текущее значение не всегда читаемо
        pass


def _af_domain(ctx: Context, d: Any) -> Iterator[Artifact]:
    yield Artifact(f"03_DOMAINS/{fname(d.name)}", d.get_sql_for("create"))


def _af_table(ctx: Context, t: Any) -> Iterator[Artifact]:
    rel = f"04_TABLES/{fname(t.name)}"
    yield Artifact(rel, t.get_sql_for("create", no_pk=True, no_unique=True))
    cons = list(t.constraints)
    ordered = (
        [c for c in cons if c.is_pkey()]
        + [c for c in cons if c.is_unique()]
        + [c for c in cons if c.is_check()]
        + [c for c in cons if c.is_fkey()]
    )
    for c in ordered:
        yield Artifact(rel, c.get_sql_for("create"))


def _af_index(ctx: Context, i: Any) -> Iterator[Artifact]:
    yield Artifact(f"04_TABLES/{fname(i.name)}", i.get_sql_for("create"))


def _af_view(ctx: Context, v: Any) -> Iterator[Artifact]:
    yield Artifact(f"05_VIEWS/{fname(v.name)}", v.get_sql_for("create"))


def _af_exception(ctx: Context, e: Any) -> Iterator[Artifact]:
    yield Artifact(f"06_EXCEPTIONS/{fname(e.name)}", e.get_sql_for("create"))


def _af_function(ctx: Context, f: Any) -> Iterator[Artifact]:
    yield Artifact("07_FUNCTIONS/00_DECLARATION.sql", f.get_sql_for("create", no_code=True), psql=True)
    yield Artifact(f"07_FUNCTIONS/{fname(f.name)}", "ALTER" + f.get_sql_for("create")[6:], psql=True)


def _af_procedure(ctx: Context, p: Any) -> Iterator[Artifact]:
    yield Artifact("08_PROCEDURES/00_DECLARATION.sql", p.get_sql_for("create", no_code=True), psql=True)
    yield Artifact(f"08_PROCEDURES/{fname(p.name)}", "ALTER" + p.get_sql_for("create")[6:], psql=True)


def _af_package(ctx: Context, pkg: Any) -> Iterator[Artifact]:
    rel = f"09_PACKAGES/{fname(pkg.name)}"
    yield Artifact(rel, pkg.get_sql_for("create"), psql=True)
    try:
        yield Artifact(rel, pkg.get_sql_for("create", body=True), psql=True)
    except Exception:  # noqa: BLE001 — у пакета может не быть тела
        pass


def _af_trigger(ctx: Context, tr: Any) -> Iterator[Artifact]:
    yield Artifact(f"10_TRIGGERS/{fname(tr.name)}", tr.get_sql_for("create"), psql=True)


def _af_role(ctx: Context, r: Any) -> Iterator[Artifact]:
    yield Artifact("11_ROLES/ROLES.sql", r.get_sql_for("create"))


# --------------------------------------------------------------------------
# Реестр селектируемых категорий (в порядке нумерации subdir)
# --------------------------------------------------------------------------
CATEGORIES: tuple[Category, ...] = (
    Category("external_function", "01_EXTERNAL_FUNCTIONS", ("external-function", "udf"), _external_functions, _af_external_function),
    Category("generator", "02_GENERATORS", ("generator", "sequence"), _plain("generators"), _af_generator),
    Category("domain", "03_DOMAINS", ("domain",), _plain("domains"), _af_domain),
    Category("table", "04_TABLES", ("table",), _plain("tables"), _af_table),
    Category("index", "04_TABLES", ("index",), _indices, _af_index),
    Category("view", "05_VIEWS", ("view",), _plain("views"), _af_view),
    Category("exception", "06_EXCEPTIONS", ("exception",), _plain("exceptions"), _af_exception),
    Category("function", "07_FUNCTIONS", ("function",), _psql_functions, _af_function),
    Category("procedure", "08_PROCEDURES", ("procedure", "proc"), _procedures, _af_procedure),
    Category("package", "09_PACKAGES", ("package",), _plain("packages"), _af_package),
    Category("trigger", "10_TRIGGERS", ("trigger",), _plain("triggers"), _af_trigger),
    Category("role", "11_ROLES", ("role",), _plain("roles"), _af_role),
)

# Все категории селектируемы и листятся. Кросс-секущие grants/comments и
# преамбула DATABASE.sql — не категории (см. ниже), в --type не участвуют.
SELECTABLE: tuple[Category, ...] = CATEGORIES

CATEGORY_BY_ALIAS: dict[str, Category] = {
    alias: cat for cat in CATEGORIES for alias in cat.aliases
}
CATEGORY_BY_KEY: dict[str, Category] = {cat.key: cat for cat in CATEGORIES}
CATEGORY_ORDER: dict[str, int] = {cat.key: i for i, cat in enumerate(CATEGORIES)}
TYPE_CHOICES: tuple[str, ...] = tuple(sorted(CATEGORY_BY_ALIAS))


# --------------------------------------------------------------------------
# Кросс-секущие секции и преамбула — только для полного дампа
# --------------------------------------------------------------------------
def database_preamble(ctx: Context) -> Artifact:
    return Artifact("DATABASE.sql", f"SET SQL DIALECT {ctx.dialect}")


def full_grants(ctx: Context) -> Iterator[Artifact]:
    privs = [
        p
        for p in ctx.schema.privileges
        if p.user_name != "SYSDBA" and not _is_sys(p.subject)
    ]
    for stmt in get_grants(privs):
        yield Artifact("12_GRANTS/GRANTS.sql", stmt)


def full_comments(ctx: Context) -> Iterator[Artifact]:
    schema = ctx.schema
    for coll in (
        schema.exceptions,
        schema.domains,
        schema.generators,
        schema.tables,
        schema.indices,
        schema.views,
        schema.triggers,
        schema.procedures,
        schema.functions,
        schema.roles,
    ):
        for obj in coll:
            if _is_sys(obj):
                continue
            if getattr(obj, "description", None) is not None:
                yield Artifact("13_COMMENTS/COMMENTS.sql", obj.get_sql_for("comment"))
    for t in schema.tables:
        if _is_sys(t):
            continue
        for col in t.columns:
            if getattr(col, "description", None) is not None:
                yield Artifact("13_COMMENTS/COMMENTS.sql", col.get_sql_for("comment"))
