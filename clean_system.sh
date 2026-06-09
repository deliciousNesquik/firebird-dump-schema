#!/bin/bash
set -euo pipefail

WORK_DIR="${1:-.}"

SYSTEM_PROCEDURES=(
    "TRANSITIONS" "CANCEL_SESSION" "DISCARD" "FINISH_SESSION" "FLUSH"
    "PAUSE_SESSION" "RESUME_SESSION" "SET_FLUSH_INTERVAL" "CANCEL_BLOB"
    "CLOSE_HANDLE" "OPEN_BLOB" "CREATE_BLOB" "SEEK" "READ_DATA" "IS_WRITABLE"
)
SYSTEM_FUNCTIONS=()

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