#!/usr/bin/env sh
echo "[pre-commit] Running backend tests & worker typecheck";
npm run test:backend || exit 1
npm run test:worker || exit 1
echo "[pre-commit] OK"
