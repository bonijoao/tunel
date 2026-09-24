import os
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


def test_metacaracteres_ficam_quotados_no_auth():
    """Auth key and hostname with special chars are shlex.quoted on the up command."""
    s = preparar.gerar_script("/tmp/safe", "k; touch /tmp/pwn", "h; rm /")
    # Find the up line
    up_line = [line for line in s.split("\n") if "--auth-key=" in line and "up" in line][0]
    # Auth key should be quoted (shlex.quote adds quotes)
    assert "'k; touch /tmp/pwn'" in up_line or '"k; touch /tmp/pwn"' in up_line
    # Hostname should be quoted
    assert "'h; rm /'" in up_line or '"h; rm /"' in up_line


def test_pasta_com_til_e_expandida_no_home():
    s = preparar.gerar_script("~/joao/tailscale", "k", "h")
    assert '"$HOME"/joao/tailscale' in s


def test_cron_uses_base64_not_sed():
    """Cron line must use base64 encoding, not sed."""
    s = preparar.gerar_script("/tmp/test", "k", "h")
    # Should use base64 encoding
    assert "base64" in s
    # Should NOT have sed command that was in v1 (D_QUOTED/sed approach)
    before_linha = s.split("LINHA=")[0]
    assert "sed" not in before_linha, "sed should not be used for D_QUOTED"


def test_cron_line_no_percent_signs():
    """The crontab LINHA should not contain unescaped % (cron line separator)."""
    s = preparar.gerar_script("/tmp/a%b; echo test", "key", "host")
    # Extract LINHA
    match = re.search(r"LINHA='(.+?)'", s, re.DOTALL)
    assert match, "LINHA definition not found"
    linha = match.group(1)
    # % should not appear (it's encoded in base64)
    assert "%" not in linha, "LINHA contains unescaped %, cron will treat as newline"


def test_cron_line_no_raw_pasta():
    """The LINHA should not contain the raw, unencoded path."""
    paths = [
        "/tmp/a b; touch /tmp/pwn",
        "/tmp/a%b",
        "/x'; touch /tmp/pwn; '",
    ]
    for pasta in paths:
        s = preparar.gerar_script(pasta, "key", "host")
        linha_match = re.search(r"LINHA='(.+?)'", s, re.DOTALL)
        assert linha_match
        linha = linha_match.group(1)
        # Raw path must not appear in LINHA (should be base64-encoded)
        assert pasta not in linha, f"Raw path {pasta} found in LINHA"


def test_cron_contains_base64_decode():
    """LINHA should contain D=$(echo ... | base64 -d) to decode at runtime."""
    s = preparar.gerar_script("/tmp/test", "k", "h")
    # Should have base64 -d in LINHA to decode
    assert "base64 -d" in s, "base64 -d not found"
    # Pattern: D=$(echo 'base64value' | base64 -d)
    assert re.search(r"D=\$\(echo '.*?' \| base64 -d\)", s), "base64 decode pattern not found"


def test_deduplicate_grep_still_works():
    """The grep -v filter for de-duplication should still match LINHA."""
    s = preparar.gerar_script("/tmp/test", "key", "host")
    # LINHA should contain the strings that grep -v looks for
    assert "tailscaled" in s
    assert "--tun=userspace" in s
    # Verify grep pattern
    assert re.search(r"grep -v 'tailscaled --tun=userspace'", s)
