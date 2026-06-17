---
title: Firebird Dump Schema
description: Выгрузка схемы Firebird в дерево «один объект — один файл» — без isql
---

[English]({{ '/' | relative_url }}) · **Русский**  ·  [GitHub](https://github.com/deliciousNesquik/firebird-dump-schema) · [Releases](https://github.com/deliciousNesquik/firebird-dump-schema/releases)

Превращает схему живой базы **Firebird** в чистое, дружелюбное к diff'ам дерево
`.sql`-файлов — **один объект на файл**. Для контроля версий, бэкапов и CI/CD.
Читает системный каталог напрямую (без `isql`), три режима: **полный дамп**,
**точечная выгрузка**, **список**.

---

## Как это работает (вживую)

**1 · Выгрузка одной таблицы** — тип и имя берутся из каталога; домены и первичный
ключ выводятся ровно как определены:

```console
$ fb-dump-schema ACCOUNTS --type table --stdout
-- ===== 04_TABLES/ACCOUNTS.sql =====
CREATE TABLE ACCOUNTS (
  OID      BAS$ID,
  ACC      CHAR(8) NOT NULL,
  ACCNAME  BAS$VAR_250,
  ACTIV    BAS$SMALLINT DEFAULT 1
);
ALTER TABLE ACCOUNTS ADD CONSTRAINT PK_ACCOUNTS
  PRIMARY KEY (ACC) USING ASCENDING INDEX PK_ACCOUNTS;
```

**2 · Процедура — это два соседних файла**: прямое объявление и тело, каждый обёрнут
в блок `SET TERM`, чтобы запускаться как есть:

```console
$ fb-dump-schema CALC_TOTAL --type procedure --stdout
-- ===== 08_PROCEDURES/CALC_TOTAL.declaration.sql =====
SET TERM ^ ;
CREATE PROCEDURE CALC_TOTAL (DOC_ID INTEGER)
RETURNS (TOTAL NUMERIC(15,2))
AS
BEGIN END ^
SET TERM ; ^

-- ===== 08_PROCEDURES/CALC_TOTAL.sql =====
SET TERM ^ ;
ALTER PROCEDURE CALC_TOTAL (DOC_ID INTEGER)
RETURNS (TOTAL NUMERIC(15,2))
AS
BEGIN
  SELECT SUM(AMOUNT) FROM DOC_LINES WHERE DOC = :DOC_ID INTO :TOTAL;
END ^
SET TERM ; ^
```

**3 · Полный дамп** создаёт стабильное нумерованное дерево:

```text
database/
├── DATABASE.sql
├── 03_DOMAINS/BAS$ID.sql
├── 04_TABLES/ACCOUNTS.sql
├── 04_TABLES/IDX_ACCOUNTS_NAME.sql
├── 08_PROCEDURES/CALC_TOTAL.declaration.sql
├── 08_PROCEDURES/CALC_TOTAL.sql
├── 11_ROLES/ROLES.sql
└── 12_GRANTS/GRANTS.sql
```

**4 · Сначала посмотреть, что есть**, перед выгрузкой:

```console
$ fb-dump-schema --list --type procedure
# procedure (2937)
  ABL$GETFILESTOSEND
  ACTION$ORDERSPEC_RECALC
  CALC_TOTAL
  ...
```

**5 · Выгрузить объект _со всем, от чего он зависит_** (рекурсивно):

```console
$ fb-dump-schema V_REPORT --with-deps
V_REPORT (view)
├─ USERLIST (таблица)          ← из RDB$DEPENDENCIES
│   └─ BAS$ID, BAS$MEMO, …      ← домены её столбцов (транзитивно)
└─ BAS$INTEGER, BAS$VAR_100    ← домены столбцов самого представления
→ записано 12 файлов
```

---

## Чем хорош

- **Один объект — один файл:** ревью и diff истории схемы.
- **Детерминированный вывод:** стабильный порядок → минимум шума в diff'ах. Генераторы
  по умолчанию выгружаются без runtime-значения.
- **Исполнимый SQL:** PSQL обёрнут в `SET TERM`; каждый файл самодостаточен.
- **Без `isql`:** прямое чтение каталога через `firebird-lib`; системные объекты отсеиваются автоматически.
- **Точечно + зависимости:** выгрузить ровно нужное, опционально с замыканием зависимостей.
- **Безопасно:** учётные данные из окружения, не в аргументах команды; маскируются в логах.

## Установка (Python не нужен)

Возьмите самодостаточный бинарь со страницы
[**Releases**](https://github.com/deliciousNesquik/firebird-dump-schema/releases):

| ОС | Файл |
| --- | --- |
| Windows | `fb-dump-schema-windows-x64.exe` |
| Linux | `fb-dump-schema-linux-x64` |
| macOS | `fb-dump-schema-macos-arm64` |

```bash
chmod +x fb-dump-schema-linux-x64
./fb-dump-schema-linux-x64 --help
```

> Клиентская библиотека Firebird (`fbclient` / `libfbclient`) должна быть доступна в
> рантайме — её грузит драйвер. Обычно она уже есть там, где работают с Firebird.

Либо из исходников через [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/deliciousNesquik/firebird-dump-schema.git
cd firebird-dump-schema && cp .env.example .env
uv run fb-dump-schema --help
```

## Режимы кратко

| Команда | Что делает |
| --- | --- |
| `fb-dump-schema` | полный дамп в `DUMP_DIR` (дерево пересоздаётся) |
| `fb-dump-schema ИМЯ [--type T]` | точечная выгрузка в дерево |
| `fb-dump-schema ИМЯ --stdout` | печать DDL объекта в консоль |
| `fb-dump-schema ИМЯ --with-deps` | объект + замыкание его зависимостей |
| `fb-dump-schema --list [--type T]` | список объектов по категориям |

**Коды возврата:** `0` успех · `1` инфраструктура/конфиг/таймаут · `2` ошибка аргументов ·
`3` частичный прогон (часть объектов пропущена или имена не найдены).

## Полная документация

Исчерпывающий справочник — все переменные `.env`, каждый флаг, структура вывода,
внутренности `--with-deps`, оговорки — в README репозитория:
[English](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/README.md) ·
[Русский](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/README.ru.md).

Firebird 3 / 4 / 5 · Лицензия: [MIT](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/LICENSE)
