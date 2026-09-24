import re
import shlex
import shutil
import subprocess

import pytest

from app import preparar


def test_script_tem_os_passos_essenciais():
    s = preparar.gerar_script("~/joao/tailscale", "tskey-auth-abc", "uni-x")
    assert "--tun=userspace-networking" in s
    assert "@reboot" in s
    assert "pkgs.tailscale.com/stable/tailscale_latest_amd64.tgz" in s
    assert "--hostname=uni-x" in s or "--hostname='uni-x'" in s


def test_script_nao_usa_sudo():
    assert "sudo" not in preparar.gerar_script("~/t", "k", "h")


def test_metacaracteres_ficam_quotados():
    s = preparar.gerar_script("/tmp/a b; touch /tmp/pwn", "k; touch /tmp/pwn2", "h")
    assert "'/tmp/a b; touch /tmp/pwn'" in s
    assert "'k; touch /tmp/pwn2'" in s
    assert "\ntouch /tmp/pwn" not in s


def test_pasta_com_til_e_expandida_no_home():
    s = preparar.gerar_script("~/joao/tailscale", "k", "h")
    assert '"$HOME"/joao/tailscale' in s


def test_cron_line_nao_expande_dollar_signs():
    """Cron line must use D_QUOTED (quoted) not unquoted $D."""
    s = preparar.gerar_script("/tmp/a b; touch /tmp/pwn", "k", "h")
    # Should define D_QUOTED using sed
    assert "D_QUOTED=" in s
    assert "sed" in s
    # LINHA should use D_QUOTED not raw $D
    assert "LINHA=" in s
    match = re.search(r"LINHA=\"(.+?)\"", s, re.DOTALL)
    assert match, "LINHA definition not found"
    linha = match.group(1)
    # The line should quote the paths using D_QUOTED
    assert "'$D_QUOTED'" in s or "'$D_QUOTED'/" in s


def test_cron_line_escapa_aspas_simples():
    """Cron line sed must handle single quotes correctly."""
    s = preparar.gerar_script("/tmp/a'b", "k", "h")
    # Should have the sed command that replaces ' with '\''
    assert "sed" in s
    assert "s/'/'\\\\''/g" in s


def test_cron_line_escapa_percent():
    """Cron line sed must escape % (special in cron)."""
    s = preparar.gerar_script("/tmp/a%b", "k", "h")
    # Should have sed that replaces % with \%
    assert "sed" in s
    assert "s/%/\\\\%/g" in s


def test_hostname_com_metacaracteres_nao_injeta():
    """Hostname with special chars should be properly quoted."""
    s = preparar.gerar_script("~/t", "k", "h; rm -rf /")
    # The hostname should be quoted in the auth command
    # Either as explicit shlex.quote or inside quotes
    auth_line = [line for line in s.split("\n") if "--hostname=" in line][0]
    assert "--hostname=" in auth_line
    # Should not have unquoted semicolon after hostname
    assert "hostname=h;" not in auth_line or "--hostname='h; rm" in auth_line or '--hostname="h;' in auth_line


def test_auth_key_com_metacaracteres_nao_injeta():
    """Auth key with special chars should be properly quoted."""
    s = preparar.gerar_script("~/t", "k$; touch /tmp/x", "h")
    # The auth key should be quoted
    auth_line = [line for line in s.split("\n") if "--auth-key=" in line][0]
    assert "--auth-key=" in auth_line
    # Should not have unquoted semicolon after key
    assert "--auth-key=k$;" not in auth_line or "--auth-key=" in auth_line


def test_cron_line_contains_d_quoted_variable():
    """LINHA should use D_QUOTED variable, not raw $D."""
    s = preparar.gerar_script("/tmp/dangerous; rm -rf /", "key", "host")
    # Should have the D_QUOTED definition
    assert "D_QUOTED=$(printf '%s" in s
    # LINHA should reference $D_QUOTED, not $D
    linha_match = re.search(r'LINHA="(.+?)"', s, re.DOTALL)
    assert linha_match
    linha = linha_match.group(1)
    # Should use $D_QUOTED, not $D without quotes
    assert "$D_QUOTED" in linha
    # Should not have unquoted $D followed by /
    assert "$D/" not in linha or "$D_QUOTED/" in linha or "'$D_QUOTED'" in linha
