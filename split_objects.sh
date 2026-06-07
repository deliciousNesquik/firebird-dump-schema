#!/bin/bash
set -euo pipefail

DDL_FILE="$1"
WORK_DIR="$2"

log "Обработка файла: $DDL_FILE"
log "Директория вывода: $WORK_DIR"

# -----------------------------------------------------------------
# Подготовка директории (Полная очистка и пересоздание)
# -----------------------------------------------------------------
if [ -d "$WORK_DIR" ]; then
    log "Удаление старой директории вывода: $WORK_DIR"
    rm -rf "$WORK_DIR"
fi

log "Создание структуры директорий..."
mkdir -p "$WORK_DIR"/{01_EXTERNAL_FUNCTIONS,02_GENERATORS,03_DOMAINS,04_TABLES,05_VIEWS,06_EXCEPTIONS,07_FUNCTIONS,08_PROCEDURES,09_PACKAGES,10_TRIGGERS,11_ROLES,12_GRANTS,13_COMMENTS}

# Дальше идет запуск AWK-парсера...
log "Запуск AWK-парсера для извлечения объектов..."
if awk -v WORK_DIR="$WORK_DIR" '

# Функция для переключения файлов (решает проблему ulimit)
function switch_file(new_file) {
    # Если файл изменился (или нам приказали сбросить вывод передав "")
    if (CURRENT_FILE != "" && CURRENT_FILE != new_file) {
        close(CURRENT_FILE)
    }
    CURRENT_FILE = new_file
}

function write_line() {
    if (CURRENT_FILE != "") {
        print $0 >> CURRENT_FILE
    }
}

