#!/bin/bash
set -euo pipefail

source ./utils.sh

exec > >(tee -a "audit_$(date +%Y%m%d).log") 2>&1

log "Starting the schematic upload process..."


CONFIG_FILE=".env"
if [ ! -f "$CONFIG_FILE" ]; then
    error "Configuration file $CONFIG_FILE not found"
    exit 1
fi

export $(grep -v '^#' "$CONFIG_FILE" | xargs)


REQUIRED_VARS=("ISC_USER" "ISC_PASSWORD" "FB_DATABASE" "METADATA_FILE" "METADATA_FILE_DELETE_AFTER_PROCESSING" "DUMP_DIR" "ISQL_PATH" "ISQL_TIMEOUT")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        error "The variable $var is not defined in $CONFIG_FILE"
        exit 1
    fi
done


# we convert paths to absolute values ​​BEFORE navigating through directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# if the paths are relative, make them absolute from the root of the launcher
[[ "$METADATA_FILE" = /* ]] || METADATA_FILE="$SCRIPT_DIR/$METADATA_FILE"
[[ "$DUMP_DIR" = /* ]] || DUMP_DIR="$SCRIPT_DIR/$DUMP_DIR"


# go to the script directory to correctly run dependencies
cd "$SCRIPT_DIR"

# phased launch

START_TIME=$SECONDS
./fetch_schema.sh
ELAPSED=$(( SECONDS - START_TIME ))
log "Schema dump completed in ${ELAPSED} seconds"

START_TIME=$SECONDS
./split_objects.sh "$METADATA_FILE" "$DUMP_DIR"
ELAPSED=$(( SECONDS - START_TIME ))
log "The metadata file is split into a structure in ${ELAPSED} seconds"

./clean_system.sh "$DUMP_DIR"

# clear credentials from the current shell session before exiting
unset ISC_USER ISC_PASSWORD
log "The script completed successfully. Done."