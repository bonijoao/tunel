$ErrorActionPreference = "Stop"
.\.venv\Scripts\pyinstaller --onefile --windowed --name Tunel-LAD --icon assets\icone.ico `
  --add-data "assets;assets" --collect-all tkinterdnd2 `
  --hidden-import keyring.backends.Windows run.py
Write-Host "Gerado: dist\Tunel-LAD.exe"
