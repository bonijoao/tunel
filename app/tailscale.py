import os
import shutil
import subprocess

_PADRAO = r"C:\Program Files\Tailscale\tailscale.exe"


def caminho():
    achado = shutil.which("tailscale")
    if achado:
        return achado
    if os.name == "nt" and os.path.exists(_PADRAO):
        return _PADRAO
    return None


def interpretar_status(returncode: int, saida: str) -> str:
    texto = saida.lower()
    if "logged out" in texto:
        return "deslogado"
    if "stopped" in texto:
        return "parado"
    if returncode == 0:
        return "conectado"
    return "desconhecido"


def status() -> str:
    exe = caminho()
    if not exe:
        return "nao_instalado"
    r = subprocess.run([exe, "status"], capture_output=True, text=True, timeout=15)
    return interpretar_status(r.returncode, r.stdout + r.stderr)


def comando_up(auth_key: str) -> list[str]:
    return [caminho() or "tailscale", "up", f"--auth-key={auth_key}"]
