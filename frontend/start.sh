#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
npm install
npx vite --port 5173
