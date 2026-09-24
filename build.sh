#!/usr/bin/env bash
set -euo pipefail
.venv/bin/pyinstaller --onefile --windowed --name Tunel-LAD --add-data "assets:assets" \
  --collect-all tkinterdnd2 \
  --hidden-import keyring.backends.SecretService --hidden-import keyring.backends.fail run.py
echo "Gerado: dist/Tunel-LAD"
