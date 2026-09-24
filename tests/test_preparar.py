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
