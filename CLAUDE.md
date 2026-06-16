# CLAUDE.md

Этот файл даёт указания Claude Code (claude.ai/code) при работе с кодом в этом репозитории.

## Что это

Пакет `fbschema`, извлекающий схему базы данных Firebird в дерево «один объект — один файл» (`.sql`). Читает системный каталог напрямую через API `Schema` из `firebird-lib` и запрашивает DDL у каждого объекта через `get_sql_for(...)`. `isql` не используется.

Три режима: **полный** дамп, **точечная** выгрузка названных объектов, **список** объектов.

## Запуск

```bash
cp .env.example .env                          # параметры подключения
uv run fb-dump-schema                          # полный дамп (.env)
uv run fb-dump-schema -c prod.env              # полный дамп, кастомный конфиг
uv run fb-dump-schema ACCOUNT                  # точечно: объект(ы), все совпадения по категориям
uv run fb-dump-schema ACCOUNT --type table     # точечно с уточнением типа
uv run fb-dump-schema ACCOUNT --stdout         # точечно: печать в консоль (не в дерево)
uv run fb-dump-schema --list [--type procedure]  # перечислить объекты
uv run python -m fbschema ...            # эквивалент без entry point
```

Конфиг — флаг `-c/--config` (по умолчанию `.env`); имена объектов — позиционные. Проверка типов:

```bash
uv run pyright fbschema
```

Зависимости и настройки `uv` (внутренний индекс, `native-tls`, dev-группа с `pyright`) — в `pyproject.toml`. При сбое TLS (`unable to get local issuer certificate`) укажите CA: `SSL_CERT_FILE="$HOME/.config/reid/root_ca.crt"` и снимите `native-tls`.