# Функция очистки имени. Удаляет ;, ^, запятые (,), а также всё, начиная со скобки (
function clean_name(str) {
    gsub(/[;^,]+$/, "", str) # удаляем мусор в конце строки (включая запятые!)
    sub(/\(.*$/, "", str)    # удаляем прилипшие параметры: name(:VAR) -> name
    return str
}

# Функция поиска слова после ключевого (INDEX, PROCEDURE и т.д.)
function get_word_after(target_word) {
    for (i = 1; i <= NF; i++) {
        if ($i == target_word) return clean_name($(i+1))
    }
    return ""
}

# 1. ОПРЕДЕЛЕНИЕ ТЕКУЩЕГО КОНТЕКСТА
# Внимание: здесь убран next, чтобы строки-триггеры (типа /* Table: ...) не проглатывались!
/^\/\*  External Function declarations \*\/$/    { DIR = "01_EXTERNAL_FUNCTIONS"; switch_file("") }
/^\/\*  Generators or sequences \*\/$/           { DIR = "02_GENERATORS"; switch_file("") }
/^\/\* Domain definitions \*\/$/                 { DIR = "03_DOMAINS"; switch_file("") }
/^\/\* Table: / && / \*\/$/                      { DIR = "04_TABLES"; switch_file("") }
/^\/\* Stored functions /                        { DIR = "07_FUNCTIONS"; switch_file("") }
/^\/\* Stored procedures /                       { DIR = "08_PROCEDURES"; switch_file("") }
/^\/\* Package /                                 { DIR = "09_PACKAGES"; switch_file("") }
/^\/\*  Index definitions /                      { DIR = "04_TABLES"; switch_file("") }
/^\/\* View: / && / \*\/$/                       { DIR = "05_VIEWS"; switch_file("") }
/^\/\*  Exceptions \*\/$/                        { DIR = "06_EXCEPTIONS"; switch_file("") }
/^\/\* Domain constraints \*\/$/                 { DIR = "03_DOMAINS"; switch_file("") }
/^\/\* Table constraints \*\/$/                  { DIR = "04_TABLES"; switch_file("") }
/^\/\* Computed fields \*\/$/                    { DIR = "04_TABLES"; switch_file("") }
/^\/\* Triggers /                                { DIR = "10_TRIGGERS"; switch_file("") }
/^\/\* Grant roles /                             { DIR = "11_ROLES"; switch_file("") }
/^\/\* Grant permissions /                       { DIR = "12_GRANTS"; switch_file("") }
/^\/\* Comments /                                { DIR = "13_COMMENTS"; switch_file("") }

/^SET SQL DIALECT/ || /^CREATE DATABASE/ {
    switch_file(WORK_DIR "/DATABASE.sql")
    write_line()
}

# 2. ОБРАБОТКА ОБЪЕКТОВ

# 01_EXTERNAL_FUNCTIONS
/^DECLARE EXTERNAL FUNCTION/,/;$/ {
    if (DIR == "01_EXTERNAL_FUNCTIONS" && /^DECLARE /) { switch_file(WORK_DIR "/" DIR "/" clean_name($4) ".sql") }
    write_line()
}

# 02_GENERATORS
/^CREATE GENERATOR/,/;$/ {
    if (DIR == "02_GENERATORS" && /^CREATE /) { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
    write_line()
}

# 03_DOMAINS
/^CREATE DOMAIN / || /^ALTER DOMAIN /,/;$/ {
    if (DIR == "03_DOMAINS" && (/^CREATE / || /^ALTER /)) { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
    write_line()
}

# 04_TABLES
/^\/\* Table:/ || /^ALTER TABLE/,/;$/ {
    if (DIR == "04_TABLES") {
        if ($2 == "Table:") { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
        if (/^ALTER TABLE/) { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
    }
    write_line()
}

# 04_TABLES (Индексы)
/^CREATE / && / INDEX /,/;$/ {
    if (DIR == "04_TABLES" && /^CREATE /) {
        idx_name = get_word_after("INDEX")
        if (idx_name != "") { switch_file(WORK_DIR "/" DIR "/" idx_name ".sql") }
    }
    write_line()
}

# 05_VIEWS
/^\/\* View/,/;$/ {
    if (DIR == "05_VIEWS" && /^\/\* View/) { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
    write_line()
}

# 06_EXCEPTIONS
/^CREATE EXCEPTION/,/;$/ {
    if (DIR == "06_EXCEPTIONS" && /^CREATE /) { switch_file(WORK_DIR "/" DIR "/" clean_name($3) ".sql") }
    write_line()
}

# 07_FUNCTIONS
/^CREATE OR ALTER FUNCTION/ || /^ALTER FUNCTION/ || /^CREATE FUNCTION/,/\^$/ {
    if (DIR == "07_FUNCTIONS") {
        if (/^CREATE /) {
            # Это пустышка (Declaration) - складываем в общий файл
            switch_file(WORK_DIR "/" DIR "/00_DECLARATION.sql")
        } else if (/^ALTER /) {
            # Это тело (Implementation) - складываем в индивидуальный файл
            func_name = get_word_after("FUNCTION")
            if (func_name != "") { switch_file(WORK_DIR "/" DIR "/" func_name ".sql") }
        }
    }
    write_line()
}

# 08_PROCEDURES
/^CREATE PROCEDURE / || /^CREATE OR ALTER PROCEDURE/ || /^ALTER PROCEDURE/,/\^$/ {
    if (DIR == "08_PROCEDURES") {
        if (/^CREATE /) {
            # Это пустышка (Declaration) - складываем в общий файл
            switch_file(WORK_DIR "/" DIR "/00_DECLARATION.sql")
        } else if (/^ALTER /) {
            # Это тело (Implementation) - складываем в индивидуальный файл
            proc_name = get_word_after("PROCEDURE")
            if (proc_name != "") { switch_file(WORK_DIR "/" DIR "/" proc_name ".sql") }
        }
    }
    write_line()
}

# 09_PACKAGES
/^\/\* Package header:/ || /^\/\* Package body:/,/\^$/ {
    if (DIR == "09_PACKAGES" && /^\/\* Package/) { switch_file(WORK_DIR "/" DIR "/" clean_name($4) ".sql") }
    write_line()
}

# 10_TRIGGERS
/^CREATE TRIGGER/ || /^CREATE OR ALTER TRIGGER/,/\^$/ {
    if (DIR == "10_TRIGGERS" && (/^CREATE / || /^ALTER /)) {
        trig_name = get_word_after("TRIGGER")
        if (trig_name != "") { switch_file(WORK_DIR "/" DIR "/" trig_name ".sql") }
    }
    write_line()
}

# 11, 12, 13 РОЛИ, ГРАНТЫ И КОММЕНТАРИИ
/^\/\* Role/,/;$/ {
    if (DIR == "11_ROLES") { switch_file(WORK_DIR "/" DIR "/ROLES.sql") }
    write_line()
}

/^GRANT /,/;$/ {
    if (DIR == "12_GRANTS") { switch_file(WORK_DIR "/" DIR "/GRANTS.sql") }
    write_line()
}

/^COMMENT ON/,/;$/ {
    if (DIR == "13_COMMENTS") { switch_file(WORK_DIR "/" DIR "/COMMENTS.sql") }
    write_line()
}
' "$DDL_FILE"; then
    log "Успешно: объекты разделены по директориям"
else
    log "ERROR: Ошибка обработки файла"
    exit 1
fi