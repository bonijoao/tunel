import tkinter as tk

import pytest

from app import perfis
from tests.fakes import FakeSftp

HOME = "/home/fulano"
PASTA = HOME + "/projeto"


class FakeSessao:
    def __init__(self):
        self._sftp = FakeSftp()
        self._sftp.pasta(PASTA)
        self._sftp.arquivo(PASTA + "/x.py", b"print(1)")
        self._sftp.arquivo(PASTA + "/relatório final.txt", b"dados")
        self._sftp.pasta(PASTA + "/pasta com espaço")
        self._sftp.arquivo(PASTA + "/pasta com espaço/dentro.txt", b"z")
        self.falhar = False
        self.fechada = False

    def conectar(self):
        pass

    def conectado(self):
        return True

    def obter(self):
        return object()

    def sftp(self):
        if self.falhar:
            raise RuntimeError("falha simulada")
        return self._sftp

    def home(self):
        return HOME

    def fechar(self):
        self.fechada = True


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    try:
        raiz = tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")
    monkeypatch.setenv("APPDATA", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setattr(perfis, "guardar_senha", lambda p, s: True)
    monkeypatch.setattr(perfis, "ler_senha", lambda p: None)
    monkeypatch.setattr(perfis, "apagar_senha", lambda p: None)
    from app.ui import dialogos, janela
    fake = FakeSessao()
    comandos = []

    def executar(cli, cmd, ao_receber):
        comandos.append(cmd)
        ao_receber("olá\n")
        return 0

    respostas = []
    monkeypatch.setattr(janela, "Sessao", lambda abrir: fake)
    monkeypatch.setattr(janela.ssh, "executar", executar)
    monkeypatch.setattr(dialogos, "confirmar_apagar", lambda *a, **k: True)
    monkeypatch.setattr(dialogos, "perguntar_conflito", lambda *a, **k: ("substituir", False))
    monkeypatch.setattr(janela.simpledialog, "askstring", lambda *a, **k: respostas.pop(0))
    j = janela.JanelaPrincipal(raiz, None)
    j.barra.v["host"].set("servidor.exemplo")
    j.barra.v["login"].set("fulano")
    j.barra.v["pasta"].set("~/projeto")
    try:
        yield j, fake, comandos, respostas
    finally:
        raiz.destroy()


def esperar(j, pred, timeout=8.0):
    """Roda o mainloop até pred() valer (checado a cada 20 ms); falha no timeout."""
    estado = {"ok": False, "t": 0.0}

    def checar():
        try:
            ok = pred()
        except Exception:
            ok = False
        estado["t"] += 0.02
        if ok:
            estado["ok"] = True
            j.raiz.quit()
        elif estado["t"] >= timeout:
            j.raiz.quit()
        else:
            j.raiz.after(20, checar)

    j.raiz.after(20, checar)
    j.raiz.mainloop()
    assert estado["ok"], "tempo esgotado; log:\n" + texto(j)


def texto(j):
    return j.log.texto.get("1.0", "end")


def ocioso(j):
    """Fila vazia e callbacks pendentes já executados (usa um 'tique' extra)."""
    marca = {"v": False}
    esperar(j, lambda: j.fila._q.unfinished_tasks == 0)
    j.raiz.after(60, lambda: marca.__setitem__("v", True))
    esperar(j, lambda: marca["v"])


def selecionar(painel, nomes):
    ids = [i for i, e in painel._entradas.items() if e.nome in nomes]
    assert len(ids) == len(nomes), (nomes, [e.nome for e in painel._entradas.values()])
    painel.arvore.selection_set(ids)


def entrada(painel, nome):
    return next(e for e in painel._entradas.values() if e.nome == nome)


def conectar(j):
    j.conectar()
    esperar(j, lambda: "Conectado:" in j.barra.estado.get() and j.remoto.caminho_atual() == PASTA)


def test_fluxos_completos(ambiente, tmp_path):
    j, fake, comandos, respostas = ambiente
    sftp = fake._sftp

    # (1) conectar
    conectar(j)
    nomes = [e.nome for e in j.remoto._entradas.values()]
    assert "x.py" in nomes and "relatório final.txt" in nomes and "pasta com espaço" in nomes
    assert j.conectado() is True

    # (2) enviar
    origem = tmp_path / "origem"
    (origem / "sub dir").mkdir(parents=True)
    (origem / "a b.txt").write_text("um")
    (origem / "ção.txt").write_text("dois")
    (origem / "sub dir" / "f.txt").write_text("tres")
    j._pedir_local(str(origem))
    selecionar(j.local, ["a b.txt", "ção.txt", "sub dir"])
    j.enviar()
    esperar(j, lambda: "Enviado(s): 3" in texto(j))
    assert sftp.conteudo(PASTA + "/a b.txt") == b"um"
    assert sftp.conteudo(PASTA + "/ção.txt") == b"dois"
    assert sftp.conteudo(PASTA + "/sub dir/f.txt") == b"tres"
    ocioso(j)
    assert "sub dir" in [e.nome for e in j.remoto._entradas.values()]

    # (3) baixar
    baixados = tmp_path / "baixados"
    baixados.mkdir()
    j._pedir_local(str(baixados))
    selecionar(j.remoto, ["relatório final.txt", "pasta com espaço"])
    j.baixar()
    esperar(j, lambda: "Baixado(s): 2" in texto(j))
    assert (baixados / "relatório final.txt").read_bytes() == b"dados"
    assert (baixados / "pasta com espaço" / "dentro.txt").read_bytes() == b"z"

    # (4) renomear / nova pasta / mover / apagar
    ocioso(j)
    selecionar(j.remoto, ["a b.txt"])
    respostas.append("novo nome.txt")
    j.renomear()
    esperar(j, lambda: "Renomeado: a b.txt -> novo nome.txt" in texto(j))
    assert PASTA + "/novo nome.txt" in sftp.itens and PASTA + "/a b.txt" not in sftp.itens

    respostas.append("nova pasta")
    j.nova_pasta()
    esperar(j, lambda: "Pasta criada: nova pasta" in texto(j))
    assert sftp.itens[PASTA + "/nova pasta"] == ("dir",)

    ocioso(j)
    selecionar(j.remoto, ["novo nome.txt"])
    respostas.append(PASTA + "/nova pasta")
    j.mover_para()
    esperar(j, lambda: "Mover: 1 item(ns) processado(s)." in texto(j))
    assert PASTA + "/nova pasta/novo nome.txt" in sftp.itens
    assert PASTA + "/novo nome.txt" not in sftp.itens

    ocioso(j)
    selecionar(j.remoto, ["nova pasta"])
    j.apagar()
    esperar(j, lambda: "Apagado(s): 1" in texto(j))
    assert PASTA + "/nova pasta" not in sftp.itens
    assert PASTA + "/nova pasta/novo nome.txt" not in sftp.itens

    # apagar a própria pasta do perfil: recusado
    j._pedir_remoto(HOME)
    esperar(j, lambda: j.remoto.caminho_atual() == HOME)
    selecionar(j.remoto, ["projeto"])
    antes = sftp.caminhos()
    j.apagar()
    esperar(j, lambda: "Recusado por segurança" in texto(j))
    ocioso(j)
    assert sftp.caminhos() == antes
    assert "ERRO:" in texto(j)

    # (5) rodar
    j._pedir_remoto(PASTA)
    esperar(j, lambda: j.remoto.caminho_atual() == PASTA)
    selecionar(j.remoto, ["x.py"])
    j.rodar()
    esperar(j, lambda: "[terminou com código 0]" in texto(j))
    assert comandos == [f"cd {PASTA} && python3 ./x.py"]
    assert "olá" in texto(j)

    # (7) soltar local -> pasta remota
    j._pedir_local(str(origem))
    ocioso(j)
    selecionar(j.local, ["ção.txt"])
    alvo = entrada(j.remoto, "pasta com espaço")
    j._ao_soltar(j.local, j.local.selecionados(), j.remoto, alvo)
    esperar(j, lambda: PASTA + "/pasta com espaço/ção.txt" in sftp.itens)

    # (6) falha: linha ERRO em português e a fila continua funcionando
    fake.falhar = True
    j._atualizar_remoto()
    esperar(j, lambda: "ERRO:" in texto(j).split("Recusado", 1)[1])
    fake.falhar = False
    ocioso(j)
    respostas.append("depois do erro")
    j.nova_pasta()
    esperar(j, lambda: "Pasta criada: depois do erro" in texto(j))
    assert PASTA + "/depois do erro" in sftp.itens