Юнит-тестов в репозитории нет. Логика проверяется офлайн-прогоном с мок-схемой (резолв/режимы writer'а/диспетчеры) и запуском против реальной БД (FB 3/4/5; нужен `libfbclient`).

## Коды возврата

`0` — успех; `1` — инфраструктура/конфиг/таймаут; `2` — ошибка аргументов CLI; `3` — частичный прогон (были пропуски объектов или не найдены запрошенные имена). Сбой одного объекта (`get_sql_for`/нет прав) логируется WARNING, пропускается и считается — не валит весь прогон.

## Архитектура

Центральная идея — развязать «какой объект какой SQL порождает» от «как это пишется в файлы» через единицу вывода `Artifact(path, sql, psql)`. Объекты сгруппированы в **категории**; каждая категория умеет отдать коллекцию (`objects`) и DDL одного объекта (`artifacts_for`) — это переиспользуется во всех трёх режимах.

```
cli.main(argv)
  ├─ argparse + пост-валидация (ошибка → exit 2)
  ├─ config.load(-c, base)        -> Config
  ├─ db.open_connection(config)   -> Connection   (NO-WAIT навязан импортом db)
  │     └─ Context(schema, dialect)
  └─ with timeout.limit(cfg.timeout):
        полный  : database_preamble + по всем CATEGORIES × objects + full_grants/full_comments
        точечный: selection.resolve(names, type) → matches
        список  : перечислить objects по категориям
        writer.write(artifacts, dump_dir, mode)   # FULL | TREE | STDOUT
```

Модули (`fbschema/`):

| Модуль | Ответственность |
| --- | --- |
| `cli.py` | argparse, выбор режима, `Run` (по-объектная устойчивость), exit-коды, оркестрация |
| `config.py` | `Config` + `load()`/валидация; `ConfigError` |
| `log.py` | `info`/`debug`/`warning`/`error` → stderr; аудит-лог `audit_YYYYMMDD.log` (под `AUDIT_LOG`) |
| `timeout.py` | `limit(seconds)` — сторож `ISQL_TIMEOUT` (SIGALRM; `<=0` отключает) |
| `db.py` | `open_connection()`, `dialect()` и **политика NO-WAIT** (патч при импорте) |
| `model.py` | `Artifact`, `Context`, `SUBDIRS` |
| `categories.py` | `Category` + `objects()`/`artifacts_for()` по видам, реестры, `database_preamble`/`full_grants`/`full_comments`, `_is_sys`, `get_grants` |
| `selection.py` | `resolve(names, type)` → `Resolved(matches, missing)`; `expand_deps` (для `--with-deps`) |
| `render.py` | `fname()`, `render(statements, psql)` — терминаторы/`SET TERM` |
| `writer.py` | `WriteMode` (FULL/TREE/STDOUT), группировка артефактов → запись/печать |

### Категории и реестр

`Category(key, subdir, aliases, objects, artifacts_for, name_of)`. `objects()` инкапсулирует фильтр `is_sys_object()` и расщепление общих коллекций по виду (на `schema.functions` сидят `external_function` через `is_external()` и PSQL `function`). `artifacts_for(ctx, obj)` повторяет логику `get_metadata_ddl`:

- Таблицы: `get_sql_for('create', no_pk=True, no_unique=True)` + констрейнты из `table.constraints` (пропуская `is_not_null`) в тот же файл. **Индексы — отдельная категория** `index` (не-enforcer), файлы тоже в `04_TABLES`.
- Процедуры/функции: stub `get_sql_for('create', no_code=True)` → `00_DECLARATION.sql`; тело `'ALTER' + get_sql_for('create')[6:]` → файл по объекту. Пропуск `is_packaged()`; внешние функции — `01_…` через `'declare'`.
- Пакеты: header `get_sql_for('create')` + тело `get_sql_for('create', body=True)`.

Селектируемые категории — в `SELECTABLE`/`CATEGORY_BY_ALIAS`; `TYPE_CHOICES` — значения для `--type`. **Не категории** (только полный режим): `database_preamble` (`DATABASE.sql`), `full_grants` (`12_GRANTS`), `full_comments` (`13_COMMENTS`) — поэтому `--type grant/comment` отклоняется argparse'ом.

### Режимы writer'а

- **FULL** — `prepare_tree` (очистка + пересоздание `SUBDIRS`) → запись всего.
- **TREE** (точечный по умолчанию) — без очистки; перезапись только затронутых файлов (`mkdir(parents)` по месту). Удалённые объекты **не подчищаются** — это делает полный дамп.
- **STDOUT** (`--stdout`) — рендер + печать с заголовком `-- ===== <path> =====`, ФС не трогаем.

Группировка артефактов идёт в порядке вставки (детерминизм). `render()` оборачивает PSQL в `SET TERM ^ ;` … `^` … `SET TERM ; ^`, остальное — `;`.

### Точечный режим: --with-deps

Флаг `--with-deps` (только точечный режим) транзитивно добавляет объекты, от которых зависят названные. `selection.expand_deps` обходит зависимости в ширину с множеством посещённых (защита от циклов). Источники зависимостей:

1. **RDB$DEPENDENCIES** через `SchemaItem.get_dependencies()`; `Dependency.depended_on` отдаёт сам объект, а `_category_of` маппит его в `Category` **по классу** (не по коду `RDB$OBJECT_TYPE`) — это важно для функций: UDF и PSQL имеют один код 15, но различаются через `is_external()`. Колонки разворачиваются в свою таблицу/представление.
2. **Домены столбцов/параметров** (`_domain_refs`) — связь «столбец → домен типа» Firebird в RDB$DEPENDENCIES НЕ пишет, поэтому собираем её отдельно из `.columns` (таблицы/представления) и `.input_params`/`.output_params`/`.arguments` (процедуры/функции); системные RDB$-домены inline-типов отсеиваются по `is_sys_object`.

Системные и пакетные объекты пропускаются. Остаточные пробелы — связи, которых нет ни в RDB$DEPENDENCIES, ни в (1)/(2): напр. таблицы по внешнему ключу или объекты из динамического SQL не отслеживаются.

### Точечный режим: grants/comments

Гранты и комментарии — кросс-секущие (привязаны к объектам). В точечном режиме файлы `GRANTS.sql`/`COMMENTS.sql` **не трогаются** (чтобы точечное обновление не переписало глобальный агрегат). Роль (`ROLES.sql`) при точечном выборе перезаписывается целиком. Освежает гранты/комментарии полный дамп.

## Критическая конвенция — параметры транзакции

Все транзакции — **read-committed + record-version + NO WAIT** (WAIT может зависнуть на блокировке). `Schema.bind()` строит свой read-курсор с дефолтом `lock_timeout=-1` (WAIT). Поэтому `db.py` **оборачивает `firebird.lib.schema.tpb`** (`_nowait_tpb`), форсируя `lock_timeout=0` (nowait). Единственное место с правилом транзакций; при обновлении `firebird-lib` перепроверьте, что обёртка перехватывает транзакцию reader'а схемы.

При чтении/анализе живого DDL используйте meta-mcp (`get_object`, `search_metadata`, `find_references`), а не открывайте соединение.

## Вне рамок (сейчас)

preload/bulk-оптимизация N+1 не нужна (запуск в LAN). `isql` не используем. Firebird 2.5 (`fdb`) вне охвата. Чистка Reid-специфики (внутренний индекс/CA в `pyproject`) — отдельно перед публикацией.

## Оговорка

«Один объект — один файл»: порядок зависимостей между представлениями не гарантирован при алфавитной склейке одной директории; для воссоздания склеивайте в порядке директорий (`01_*` → `13_*`).

## Проверка

1. **Типы:** `uv run pyright fbschema` → 0 ошибок.
2. **Офлайн:** прогон с мок-схемой — `resolve` (регистр, коллизии, missing, фильтр sys/enforcer), режимы writer'а, диспетчеры `run_*`, валидация argparse.
3. **Полный режим:** `uv run fb-dump-schema -c test.env` → дерево `01_*..13_*`; число файлов сверить с `list_objects`/`search_metadata` из meta-mcp.
4. **Точечный/список:** `… ACCOUNT`, `… ACCOUNT --stdout`, `… --list --type procedure`.
5. **Round-trip:** склейка в порядке директорий → `isql` в пустую БД без ошибок.
