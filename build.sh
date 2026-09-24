#!/usr/bin/env bash
set -euo pipefail
.venv/bin/pyinstaller --onefile --windowed --name tunel \n  --hidden-import keyring.backends.SecretService --hidden-import keyring.backends.fail run.py
echo "Gerado: dist/tunel"
