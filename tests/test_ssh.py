import pytest
from app import ssh
from app.perfis import Perfil


def test_script_r_e_python():
    assert ssh.comando_script("~/a/x.R") == 'Rscript "$HOME"/a/x.R'
    assert ssh.comando_script("/tmp/y.PY") == "python3 /tmp/y.PY"


def test_script_com_til_nao_deixa_metacaractere_solto():
    assert ssh.comando_script("~/a;rm -rf x/y.py") == "python3 \"$HOME\"'/a;rm -rf x/y.py'"


def test_script_com_espacos_e_quotado():
    assert ssh.comando_script("/tmp/meu script.py") == "python3 '/tmp/meu script.py'"


def test_script_extensao_desconhecida():
    with pytest.raises(ValueError, match="Extensão não suportada"):
        ssh.comando_script("/tmp/a.txt")


def test_instalar_chave_quota_e_e_idempotente():
    cmd = ssh.comando_instalar_chave("ssh-ed25519 AAAA x'y@pc")
    assert "'" in cmd and "x'y" not in cmd.replace("'\"'\"'", "")
    assert "grep -qxF" in cmd
    assert "chmod 600" in cmd


def test_comando_terminal_com_chave():
    p = Perfil("n", "100.1.1.1", "geraldo")
    cmd = ssh.comando_terminal(p, "C:/k/id")
    assert cmd[-1] == "geraldo@100.1.1.1"
    assert "-i" in cmd and "C:/k/id" in cmd


def test_janela_terminal_windows():
    r = ssh.comando_janela_terminal(["ssh", "u@h"], "nt", lambda n: None)
    assert r[:3] == ["cmd", "/c", "start"] and r[-2:] == ["ssh", "u@h"]


def test_janela_terminal_linux_escolhe_primeiro_disponivel():
    achados = {"gnome-terminal": "/usr/bin/gnome-terminal"}
    r = ssh.comando_janela_terminal(["ssh", "u@h"], "posix", achados.get)
    assert r[0] == "gnome-terminal" and r[-2:] == ["ssh", "u@h"]


def test_janela_terminal_linux_sem_emulador():
    with pytest.raises(RuntimeError, match="terminal"):
        ssh.comando_janela_terminal(["ssh", "u@h"], "posix", lambda n: None)


def test_comando_terminal_sem_chave():
    cmd = ssh.comando_terminal(Perfil("n", "h", "u"), None)
    assert "-i" not in cmd


@pytest.mark.parametrize("exc,trecho", [
    (TimeoutError(), "Tailscale"),
    (OSError("Network is unreachable"), "Tailscale"),
])
def test_traduzir_erro_rede(exc, trecho):
    assert trecho in ssh.traduzir_erro(exc)


def test_traduzir_erro_autenticacao():
    import paramiko
    assert "senha" in ssh.traduzir_erro(paramiko.AuthenticationException()).lower()
