import base64
import re
import shlex
import shutil
import subprocess

import pytest

from app import preparar

HOSTIS = ["/tmp/a b; touch /tmp/pwn'x%y", "/x'; touch /tmp/pwn; '"]
precisa_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash ausente")


def _trecho(script, prefixos):
    """Linhas do script por prefixo exato; da atribuição D= só a primeira (a da pasta)."""
    linhas, visto_d = [], False
    for l in script.splitlines():
        if l.startswith("D="):
            if visto_d:
                continue
            visto_d = True
        if l.startswith(prefixos):
            linhas.append(l)
    return linhas


def _linha_cron(pasta, auth_key="k; touch /tmp/pwn2", hostname="h$(touch /tmp/pwn3)"):
    script = preparar.gerar_script(pasta, auth_key, hostname)
    trecho = _trecho(script, ("D=", "B=", "LINHA="))
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
    assert shlex.quote(host) in up[0] and shlex.quote(auth) not in up[0]
    chave = [l for l in script.splitlines() if l.startswith("( umask 077; printf %s ")]
    assert len(chave) == 1 and shlex.quote(auth) in chave[0]
    assert sum(shlex.quote(auth) in l for l in script.splitlines()) == 1
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


def _crontab_falso(tmp_path, fixture):
    import os
    entrada, saida = tmp_path / "entrada", tmp_path / "saida"
    if fixture is not None:
        entrada.write_text(fixture, encoding="utf-8")
    fn = ('crontab() { if [ "$1" = "-l" ]; then '
          'if [ -f "$CRON_IN" ]; then cat "$CRON_IN"; else echo "no crontab for x" >&2; return 1; fi; '
          'else cat > "$CRON_OUT"; fi; }\n')
    env = dict(os.environ, CRON_IN=str(entrada), CRON_OUT=str(saida))
    return fn, env, saida


ANTIGA = "@reboot D=$(echo QQ== | base64 -d); nohup setsid \"$D/tailscaled\" --tun=userspace-networking --state=x &\n"


@precisa_bash
@pytest.mark.parametrize("fixture,outras", [
    (None, []),
    (ANTIGA, []),
    ("0 5 * * * /usr/bin/backup\n" + ANTIGA + "30 6 * * 1 /bin/outra\n",
     ["0 5 * * * /usr/bin/backup", "30 6 * * 1 /bin/outra"]),
])
def test_crontab_instala_uma_linha_reboot(tmp_path, fixture, outras):
    script = preparar.gerar_script("/x/y", "k", "h")
    fn, env, saida = _crontab_falso(tmp_path, fixture)
    pipeline = [l for l in script.splitlines() if l.startswith("( crontab")]
    assert len(pipeline) == 1
    linhas = _trecho(script, ("D=", "B=", "LINHA=", "( crontab"))
    sh_cmd = shutil.which("sh") or "bash"
    r = subprocess.run([sh_cmd, "-c", "set -e\n" + fn + "\n".join(linhas)],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    instaladas = saida.read_text(encoding="utf-8").splitlines()
    assert len([l for l in instaladas if l.startswith("@reboot")]) == 1
    assert "--tun=userspace-networking" in [l for l in instaladas if l.startswith("@reboot")][0]
    assert "QQ==" not in "".join(instaladas)
    assert [l for l in instaladas if not l.startswith("@reboot")] == outras


@precisa_bash
def test_pasta_relativa_vira_caminho_absoluto_no_cron(tmp_path):
    import os
    script = preparar.gerar_script("rel/ts", "k", "h")
    linhas = script.splitlines()
    i_cd = linhas.index('cd "$D"')
    assert linhas[i_cd + 1] == 'D=$(pwd -P)'
    sel = [linhas[1], 'mkdir -p "$D/state"', 'cd "$D"', 'D=$(pwd -P)']
    sel += [l for l in linhas if l.startswith(("B=", "LINHA="))]
    assert linhas[1].startswith("D=")
    sh_cmd = shutil.which("sh") or "bash"
    r = subprocess.run([sh_cmd, "-c", "set -e\n" + "\n".join(sel) + '\nprintf "%s" "$LINHA"'],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    b64 = re.search(r"D=\$\(echo (\S+) \| base64 -d\)", r.stdout).group(1)
    assert base64.b64decode(b64).decode().startswith("/")


def test_auth_key_nao_aparece_em_argv():
    auth = "tskey-auth-SEGREDO"
    script = preparar.gerar_script("/x/y", auth, "h")
    assert "--auth-key=" + auth not in script
    assert "--auth-key=" + shlex.quote(auth) not in script
    assert '--auth-key=file:"$D/.authkey"' in script
    assert "trap 'rm -f \"$D/.authkey\"' EXIT" in script
    assert f'printf %s {shlex.quote(auth)} > "$D/.authkey"' in script
    assert 'rm -f "$D/.authkey"' in script
