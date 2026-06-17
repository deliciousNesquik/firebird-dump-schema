<p align="center"><img src="assets/banner-640x320.png" alt="Firebird Dump Schema" width="640"></p>

# Firebird Dump Schema

**English** · [Русский](README.ru.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Releases](https://img.shields.io/github/v/release/deliciousNesquik/firebird-dump-schema?sort=semver)](https://github.com/deliciousNesquik/firebird-dump-schema/releases)
[![Firebird 3/4/5](https://img.shields.io/badge/Firebird-3%20%7C%204%20%7C%205-orange)](https://firebirdsql.org/)

Command-line tool that extracts the **DDL metadata** of a Firebird database into a
structured **one-object-per-file** tree (`.sql`). Built for schema version control,
backups and CI/CD.

It reads the system catalog directly through [`firebird-lib`](https://pypi.org/project/firebird-lib/)
and asks every object for its own DDL — **no `isql`** and no monolithic dump parsing.
Object type and name come from the catalog, and system objects are filtered out
automatically.

---

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Requirements](#requirements)
- [Configuration (`.env`)](#configuration-env)
- [Usage](#usage)
- [Command-line options](#command-line-options)
- [Output layout](#output-layout)
- [Exit codes & behavior](#exit-codes--behavior)
- [`--with-deps` (dependency resolution)](#--with-deps-dependency-resolution)
- [Transactions](#transactions)
- [Logging](#logging)
- [Caveats & limitations](#caveats--limitations)
- [Recreating the schema](#recreating-the-schema)
- [Development](#development)
- [License](#license)

---

## Features

- **One object — one file**, in a stable numbered tree → clean diffs and code review of the schema.
- **Three modes:** full dump, targeted export of named objects, and listing.
- **Direct catalog reads** via `firebird-lib` — no `isql`, no banner parsing.
- **Automatic system-object filtering** by the catalog flag — no hand-maintained lists.
- **Runnable output** — PSQL objects are wrapped in `SET TERM` blocks; each file is self-contained.
- **Deterministic output** — stable ordering across runs, minimal diff noise.
- **Dependency expansion** (`--with-deps`) — pull everything a named object depends on.
- **Safety** — credentials are read from the environment, never passed on the command line, and masked in logs.
- **Persistent audit log** — all output mirrored to `audit_YYYYMMDD.log` (toggleable).
- **Cross-platform** — prebuilt binaries for Windows / Linux / macOS, or run from source.

## Installation

### Prebuilt binaries (no Python required)

Download a self-contained executable from the
[**Releases**](https://github.com/deliciousNesquik/firebird-dump-schema/releases) page
(built for Windows, Linux and macOS):

| OS | Asset |
| --- | --- |
| Windows | `fb-dump-schema-windows-x64.exe` |
| Linux | `fb-dump-schema-linux-x64` |
| macOS | `fb-dump-schema-macos-arm64` |

```bash
# Linux / macOS
chmod +x fb-dump-schema-linux-x64
./fb-dump-schema-linux-x64 --help
```

- **macOS:** the binary is unsigned — allow it the first time in *System Settings →
  Privacy & Security*.
- **Firebird client library required.** The binary still needs `fbclient.dll` /
  `libfbclient.so` / `libfbclient.dylib` available at runtime (the driver loads it).
  It is usually already present wherever Firebird is used; otherwise install the
  Firebird client (or server). This is the one dependency a frozen binary cannot bundle.

### From source (with [uv](https://docs.astral.sh/uv/))

```bash
git clone https://github.com/deliciousNesquik/firebird-dump-schema.git
cd firebird-dump-schema
cp .env.example .env          # fill in credentials/paths
uv run fb-dump-schema --help  # uv builds the environment from pyproject.toml automatically
```

Without `uv`, install the package into a virtualenv and run `python -m fbschema`.

## Requirements

- **Target DBMS:** Firebird 3 / 4 / 5. (Firebird 2.5 is out of scope — it needs a
  different driver.)
- **Firebird client library** (`libfbclient`) reachable by `firebird-driver`.
- **For running from source:** Python 3.11+; dependencies `firebird-driver`,
  `firebird-lib`, `python-dotenv` (declared in `pyproject.toml`).

## Configuration (`.env`)

Connection parameters are read from an `.env` file (path via `-c/--config`, default `./.env`).

| Variable | Required | Default | Description |
| --- | :---: | --- | --- |
| `ISC_USER` | ✅ | — | Database user (e.g. `SYSDBA`). |
| `ISC_PASSWORD` | ✅ | — | User password. |
| `FB_DATABASE` | ✅ | — | Database address. Local: path or alias. Remote: `HOST:ALIAS_OR_PATH`. |
| `DUMP_DIR` | ✅ | — | Output directory for the schema tree. Absolute, or relative to the current working directory. |
| `ISQL_TIMEOUT` | — | `0` | Metadata-read timeout in seconds; `<= 0` disables it. POSIX only (SIGALRM). |
| `DB_CHARSET` | — | `UTF8` | Connection charset. For legacy databases whose metadata is single-byte, set it explicitly (e.g. `WIN1251` for Cyrillic), otherwise reading fails with `UnicodeDecodeError`. |
| `AUDIT_LOG` | — | `true` | Write `audit_YYYYMMDD.log`. `false`/`0`/`no`/`off` disables the file. |

The `ISC_*` prefix is intentional: these are standard Firebird variables, read at
runtime and never passed as command-line arguments (so they don't leak via `ps aux`).

## Usage

The config path is a flag (`-c/--config`, default `./.env`); object names are positional.

### Full dump

No object names and no `--list` → dump the whole schema (the tree is wiped and rebuilt).

```bash
fb-dump-schema                    # uses ./.env
fb-dump-schema -c production.env  # custom config (multiple databases)
```

### Targeted export

One or more object names → export only those objects. Names may collide across object
types; `--type` disambiguates. Without `--type`, **all** matches across categories are exported.

```bash
fb-dump-schema ACCOUNT                 # all matches named ACCOUNT
fb-dump-schema ACCOUNT --type table    # only the table
fb-dump-schema CALC_TOTAL --stdout     # print DDL to console instead of the tree
fb-dump-schema V_REPORT --with-deps    # object + everything it depends on
```

By default targeted export writes into the existing `DUMP_DIR`, **updating only the
named objects' files** (the tree is *not* wiped, and stale files are *not* pruned —
that is the full dump's job). Grants and comments are not touched in targeted mode
(they are refreshed by a full dump). `--stdout` prints rendered SQL and touches no files.

### List

```bash
fb-dump-schema --list                  # all objects grouped by category
fb-dump-schema --list --type procedure # only procedures
```

## Command-line options

| Option | Mode | Description |
| --- | --- | --- |
| `-c`, `--config ENV` | all | Path to the `.env` (default `./.env`). |
| `NAMES…` (positional) | targeted | Object names to export. Presence selects targeted mode. |
| `--type TYPE` | targeted, list | Restrict to one object type. In list mode it filters. |
| `--list` | list | List object names by category and exit. |
| `--stdout` | targeted | Print SQL to stdout instead of writing the tree. |
| `--with-deps` | targeted | Also export objects the named ones depend on (transitively). |
| `--with-generator-values` | all | Emit current generator/sequence values (off by default — see below). |
| `-h`, `--help` | — | Show help. |

**`--type` values:** `table`, `index`, `view`, `procedure` (`proc`), `function`,
`external-function` (`udf`), `trigger`, `exception`, `domain`, `generator` (`sequence`),
`role`, `package`. (`grant`/`comment` are cross-cutting and not selectable.)

`python -m fbschema …` is equivalent to the `fb-dump-schema` entry point.

## Output layout

`DUMP_DIR` gets a numbered tree; filenames match object names:

```
01_EXTERNAL_FUNCTIONS/   05_VIEWS/        09_PACKAGES/
02_GENERATORS/           06_EXCEPTIONS/   10_TRIGGERS/
03_DOMAINS/              07_FUNCTIONS/    11_ROLES/      (ROLES.sql)
04_TABLES/               08_PROCEDURES/   12_GRANTS/     (GRANTS.sql)
DATABASE.sql                              13_COMMENTS/   (COMMENTS.sql)
```

- **Tables** — `CREATE TABLE` plus its constraints in one file; **indexes** are
  separate files in `04_TABLES`.
- **Procedures / functions** — two adjacent files per object: `<NAME>.declaration.sql`
  (forward declaration) and `<NAME>.sql` (body). They are processed separately and
  resolve circular dependencies.
- **External functions (UDFs)** go to `01_EXTERNAL_FUNCTIONS`.
- **Packages** — header + body in one file.
- **Generators** are dumped **without** their current value by default (it is runtime
  state and produces diff noise); add `--with-generator-values` to include it.
- **Roles / grants / comments** are aggregated (`ROLES.sql`, `GRANTS.sql`,
  `COMMENTS.sql`); `DATABASE.sql` holds the SQL dialect preamble.
- **PSQL objects** are wrapped in `SET TERM ^ ;` … `^` … `SET TERM ; ^`; everything else
  is terminated with `;`. Output is deterministic (sorted) for stable diffs.

## Exit codes & behavior

| Code | Meaning |
| :---: | --- |
| `0` | Success. |
| `1` | Infrastructure / configuration / timeout error (cannot connect, bad `.env`, timed out). |
| `2` | Command-line argument error (invalid combination or unknown `--type`). |
| `3` | Partial run: some objects were skipped (error / no permission) or requested names were not found. |

A single object's failure (`get_sql_for` raising, or insufficient privileges) is logged
as a warning, skipped and counted — it does **not** abort the whole dump (CI-friendly).

Argument errors that yield exit `2` include: `--list` together with names; `--list`
together with `--stdout`; `--stdout` or `--with-deps` without names; `--type` in full
mode (no names, no `--list`); an unknown `--type` value.

## `--with-deps` (dependency resolution)

In targeted mode, `--with-deps` additionally exports everything the named objects depend
on, **recursively (transitively)** — for a self-contained, recreatable set. It is a
breadth-first walk with cycle protection.

Example for a view `DBA$MONITOR` that reads table `USERLIST`:

```
DBA$MONITOR (view)
├─ USERLIST (table)                  ← level 1: from RDB$DEPENDENCIES
│   ├─ BAS$ID, BAS$MEMO, …            ← level 2: domains of USERLIST's columns
├─ BAS$TIMESTAMP                     ← from the view body (RDB$DEPENDENCIES)
└─ BAS$INTEGER, BAS$VAR_100          ← domains of the view's own columns
```

Dependency sources:

- **`RDB$DEPENDENCIES`** (views → tables, procedures → procedures/tables, expressions…).
- **Column / parameter domains** — Firebird does *not* record the "column → its type
  domain" link in `RDB$DEPENDENCIES`, so it is collected separately.

Not tracked: links outside those sources — e.g. tables referenced by a foreign key, or
objects referenced only from dynamic SQL.

## Transactions

Metadata is always read in a **read-committed + record-version + NO WAIT** transaction
(WAIT mode could hang the process on a lock conflict). NO WAIT is enforced on the
transaction `firebird-lib` opens internally.

## Logging

Diagnostic output goes to **stderr**, so **stdout stays clean data** (object names in
`--list`, SQL in `--stdout`) — pipe- and redirect-friendly. In tree-writing modes (full
and targeted) the diagnostics are also mirrored to a persistent `audit_YYYYMMDD.log` in
the current directory; disable it with `AUDIT_LOG=false`. Passwords are masked (`********`).

## Caveats & limitations

- **Not byte-identical to `isql -a`.** `firebird-lib` formats DDL differently (whitespace,
  clause order), though it is semantically equivalent. The first run over a tree produced
  by another tool yields a large one-time diff.
- **View ordering.** With one file per object, inter-view dependency order is not
  guaranteed when concatenating a single directory alphabetically.
- **`--with-deps`** does not follow foreign keys or dynamic-SQL references (see above).
- **Charset.** Legacy single-byte databases need `DB_CHARSET` set explicitly.
- **Performance over WAN.** `firebird-lib` reads some per-object metadata lazily; over a
  high-latency link a full dump of a large database can be slow. Run the full dump close
  to the database (LAN); targeted exports stay cheap.
- **Firebird 2.5** is out of scope.

## Recreating the schema

Concatenate the files in directory order (`01_*` → `13_*`) and feed them to `isql`
against a fresh database. For procedures/functions, apply all `*.declaration.sql` before
the bodies (forward declarations satisfy circular dependencies). The numbered directories
encode the correct cross-category order.

## Development

```bash
uv run pyright fbschema   # type-check (0 errors expected)
uv run pytest -q          # offline test suite (no database required)
```

Tests run against a mock schema, so they need neither a live database nor `libfbclient`.
CI (GitHub Actions) runs type-check + tests on every push; tagging `vX.Y.Z` builds and
publishes the standalone binaries.

## License

[MIT](LICENSE).
