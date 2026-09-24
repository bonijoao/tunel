import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import keyring

SERVICO = "tunel"


@dataclass
class Perfil:
    nome: str
    host: str
    login: str
    pasta_remota: str = "~"


_LOGIN_OK = re.compile(r"[A-Za-z0-9._@-]+")
_HOST_OK = re.compile(r"[A-Za-z0-9.:_-]+")


def validar(p: Perfil):
    """Devolve o texto do erro (em português) ou None se login e host são aceitáveis."""
    if not p.login or not p.host:
        return "Preencha Host/IP e Login."
    if p.login.startswith("-") or not _LOGIN_OK.fullmatch(p.login):
        return "Login inválido: use apenas letras, números e . _ @ - (sem começar com '-')."
    if p.host.startswith("-") or not _HOST_OK.fullmatch(p.host):
        return "Host inválido: use apenas letras, números e . : _ - (sem começar com '-')."
    return None


def _base(base, sistema=None):
    if base is not None:
        return Path(base)
    if (sistema or os.name) == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "tunel"
    xdg = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(xdg) / "tunel"


def carregar(base=None) -> list[Perfil]:
    arq = _base(base) / "perfis.json"
    if not arq.exists():
        return []
    return [Perfil(**d) for d in json.loads(arq.read_text(encoding="utf-8"))]


def salvar(perfis: list[Perfil], base=None) -> None:
    pasta = _base(base)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "perfis.json").write_text(
        json.dumps([asdict(p) for p in perfis], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _usuario(p: Perfil) -> str:
    return f"{p.login}@{p.host}"


def guardar_senha(p: Perfil, senha: str) -> bool:
    try:
        keyring.set_password(SERVICO, _usuario(p), senha)
        return True
    except keyring.errors.KeyringError:
        return False


def ler_senha(p: Perfil):
    try:
        return keyring.get_password(SERVICO, _usuario(p))
    except keyring.errors.KeyringError:
        return None


def apagar_senha(p: Perfil) -> None:
    try:
        keyring.delete_password(SERVICO, _usuario(p))
    except keyring.errors.KeyringError:
        pass
