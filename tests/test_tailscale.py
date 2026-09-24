from app import tailscale


def test_conectado():
    assert tailscale.interpretar_status(0, "100.1.1.1  pc  user@  windows  -") == "conectado"


def test_deslogado():
    assert tailscale.interpretar_status(1, "Logged out.") == "deslogado"


def test_parado():
    assert tailscale.interpretar_status(1, "Tailscale is stopped.") == "parado"


def test_saida_estranha():
    assert tailscale.interpretar_status(1, "erro qualquer") == "desconhecido"


def test_sem_binario(monkeypatch):
    monkeypatch.setattr(tailscale, "caminho", lambda: None)
    assert tailscale.status() == "nao_instalado"


def test_comando_up_nao_interpola_shell():
    cmd = tailscale.comando_up("tskey-auth-a; rm -rf ~")
    assert cmd[-1] == "--auth-key=tskey-auth-a; rm -rf ~"
    assert isinstance(cmd, list)


def test_mascarar_troca_a_chave():
    assert tailscale.mascarar("erro com tskey-auth-XYZ aqui", "tskey-auth-XYZ") == "erro com ******** aqui"


def test_mascarar_chave_vazia_nao_altera():
    assert tailscale.mascarar("texto", "") == "texto"
