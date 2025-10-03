#!/bin/bash
# Wrapper: run from backend directory to install & start both backend and frontend.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}"/..
exec "${ROOT_DIR}/install_and_start.sh" "$@"
