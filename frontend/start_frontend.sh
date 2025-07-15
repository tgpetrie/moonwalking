#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d "node_modules" ]; then
  npm install --no-bin-links
fi
[ ! -f .env ] && cp .env.example .env
npm run dev
