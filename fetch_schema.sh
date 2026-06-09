#!/bin/bash
set -euo pipefail

source ./utils.sh

# checking for the presence of the isql utility
if [ ! -x "$ISQL_PATH" ]; then
    error "isql not found or not executable: $ISQL_PATH"
    exit 1
fi

debug "DB username                     : [$ISC_USER]"
debug "User password                   : [********]"
debug "Path to the DB                  : [$FB_DATABASE]"
debug "Metadata file                   : [$METADATA_FILE]"
debug "Delete metadata file after dump : [$METADATA_FILE_DELETE_AFTER_PROCESSING]"

if [ -f "$METADATA_FILE" ]; then
    debug "Deleting the old metadata file"
    rm -f "$METADATA_FILE"
fi

log "Extracting metadata via isql..."

# exporting the password to the isql scope
export ISC_USER="$ISC_USER"
export ISC_PASSWORD="$ISC_PASSWORD"

# Prepare timeout prefix
[[ "$ISQL_TIMEOUT" -lt 1 ]] && {
    error "The timeout specified is less than 1. Don't use a timeout to run the command."
    TIMEOUT_CMD=()
} || TIMEOUT_CMD=(timeout "$ISQL_TIMEOUT")

# Execute
if "${TIMEOUT_CMD[@]}" "$ISQL_PATH" -a -output "$METADATA_FILE" "$FB_DATABASE"; then
    log "Metadata successfully extracted to $METADATA_FILE"
else
    error "Error retrieving metadata using isql utility"
    exit 1
fi