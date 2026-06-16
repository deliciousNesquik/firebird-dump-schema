"""Сборка исполнимого текста .sql-файла из набора инструкций.

firebird-lib возвращает инструкции без терминаторов и без SET TERM, поэтому
добавляем их здесь.
"""

from __future__ import annotations


def fname(name: str) -> str:
    """Безопасное имя файла для объекта. Идентификаторы Firebird обычно
    [A-Z0-9_$], но идентификаторы в кавычках могут содержать что угодно —
    на всякий случай удаляем разделители путей."""
    safe = name.strip().replace("/", "_").replace("\\", "_").replace("\x00", "")
    return f"{safe}.sql"


def render(statements: list[str], psql: bool) -> str:
    """PSQL-объекты (процедуры, функции, триггеры, пакеты) оборачиваются в блок
    SET TERM и завершаются ``^``; всё остальное завершается ``;``."""
    if psql:
        out = ["SET TERM ^ ;", ""]
        for stmt in statements:
            out.append(stmt.rstrip().rstrip("^").rstrip())
            out.append("^")
            out.append("")
        out.append("SET TERM ; ^")
        out.append("")
        return "\n".join(out)
    return "\n".join(f"{s.rstrip().rstrip(';')};" for s in statements) + "\n"
