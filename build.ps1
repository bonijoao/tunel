$ErrorActionPreference = "Stop"
.\.venv\Scripts\pyinstaller --onefile --windowed --name tunel --hidden-import keyring.backends.Windows run.py
Write-Host "Gerado: dist\tunel.exe"
