#!/bin/bash
# Set up ESLint for the frontend
set -e
cd ../../frontend
npm install --save-dev eslint @eslint/js eslint-plugin-react eslint-plugin-jsx-a11y
cd ../..
echo "ESLint setup complete."
