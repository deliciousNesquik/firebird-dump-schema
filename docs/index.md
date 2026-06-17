---
title: Firebird Dump Schema
description: Extract a Firebird schema into a one-object-per-file SQL tree — no isql
---

**English** · [Русский]({% link ru.md %})  ·  [GitHub](https://github.com/deliciousNesquik/firebird-dump-schema) · [Releases](https://github.com/deliciousNesquik/firebird-dump-schema/releases)

Turn a live **Firebird** database schema into a clean, diff-friendly tree of
`.sql` files — **one object per file**. Built for version control, backups and
CI/CD. Reads the system catalog directly (no `isql`), three modes: **full dump**,
**targeted export**, **listing**.

---

## See it in action

**1 · Export one table** — type and name come from the catalog; domains and the
primary key are emitted exactly as defined:

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

**2 · A procedure becomes two adjacent files** — a forward declaration and the
body, each wrapped in a `SET TERM` block so it runs as-is:

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

**3 · Full dump** produces a stable numbered tree:

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

**4 · Discover what's there** before exporting:

```console
$ fb-dump-schema --list --type procedure
# procedure (2937)
  ABL$GETFILESTOSEND
  ACTION$ORDERSPEC_RECALC
  CALC_TOTAL
  ...
```

**5 · Pull an object _with everything it depends on_** (recursively):

```console
$ fb-dump-schema V_REPORT --with-deps
V_REPORT (view)
├─ USERLIST (table)            ← from RDB$DEPENDENCIES
│   └─ BAS$ID, BAS$MEMO, …      ← domains of its columns (transitive)
└─ BAS$INTEGER, BAS$VAR_100    ← domains of the view's own columns
→ wrote 12 files
```

---

## Why it's nice

- **One object — one file:** reviewable, diffable schema history.
- **Deterministic output:** stable ordering → minimal diff noise. Generators are
  dumped without their runtime value by default.
- **Runnable SQL:** PSQL wrapped in `SET TERM`; each file self-contained.
- **No `isql`:** direct catalog reads via `firebird-lib`; system objects filtered automatically.
- **Targeted + dependencies:** export exactly what you need, optionally with its
  dependency closure.
- **Safe:** credentials from the environment, never on the command line; masked in logs.

## Install (no Python required)

Grab a self-contained binary from
[**Releases**](https://github.com/deliciousNesquik/firebird-dump-schema/releases):

| OS | Asset |
| --- | --- |
| Windows | `fb-dump-schema-windows-x64.exe` |
| Linux | `fb-dump-schema-linux-x64` |
| macOS | `fb-dump-schema-macos-arm64` |

```bash
chmod +x fb-dump-schema-linux-x64
./fb-dump-schema-linux-x64 --help
```

> The Firebird **client library** (`fbclient` / `libfbclient`) must be available at
> runtime — the driver loads it. It's usually already installed wherever Firebird is used.

Or run from source with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/deliciousNesquik/firebird-dump-schema.git
cd firebird-dump-schema && cp .env.example .env
uv run fb-dump-schema --help
```

## Modes at a glance

| Command | What it does |
| --- | --- |
| `fb-dump-schema` | full dump to `DUMP_DIR` (tree rebuilt) |
| `fb-dump-schema NAME [--type T]` | targeted export into the tree |
| `fb-dump-schema NAME --stdout` | print object DDL to console |
| `fb-dump-schema NAME --with-deps` | object + its dependency closure |
| `fb-dump-schema --list [--type T]` | list objects by category |

**Exit codes:** `0` ok · `1` infra/config/timeout · `2` bad arguments · `3` partial
(some objects skipped or names not found).

## Full documentation

Complete reference — all `.env` variables, every flag, output layout, `--with-deps`
internals, caveats — is in the repository README:
[English](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/README.md) ·
[Русский](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/README.ru.md).

Firebird 3 / 4 / 5 · License: [MIT](https://github.com/deliciousNesquik/firebird-dump-schema/blob/main/LICENSE)
