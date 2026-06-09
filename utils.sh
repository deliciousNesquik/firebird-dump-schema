#!/bin/bash
set -euo pipefail

# script logging functions
log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1"; }
debug() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [DEBUG] $1"; }
error() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1" >&2; }
