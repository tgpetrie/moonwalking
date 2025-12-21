#!/usr/bin/env bash
set -euo pipefail

tail -n 120 -f /tmp/mw_backend.log /tmp/mw_frontend.log
