"""Оркестрация: разбор argv, выбор режима, обработка ошибок верхнего уровня.

Режимы:
  полный   — нет имён и нет --list: очистить дерево и выгрузить всё;
  точечный — есть имена: выгрузить названные объекты (в дерево или --stdout);
  список   — --list: перечислить объекты по категориям.

Коды возврата: 0 — успех; 1 — инфраструктура/конфиг/таймаут;
2 — ошибка аргументов CLI; 3 — частичный прогон (пропуски/не найдено).
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import categories, config, db, log, selection, timeout, writer
from .model import Artifact, Context
from .writer import WriteMode


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fb-dump-schema",
        description="Выгрузка схемы Firebird в дерево «один объект — один файл».",
    )
    p.add_argument("-c", "--config", default=".env", metavar="ENV",
                   help="путь к .env с параметрами подключения (по умолчанию ./.env)")
    p.add_argument("names", nargs="*",
                   help="имена объектов для точечной выгрузки; без них — полный дамп")
    p.add_argument("--type", dest="type", choices=categories.TYPE_CHOICES, metavar="TYPE",
                   help="уточнить тип объекта (для точечного режима или фильтра --list)")
    p.add_argument("--list", action="store_true", dest="list_mode",
                   help="перечислить объекты по категориям и выйти")
    p.add_argument("--stdout", action="store_true", dest="to_stdout",
                   help="в точечном режиме печатать SQL в консоль вместо записи в дерево")
    p.add_argument("--with-deps", action="store_true", dest="with_deps",
                   help="в точечном режиме также выгрузить объекты, от которых зависят названные (RDB$DEPENDENCIES)")
    p.add_argument("--with-generator-values", action="store_true", dest="with_generator_values",
                   help="писать текущие значения генераторов (по умолчанию нет — это runtime-состояние)")
    return p


@dataclass
class Run:
    """Сборщик артефактов с по-объектной устойчивостью: сбой одного объекта
    логируется, пропускается и считается, но не валит весь прогон."""

    artifacts: list[Artifact] = field(default_factory=list)
    skipped: int = 0

    def emit_object(self, ctx: Context, cat: categories.Category, obj: Any) -> None:
        try:
            self.artifacts.extend(cat.artifacts_for(ctx, obj))
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Пропуск {cat.key} {cat.name_of(obj)}: {exc}")
            self.skipped += 1

    def emit_section(self, producer, label: str) -> None:  # noqa: ANN001
        try:
            self.artifacts.extend(producer())
        except Exception as exc:  # noqa: BLE001
            log.warning(f"Пропуск секции {label}: {exc}")
            self.skipped += 1


def run_full(ctx: Context, dump_dir: Path) -> int:
    log.info("Полный дамп схемы...")
    run = Run()
    run.artifacts.append(categories.database_preamble(ctx))
    for cat in categories.SELECTABLE:
        for obj in cat.objects(ctx.schema):
            run.emit_object(ctx, cat, obj)
    run.emit_section(lambda: categories.full_grants(ctx), "12_GRANTS")
    run.emit_section(lambda: categories.full_comments(ctx), "13_COMMENTS")
    count = writer.write(run.artifacts, dump_dir, WriteMode.FULL)
    log.info(f"Готово: файлов {count}, пропущено объектов {run.skipped}")
    return 3 if run.skipped else 0


def run_targeted(ctx: Context, dump_dir: Path, names: list[str],
                 type_alias: str | None, to_stdout: bool, with_deps: bool) -> int:
    resolved = selection.resolve(ctx.schema, names, type_alias)
    for name in resolved.missing:
        log.warning(f"Объект не найден: {name}")

    targets = list(resolved.matches)
    if with_deps and targets:
        extra = selection.expand_deps(ctx.schema, targets)
        if extra:
            log.info(f"--with-deps: добавлено зависимостей: {len(extra)}")
        targets += extra

    run = Run()
    for cat, obj in targets:
        run.emit_object(ctx, cat, obj)
    mode = WriteMode.STDOUT if to_stdout else WriteMode.TREE
    count = writer.write(run.artifacts, dump_dir, mode)
    where = "напечатано" if to_stdout else f"записано в {dump_dir}"
    log.info(f"Готово: {where} файлов {count}, "
             f"объектов {len(targets)}, пропущено {run.skipped}, "
             f"не найдено {len(resolved.missing)}")
    return 3 if (run.skipped or resolved.missing) else 0


def run_list(ctx: Context, type_alias: str | None) -> int:
    cats = [categories.CATEGORY_BY_ALIAS[type_alias]] if type_alias else list(categories.SELECTABLE)
    for cat in cats:
        names = sorted(cat.name_of(o) for o in cat.objects(ctx.schema))
        print(f"# {cat.key} ({len(names)})")
        for name in names:
            print(f"  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv if argv is None else argv
    parser = _build_parser()
    args = parser.parse_args(list(raw)[1:])

    if args.list_mode and args.names:
        parser.error("--list нельзя использовать вместе с именами объектов")
    if args.list_mode and args.to_stdout:
        parser.error("--list нельзя использовать вместе с --stdout")
    if args.to_stdout and not args.names:
        parser.error("--stdout доступен только в точечном режиме (с именами объектов)")
    if args.with_deps and not args.names:
        parser.error("--with-deps доступен только в точечном режиме (с именами объектов)")
    if args.type and not args.names and not args.list_mode:
        parser.error("--type имеет смысл только в точечном режиме или с --list")

    base_dir = Path.cwd()

    try:
        cfg = config.load(args.config, base_dir)
    except config.ConfigError as exc:
        log.error(str(exc))
        return 1

    # Аудит-лог пишем только когда реально пишем в дерево (полный или точечный
    # без --stdout) И он не отключён через AUDIT_LOG=false. Для --list/--stdout —
    # только консоль.
    writes_tree = not args.list_mode and not args.to_stdout
    if writes_tree and cfg.audit_log:
        log.configure(base_dir)
    log.info("Запуск процесса выгрузки схемы...")

    log.debug(f"Файл окружения                  : [{cfg.source}]")
    log.debug(f"Пользователь БД                 : [{cfg.user}]")
    log.debug("Пароль пользователя             : [********]")
    log.debug(f"Путь к БД                       : [{cfg.database}]")

    started = datetime.now()
    con = None
    try:
        with timeout.limit(cfg.timeout):
            log.info("Подключение и чтение метаданных (read-committed, rec-version, NO WAIT)...")
            con = db.open_connection(cfg)
            ctx = Context(schema=con.schema, dialect=db.dialect(con),
                          with_generator_values=args.with_generator_values)

            if args.list_mode:
                code = run_list(ctx, args.type)
            elif args.names:
                code = run_targeted(ctx, cfg.dump_dir, args.names, args.type, args.to_stdout, args.with_deps)
            else:
                code = run_full(ctx, cfg.dump_dir)
    except TimeoutError as exc:
        log.error(str(exc))
        return 1
    except Exception as exc:  # noqa: BLE001
        log.error(f"Ошибка при извлечении схемы: {exc}")
        return 1
    finally:
        if con is not None:
            con.close()
        for var in ("ISC_USER", "ISC_PASSWORD"):
            os.environ.pop(var, None)

    elapsed = (datetime.now() - started).total_seconds()
    log.info(f"Завершено за {elapsed:.1f} с (код {code})")
    return code
