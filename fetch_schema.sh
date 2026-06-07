#!/bin/bash
set -euo pipefail

# Проверка наличия утилиты isql
if [ ! -x "$ISQL_PATH" ]; then
    error "isql не найден или не исполняемый: $ISQL_PATH"
    exit 1
fi

debug "Имя пользователя БД : [$ISC_USER]"
debug "Пароль пользователя : [********]"
debug "Путь до БД          : [$FB_DATABASE]"
debug "Файл метаданных     : [$METADATA_FILE]"

if [ -f "$METADATA_FILE" ]; then
    debug "Удаление старого файла метаданных"
    rm -f "$METADATA_FILE"
fi

log "Извлечение метаданных через isql..."

# Экспортируем пароль в область видимости isql
export ISC_USER="$ISC_USER"
export ISC_PASSWORD="$ISC_PASSWORD"

if "$ISQL_PATH" -a -output "$METADATA_FILE" "$FB_DATABASE"; then
    log "Метаданные успешно извлечены в $METADATA_FILE"
else
    error "Ошибка извлечения метаданных утилитой isql"
    exit 1
fi