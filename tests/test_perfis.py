import pytest
import json
from app import perfis
from app.perfis import Perfil


def test_salvar_e_carregar_preserva_nomes_estranhos(tmp_path):
    lista = [Perfil('PC "do" João, sala 3', "10.0.0.1", "fulano", "~/Documents/x y")]
    perfis.salvar(lista, tmp_path)
    assert perfis.carregar(tmp_path) == lista


def test_carregar_sem_arquivo_devolve_lista_vazia(tmp_path):
    assert perfis.carregar(tmp_path) == []


def test_arquivo_nunca_contem_senha(tmp_path, monkeypatch):
    guardado = {}
    monkeypatch.setattr(perfis.keyring, "set_password", lambda s, u, p: guardado.update({(s, u): p}))
    p = Perfil("a", "h", "u")
    perfis.guardar_senha(p, "segredo123")
    perfis.salvar([p], tmp_path)
    assert "segredo123" not in (tmp_path / "perfis.json").read_text(encoding="utf-8")
    assert "segredo123" in guardado.values()


def test_sem_cofre_nao_quebra(monkeypatch):
    def falha(*a):
        raise perfis.keyring.errors.NoKeyringError()
    monkeypatch.setattr(perfis.keyring, "set_password", falha)
    monkeypatch.setattr(perfis.keyring, "get_password", falha)
    p = Perfil("a", "h", "u")
    assert perfis.guardar_senha(p, "x") is False
    assert perfis.ler_senha(p) is None


def test_pasta_de_config_no_linux(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert perfis._base(None, sistema="posix") == tmp_path / "tunel"


def test_ler_e_apagar_senha(monkeypatch):
    cofre = {}
    monkeypatch.setattr(perfis.keyring, "set_password", lambda s, u, p: cofre.__setitem__((s, u), p))
    monkeypatch.setattr(perfis.keyring, "get_password", lambda s, u: cofre.get((s, u)))
    monkeypatch.setattr(perfis.keyring, "delete_password", lambda s, u: cofre.pop((s, u), None))
    p = Perfil("a", "h", "u")
    perfis.guardar_senha(p, "x")
    assert perfis.ler_senha(p) == "x"
    perfis.apagar_senha(p)
    assert perfis.ler_senha(p) is None


@pytest.mark.parametrize("login,host", [
    ("fulano", "100.64.0.1"), ("fu.lano_x@dom-1", "pc-uni.rede.ts.net"), ("u", "fd7a:115c::1"),
])
def test_validar_aceita(login, host):
    assert perfis.validar(perfis.Perfil("n", host, login)) is None


@pytest.mark.parametrize("login,host", [
    ("", "h"), ("u", ""), ("-oProxy", "h"), ("u", "-h"), ("a b", "h"), ("u", "h;rm"),
    ("u;x", "h"), ("u", "h h"), ("u$(x)", "h"),
])
def test_validar_recusa(login, host):
    assert isinstance(perfis.validar(perfis.Perfil("n", host, login)), str)
