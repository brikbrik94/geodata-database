#!/usr/bin/env bash
set -euo pipefail

# 1. Update Submodules
echo "🔄 Updating submodules..."
git submodule update --init --recursive

# 2. Setup Python Virtual Environment
echo "🐍 Setting up Python venv..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Initialization complete."
