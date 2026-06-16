"""Запись артефактов в дерево «один объект — один файл» либо в stdout.

Writer не знает ничего про Firebird: группирует артефакты по целевому пути,
рендерит и пишет. Три режима:
  FULL   — очистить дерево (rmtree + пересоздать SUBDIRS) и записать всё;
  TREE   — без очистки, перезаписать только затронутые файлы (точечный режим);
  STDOUT — отрендерить и напечатать, ФС не трогать.
"""

from __future__ import annotations

import enum
import shutil
import sys
from pathlib import Path
from typing import Iterable, TextIO

from . import log
from .model import SUBDIRS, Artifact
from .render import render


class WriteMode(enum.Enum):
    FULL = "full"
    TREE = "tree"
    STDOUT = "stdout"


def prepare_tree(dump_dir: Path) -> None:
    if dump_dir.exists():
        log.info(f"Удаление прежней выходной директории: {dump_dir}")
        shutil.rmtree(dump_dir)
    log.info("Создание структуры директорий...")
    for sub in SUBDIRS:
        (dump_dir / sub).mkdir(parents=True, exist_ok=True)


def _group(artifacts: Iterable[Artifact]) -> dict[str, dict]:
    # Ключ — относительный путь; порядок вставки сохраняется (детерминизм/stdout).
    grouped: dict[str, dict] = {}
    for art in artifacts:
        if not art.sql or not art.sql.strip():
            continue
        entry = grouped.setdefault(art.path, {"psql": False, "stmts": []})
        entry["psql"] = entry["psql"] or art.psql
        entry["stmts"].append(art.sql.strip())
    return grouped


def write(
    artifacts: Iterable[Artifact],
    dump_dir: Path,
    mode: WriteMode = WriteMode.FULL,
    out: TextIO | None = None,
) -> int:
    grouped = _group(artifacts)

    if mode is WriteMode.STDOUT:
        stream = out or sys.stdout
        for rel, entry in grouped.items():
            print(f"-- ===== {rel} =====", file=stream)
            print(render(entry["stmts"], entry["psql"]), file=stream)
        return len(grouped)

    if mode is WriteMode.FULL:
        prepare_tree(dump_dir)

    for rel, entry in grouped.items():
        path = dump_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(entry["stmts"], entry["psql"]), encoding="utf-8")
    return len(grouped)
