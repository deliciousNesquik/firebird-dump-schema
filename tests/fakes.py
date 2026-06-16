"""Лёгкие фейки схемы firebird-lib для офлайн-тестов (без БД и libfbclient)."""

from __future__ import annotations

from typing import Any

_COLLECTIONS = (
    "functions", "generators", "domains", "tables", "indices", "views",
    "exceptions", "procedures", "packages", "triggers", "roles", "privileges",
)


class FConstraint:
    def __init__(self, name: str, kind: str) -> None:
        self.name = name
        self.kind = kind  # pkey | unique | check | fkey | not_null

    def is_pkey(self) -> bool: return self.kind == "pkey"
    def is_unique(self) -> bool: return self.kind == "unique"
    def is_check(self) -> bool: return self.kind == "check"
    def is_fkey(self) -> bool: return self.kind == "fkey"
    def is_not_null(self) -> bool: return self.kind == "not_null"

    def get_sql_for(self, action: str, **kw: Any) -> str:
        return f"ALTER TABLE ADD CONSTRAINT {self.name} ({self.kind})"


class FCol:
    def __init__(self, name: str, domain: Any = None, description: str | None = None) -> None:
        self.name = name
        self.domain = domain
        self.description = description

    def get_sql_for(self, action: str, **kw: Any) -> str:
        return f"COMMENT ON COLUMN {self.name} IS '{self.description}'"


class FObj:
    """Универсальный фейк объекта схемы."""

    def __init__(self, name: str, *, sys: bool = False, external: bool = False,
                 packaged: bool = False, enforcer: bool = False,
                 constraints: list[FConstraint] | None = None,
                 columns: list[FCol] | None = None, value: int = 0,
                 description: str | None = None, deps: list["FObj"] | None = None) -> None:
        self.name = name
        self._sys = sys
        self._ext = external
        self._pkg = packaged
        self._enf = enforcer
        self.constraints = constraints or []
        self.columns = columns or []
        self.value = value
        self.description = description
        self._deps = deps or []

    def is_sys_object(self) -> bool: return self._sys
    def is_external(self) -> bool: return self._ext
    def is_packaged(self) -> bool: return self._pkg
    def is_enforcer(self) -> bool: return self._enf

    def get_sql_for(self, action: str, **kw: Any) -> str:
        if action == "declare":
            return f"DECLARE EXTERNAL FUNCTION {self.name} ENTRY_POINT 'x'"
        if action == "comment":
            return f"COMMENT ON {self.name} IS '{self.description}'"
        if action == "alter":
            return f"ALTER SEQUENCE {self.name} RESTART WITH {kw.get('value')}"
        return f"CREATE OBJ {self.name}"

    def get_dependencies(self) -> list["FDep"]:
        return [FDep(d) for d in self._deps]


class FDep:
    def __init__(self, target: FObj) -> None:
        self._t = target

    @property
    def depended_on(self) -> FObj:
        return self._t


class FSchema:
    def __init__(self, **collections: list[Any]) -> None:
        for name in _COLLECTIONS:
            setattr(self, name, collections.get(name, []))
