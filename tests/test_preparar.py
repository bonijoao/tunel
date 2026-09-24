import base64
import re
import shlex
import shutil
import subprocess

import pytest

from app import preparar

HOSTIS = ["/tmp/a b; touch /tmp/pwn'x%y", "/x'; touch /tmp/pwn; '"]
precisa_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash ausente")


def _linha_cron(pasta, auth_key="k; touch /tmp/pwn2", hostname="h$(touch /tmp/pwn3)"):
    script = preparar.gerar_script(pasta, auth_key, hostname)
    trecho = [l for l in script.splitlines() if l.startswith(("D=", "B=", "LINHA="))]
    assert [l[:2] for l in trecho] == ["D=", "B=", "LI"]
    sh_cmd = shutil.which("sh") or "bash"
    r = subprocess.run([sh_cmd, "-c", "\n".join(trecho) + '\nprintf "%s" "$LINHA"'],
                       capture_output=True, text=True, check=True)
    return script, r.stdout


@precisa_bash
@pytest.mark.parametrize("pasta", HOSTIS)
def test_linha_cron_nao_vaza_o_caminho_nem_percent(pasta):
    _, linha = _linha_cron(pasta)
    assert linha.startswith("@reboot ")
    assert "\n" not in linha
    assert "%" not in linha
    assert pasta not in linha
    assert "touch" not in linha


@precisa_bash
@pytest.mark.parametrize("pasta", HOSTIS)
def test_linha_cron_ida_e_volta_do_caminho(pasta):
    _, linha = _linha_cron(pasta)
    b64 = re.search(r"D=\$\(echo (\S+) \| base64 -d\)", linha).group(1)
    assert base64.b64decode(b64).decode() == pasta
    sh_cmd = shutil.which("sh") or "bash"
    r = subprocess.run([sh_cmd, "-c", f'D=$(echo {b64} | base64 -d); printf %s "$D"'],
                       capture_output=True, text=True, check=True)
    assert r.stdout == pasta


@precisa_bash
def test_linha_cron_mantem_d_literal_para_o_cron_expandir():
    _, linha = _linha_cron(HOSTIS[0])
    assert '"$D/tailscaled"' in linha and '--socket="$D/tailscaled.sock"' in linha


@precisa_bash
def test_filtro_de_deduplicacao_casa_com_a_linha_nova():
    script, linha = _linha_cron(HOSTIS[0])
    padrao = re.search(r"grep -v -- '([^']+)'", script).group(1)
    r = subprocess.run(["grep", "-c", "--", padrao], input=linha, capture_output=True, text=True)
    assert r.stdout.strip() == "1"


def test_hostname_e_auth_key_so_na_linha_do_up_e_quotados():
    auth, host = "k; touch /tmp/pwn2", "h$(touch /tmp/pwn3)"
    script = preparar.gerar_script("/x/y", auth, host)
    up = [l for l in script.splitlines() if " up " in l]
    assert len(up) == 1
    assert shlex.quote(auth) in up[0] and shlex.quote(host) in up[0]
    for l in script.splitlines():
        if l.startswith(("LINHA=", "B=")):
            assert "pwn" not in l and "touch" not in l


def test_script_tem_os_passos_essenciais():
    s = preparar.gerar_script("~/joao/tailscale", "tskey-auth-abc", "uni-x")
    assert "--tun=userspace-networking" in s
    assert "@reboot" in s
    assert "pkgs.tailscale.com/stable/tailscale_latest_amd64.tgz" in s
    assert "--hostname=uni-x" in s or "--hostname='uni-x'" in s


def test_script_nao_usa_sudo():
    assert "sudo" not in preparar.gerar_script("~/t", "k", "h")


def test_pasta_com_til_e_expandida_no_home():
    s = preparar.gerar_script("~/joao/tailscale", "k", "h")
    assert '"$HOME"/joao/tailscale' in s
