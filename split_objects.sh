#!/bin/bash
set -euo pipefail

source ./utils.sh

DDL_FILE="$1"
WORK_DIR="$2"

log "File processing: $DDL_FILE"
log "Output directory: $WORK_DIR"


if [ -d "$WORK_DIR" ]; then
    log "Removing the old output directory: $WORK_DIR"
    rm -rf "$WORK_DIR"
fi

log "Creating directory structure..."
mkdir -p "$WORK_DIR"/{01_EXTERNAL_FUNCTIONS,02_GENERATORS,03_DOMAINS,04_TABLES,05_VIEWS,06_EXCEPTIONS,07_FUNCTIONS,08_PROCEDURES,09_PACKAGES,10_TRIGGERS,11_ROLES,12_GRANTS,13_COMMENTS}

# next comes the launch of the AWK parser...
log "Running the AWK parser to extract objects..."
if awk -f parser.awk -v WORK_DIR="$WORK_DIR" "$DDL_FILE"; then
    log "Success: objects are separated into directories"
else
    error "ERROR: File processing error"
    exit 1
fi

if [[ "$METADATA_FILE_DELETE_AFTER_PROCESSING" == 'true' ]]; then
	log "Delete the metadata file after the parser finishes."
	rm -rf "$DDL_FILE"
fi