import codecs
import os
import posixpath
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Callable

import paramiko

from app.perfis import Perfil

_INTERPRETES = {".r": "Rscript", ".py": "python3"}


def comando_script(caminho_remoto: str) -> str:
    ext = posixpath.splitext(caminho_remoto)[1].lower()
    if ext not in _INTERPRETES:
        raise ValueError(f"Extensão não suportada: {ext or '(nenhuma)'}. Use .R ou .py.")
    if caminho_remoto.startswith("~/"):
        arg = '"$HOME"' + shlex.quote(caminho_remoto[1:])
    else:
        arg = shlex.quote(caminho_remoto)
    return f"{_INTERPRETES[ext]} {arg}"


def comando_instalar_chave(pub: str) -> str:
    q = shlex.quote(pub.strip())
    return (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        f"(grep -qxF {q} ~/.ssh/authorized_keys || echo {q} >> ~/.ssh/authorized_keys) && "
        "chmod 600 ~/.ssh/authorized_keys"
    )


def comando_terminal(perfil: Perfil, chave) -> list[str]:
    cmd = ["ssh"]
    if chave:
        cmd += ["-i", str(chave)]
    return cmd + ["--", f"{perfil.login}@{perfil.host}"]


def traduzir_erro(exc: Exception) -> str:
    if isinstance(exc, paramiko.AuthenticationException):
        return "Login ou senha incorretos. Confira as credenciais deste PC."
    if isinstance(exc, FileNotFoundError):
        return f"Arquivo ou pasta não encontrado (local ou no PC remoto): {exc}"
    if isinstance(exc, PermissionError):
        return f"Sem permissão para acessar o arquivo ou pasta: {exc}"
    if isinstance(exc, paramiko.SSHException):
        if "No authentication methods available" in str(exc):
            return "Nenhum método de autenticação disponível. Preencha a senha ou instale uma chave SSH."
        return f"Falha na negociação SSH: {exc}"
    if isinstance(exc, RuntimeError):
        return f"Erro na operação remota: {exc}"
    if isinstance(exc, (TimeoutError, OSError)):
        return ("Não consegui alcançar o PC. Confira: o Tailscale está ligado e logado "
                "neste computador? O IP/nome está correto? O PC da universidade está ligado?")
    return f"Erro inesperado: {exc}"


def garantir_chave(pasta=None):
    pasta = Path(pasta) if pasta else Path.home() / ".ssh"
    priv = pasta / "id_ed25519"
    pasta.mkdir(parents=True, exist_ok=True)
    if not priv.exists():
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(priv)], check=True)
    return priv, (pasta / "id_ed25519.pub").read_text(encoding="utf-8").strip()


def conectar(perfil: Perfil, senha=None, chave=None, timeout: int = 10) -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    # Escolha deliberada: o tráfego normalmente passa pelo Tailscale/WireGuard, que já autentica
    # o par; no uso direto pela rede local a chave do servidor é aceita na primeira conexão.
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(
        perfil.host, username=perfil.login, password=senha,
        key_filename=str(chave) if chave else None,
        timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
        look_for_keys=False, allow_agent=False,
    )
    return cli


def instalar_chave(perfil: Perfil, senha: str) -> None:
    _, pub = garantir_chave()
    cli = conectar(perfil, senha=senha)
    try:
        _, out, err = cli.exec_command(comando_instalar_chave(pub))
        if out.channel.recv_exit_status() != 0:
            raise RuntimeError(err.read().decode(errors="replace"))
    finally:
        cli.close()


def resolver_remoto(cli, caminho: str) -> str:
    if caminho == "~" or caminho.startswith("~/"):
        _, out, _ = cli.exec_command("echo $HOME")
        home = out.read().decode().strip()
        return home + caminho[1:]
    return caminho


def enviar(cli, local: str, remoto: str) -> None:
    sftp = cli.open_sftp()
    try:
        sftp.put(local, resolver_remoto(cli, remoto))
    finally:
        sftp.close()


def baixar(cli, remoto: str, local: str) -> None:
    sftp = cli.open_sftp()
    try:
        sftp.get(resolver_remoto(cli, remoto), local)
    finally:
        sftp.close()


def _garantir_dir_remoto(sftp, caminho: str) -> None:
    try:
        sftp.stat(caminho)
    except (IOError, OSError):
        sftp.mkdir(caminho)


def _enviar_rec(sftp, local: str, remoto: str) -> None:
    _garantir_dir_remoto(sftp, remoto)
    for nome in sorted(os.listdir(local)):
        origem = os.path.join(local, nome)
        if os.path.islink(origem):
            continue
        destino = posixpath.join(remoto, nome)
        if os.path.isdir(origem):
            _enviar_rec(sftp, origem, destino)
        elif os.path.isfile(origem):
            sftp.put(origem, destino)


def enviar_pasta(cli, local_dir: str, remoto_dir: str) -> None:
    sftp = cli.open_sftp()
    try:
        _enviar_rec(sftp, local_dir, resolver_remoto(cli, remoto_dir))
    finally:
        sftp.close()


def _baixar_rec(sftp, remoto: str, local: str) -> None:
    os.makedirs(local, exist_ok=True)
    for attr in sftp.listdir_attr(remoto):
        origem = posixpath.join(remoto, attr.filename)
        destino = os.path.join(local, attr.filename)
        if stat.S_ISLNK(attr.st_mode):
            continue
        if stat.S_ISDIR(attr.st_mode):
            _baixar_rec(sftp, origem, destino)
        elif stat.S_ISREG(attr.st_mode):
            sftp.get(origem, destino)


def baixar_pasta(cli, remoto_dir: str, local_dir: str) -> None:
    sftp = cli.open_sftp()
    try:
        _baixar_rec(sftp, resolver_remoto(cli, remoto_dir), local_dir)
    finally:
        sftp.close()


def ler_canal(canal, ao_receber: Callable[[str], None]) -> int:
    dec = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def _emitir(dados: bytes) -> None:
        texto = dec.decode(dados)
        if texto:
            ao_receber(texto)

    while True:
        if canal.recv_ready():
            _emitir(canal.recv(4096))
        elif canal.exit_status_ready():
            while canal.recv_ready():
                _emitir(canal.recv(4096))
            resto = dec.decode(b"", final=True)
            if resto:
                ao_receber(resto)
            return canal.recv_exit_status()
        else:
            canal.status_event.wait(0.1)


def executar(cli, comando: str, ao_receber: Callable[[str], None]) -> int:
    canal = cli.get_transport().open_session()
    canal.set_combine_stderr(True)
    canal.exec_command(comando)
    return ler_canal(canal, ao_receber)


_EMULADORES = (
    ("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--"]), ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]), ("xterm", ["-e"]),
)


def comando_janela_terminal(cmd, sistema, achar):
    if sistema == "nt":
        return ["cmd", "/c", "start", "", *cmd]
    for nome, flag in _EMULADORES:
        if achar(nome):
            return [nome, *flag, *cmd]
    raise RuntimeError("Nenhum terminal gráfico encontrado. Instale gnome-terminal, konsole ou xterm.")


def abrir_terminal(perfil: Perfil, chave=None) -> None:
    cmd = comando_janela_terminal(comando_terminal(perfil, chave), os.name, shutil.which)
    subprocess.Popen(cmd)
