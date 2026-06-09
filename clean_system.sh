#!/bin/bash
set -euo pipefail

source ./utils.sh

WORK_DIR="${1:-.}"
PROCEDURES_LIST="./system_procedures.list"
FUNCTIONS_LIST="./system_functions.list"

SYSTEM_PROCEDURES=()
SYSTEM_FUNCTIONS=()

# dynamic loading of a list of procedures
if [ -f "$PROCEDURES_LIST" ]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        SYSTEM_PROCEDURES+=("$line")
    done < "$PROCEDURES_LIST"
    debug "System procedures loaded: ${#SYSTEM_PROCEDURES[@]}"
else
    debug "List file $PROCEDURES_LIST not found. Skipping system procedures removal."
fi

# dynamic loading of a list of functions
if [ -f "$FUNCTIONS_LIST" ]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        SYSTEM_FUNCTIONS+=("$line")
    done < "$FUNCTIONS_LIST"
    debug "System procedures loaded: ${#SYSTEM_FUNCTIONS[@]}"
else
    debug "List file $FUNCTIONS_LIST not found. Skipping system procedures removal."
fi

count=0

remove_objects() {
    local target_dir="$1"
    shift
    local objects=("$@")
    
    if [ -d "$target_dir" ] && [ ${#objects[@]} -gt 0 ]; then
        for obj in "${objects[@]}"; do
            local target="$target_dir/${obj}.sql"
            if [ -f "$target" ]; then
                rm -f "$target"
                debug "System object removed: $target"
                ((count++))
            fi
        done
    fi
}

remove_objects "$WORK_DIR/08_PROCEDURES" "${SYSTEM_PROCEDURES[@]+"${SYSTEM_PROCEDURES[@]}"}"
remove_objects "$WORK_DIR/07_FUNCTIONS" "${SYSTEM_FUNCTIONS[@]+"${SYSTEM_FUNCTIONS[@]}"}"

log "System objects removed: $count"