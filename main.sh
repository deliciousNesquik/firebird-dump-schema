#!/bin/bash
set -euo pipefail

# Центр логирования
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1"; }
debug() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [DEBUG] $1"; }
error() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2; }

log "Запуск процесса выгрузки схемы..."

CONFIG_FILE=".env"
if [ ! -f "$CONFIG_FILE" ]; then
    error "Файл конфигурации $CONFIG_FILE не найден"
    exit 1
fi

# Экспортируем функции, чтобы они были доступны в дочерних скриптах
export -f log debug error

# Включаем автоматический экспорт всех новых переменных
set -a
source "$CONFIG_FILE"
# Выключаем автоматический экспорт, чтобы не засорять окружение дальше
set +a

REQUIRED_VARS=("ISC_USER" "ISC_PASSWORD" "FB_DATABASE" "METADATA_FILE" "DUMP_DIR" "ISQL_PATH")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        error "Переменная $var не задана в $CONFIG_FILE"
        exit 1
    fi
done

# Приводим пути к абсолютным значениям ДО перехода по директориям
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Если пути относительные, делаем их абсолютными от корня запуска
[[ "$METADATA_FILE" = /* ]] || METADATA_FILE="$SCRIPT_DIR/$METADATA_FILE"
[[ "$DUMP_DIR" = /* ]] || DUMP_DIR="$SCRIPT_DIR/$DUMP_DIR"

# Переходим в директорию скриптов для корректного запуска зависимостей
cd "$SCRIPT_DIR"

# Поэтапный запуск
./fetch_schema.sh
./split_objects.sh "$METADATA_FILE" "$DUMP_DIR"
./clean_system.sh "$DUMP_DIR"

# Очистка учетных данных из текущей сессии shell перед выходом
unset ISC_USER ISC_PASSWORD
log "Работа скрипта успешно завершена. Готово."