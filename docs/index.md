---
title: Firebird Dump Schema
---

# Firebird Dump Schema

Утилита командной строки для извлечения DDL-метаданных Firebird в дерево
«один объект — один файл» (`.sql`). Для контроля версий схемы, бэкапов и CI/CD.
Читает системный каталог напрямую (без `isql`); три режима — полный дамп,
точечная выгрузка, список объектов.

## Скачать (без Python и uv)

Готовые бинарники — на странице [**Releases**](https://github.com/deliciousNesquik/firebird-dump-schema/releases):

- **Windows** — `fb-dump-schema-windows-x64.exe`
- **Linux** — `fb-dump-schema-linux-x64`
- **macOS** — `fb-dump-schema-macos-arm64`

После скачивания:

```bash
# Linux / macOS
chmod +x fb-dump-schema-*        # сделать исполняемым
./fb-dump-schema-linux-x64 --help
```

- **macOS:** бинарь не подписан — при первом запуске разрешите его в
  «Системные настройки → Конфиденциальность и безопасность».
- **Требуется клиентская библиотека Firebird** (`fbclient.dll` / `libfbclient.so` /
  `libfbclient.dylib`) — её грузит драйвер в рантайме. Обычно она уже есть там, где
  работают с Firebird; иначе поставьте Firebird client (или сервер).

## Быстрый старт

```bash
cp .env.example .env          # параметры подключения (ISC_USER, ISC_PASSWORD, FB_DATABASE, DUMP_DIR)
fb-dump-schema                # полный дамп
fb-dump-schema ACCOUNT        # точечно: один объект (все совпадения по категориям)
fb-dump-schema ACCOUNT --type table --stdout   # печать DDL в консоль
fb-dump-schema --list --type procedure          # перечислить процедуры
```

Для legacy-баз с однобайтовой кодировкой укажите `DB_CHARSET` (напр. `WIN1251`).

## Документация и исходники

Полное описание режимов, кодов возврата и структуры вывода — в
[README репозитория](https://github.com/deliciousNesquik/firebird-dump-schema).

Лицензия — MIT.
