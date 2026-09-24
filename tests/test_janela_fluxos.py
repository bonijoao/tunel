import gc
import threading
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
        self.falhar_home = False
        self.trava = None          # Event: faz conectar() esperar até ser liberado
        self.fechada = False

    def conectar(self):
        if self.trava is not None:
            self.trava.wait(8)

    def conectado(self):
        return True

    def obter(self):
        return object()

    def sftp(self):
        if self.falhar:
            raise RuntimeError("falha simulada")
        return self._sftp

    def home(self):
        if self.falhar_home:
            raise RuntimeError("Não consegui descobrir a pasta pessoal no PC remoto.")
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
    _emular_linux(raiz)
    j.barra.v["host"].set("servidor.exemplo")
    j.barra.v["login"].set("fulano")
    j.barra.v["pasta"].set("~/projeto")
    try:
        yield j, fake, comandos, respostas
    finally:
        gc.collect()        # solta as variáveis Tk com a raiz ainda viva (evita Variable.__del__ tardio)
        raiz.destroy()


def _emular_linux(raiz):
    """Como no Linux/CI: `after` chamado de outra thread fora do mainloop falha na hora (no Windows ele espera)."""
    raiz._rodando = False
    original = raiz.after

    def after(ms, func=None, *args):
        if threading.current_thread() is not threading.main_thread() and not raiz._rodando:
            raise RuntimeError("main thread is not in main loop")
        return original(ms, func, *args) if func is not None else original(ms)
    raiz.after = after


def esperar(j, pred, timeout=8.0, acao=None):
    """Roda o mainloop até pred() valer (checado a cada 20 ms); falha no timeout.

    `acao` roda DENTRO do mainloop (como o clique de um usuário): a thread da fila só pode usar `after` com ele ativo."""
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
    if acao is not None:
        j.raiz.after(0, acao)
    j.raiz._rodando = True
    try:
        j.raiz.mainloop()
    finally:
        j.raiz._rodando = False
    assert estado["ok"], "tempo esgotado; log:\n" + texto(j)


def texto(j):
    return j.log.texto.get("1.0", "end")


def ocioso(j, acao=None):
    """Fila vazia e callbacks pendentes já executados (usa um 'tique' extra)."""
    marca = {"v": False}
    esperar(j, lambda: j.fila._q.unfinished_tasks == 0, acao=acao)
    j.raiz.after(60, lambda: marca.__setitem__("v", True))
    esperar(j, lambda: marca["v"])


def selecionar(painel, nomes):
    ids = [i for i, e in painel._entradas.items() if e.nome in nomes]
    assert len(ids) == len(nomes), (nomes, [e.nome for e in painel._entradas.values()])
    painel.arvore.selection_set(ids)


def entrada(painel, nome):
    return next(e for e in painel._entradas.values() if e.nome == nome)


def conectar(j):
    esperar(j, lambda: "Conectado:" in j.barra.estado.get() and j.remoto.caminho_atual() == PASTA,
            acao=j.conectar)


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
    esperar(j, lambda: "Enviado(s): 3" in texto(j), acao=j.enviar)
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
    esperar(j, lambda: "Baixado(s): 2" in texto(j), acao=j.baixar)
    assert (baixados / "relatório final.txt").read_bytes() == b"dados"
    assert (baixados / "pasta com espaço" / "dentro.txt").read_bytes() == b"z"

    # (4) renomear / nova pasta / mover / apagar
    ocioso(j)
    selecionar(j.remoto, ["a b.txt"])
    respostas.append("novo nome.txt")
    esperar(j, lambda: "Renomeado: a b.txt -> novo nome.txt" in texto(j), acao=j.renomear)
    assert PASTA + "/novo nome.txt" in sftp.itens and PASTA + "/a b.txt" not in sftp.itens

    respostas.append("nova pasta")
    esperar(j, lambda: "Pasta criada: nova pasta" in texto(j), acao=j.nova_pasta)
    assert sftp.itens[PASTA + "/nova pasta"] == ("dir",)

    ocioso(j)
    selecionar(j.remoto, ["novo nome.txt"])
    respostas.append(PASTA + "/nova pasta")
    esperar(j, lambda: "Mover: 1 item(ns) processado(s)." in texto(j), acao=j.mover_para)
    assert PASTA + "/nova pasta/novo nome.txt" in sftp.itens
    assert PASTA + "/novo nome.txt" not in sftp.itens

    ocioso(j)
    selecionar(j.remoto, ["nova pasta"])
    esperar(j, lambda: "Apagado(s): 1" in texto(j), acao=j.apagar)
    assert PASTA + "/nova pasta" not in sftp.itens
    assert PASTA + "/nova pasta/novo nome.txt" not in sftp.itens

    # apagar a própria pasta do perfil: recusado
    esperar(j, lambda: j.remoto.caminho_atual() == HOME, acao=lambda: j._pedir_remoto(HOME))
    selecionar(j.remoto, ["projeto"])
    antes = sftp.caminhos()
    esperar(j, lambda: "Recusado por segurança" in texto(j), acao=j.apagar)
    ocioso(j)
    assert sftp.caminhos() == antes
    assert "ERRO:" in texto(j)

    # (5) rodar
    esperar(j, lambda: j.remoto.caminho_atual() == PASTA, acao=lambda: j._pedir_remoto(PASTA))
    selecionar(j.remoto, ["x.py"])
    esperar(j, lambda: "[terminou com código 0]" in texto(j), acao=j.rodar)
    assert comandos == [f"cd {PASTA} && python3 ./x.py"]
    assert "olá" in texto(j)

    # (7) soltar local -> pasta remota
    j._pedir_local(str(origem))
    ocioso(j)
    selecionar(j.local, ["ção.txt"])
    alvo = entrada(j.remoto, "pasta com espaço")
    esperar(j, lambda: PASTA + "/pasta com espaço/ção.txt" in sftp.itens, acao=lambda: j._ao_soltar(j.local, j.local.selecionados(), j.remoto, alvo))

    # (6) falha: linha ERRO em português e a fila continua funcionando
    fake.falhar = True
    esperar(j, lambda: "ERRO:" in texto(j).split("Recusado", 1)[1], acao=j._atualizar_remoto)
    fake.falhar = False
    ocioso(j)
    respostas.append("depois do erro")
    esperar(j, lambda: "Pasta criada: depois do erro" in texto(j), acao=j.nova_pasta)
    assert PASTA + "/depois do erro" in sftp.itens


def test_apagar_pelo_symlink_para_a_raiz_e_recusado(ambiente):
    j, fake, comandos, respostas = ambiente
    sftp = fake._sftp
    sftp.link(PASTA + "/raiz", "/")
    conectar(j)
    esperar(j, lambda: j.remoto.caminho_atual() == PASTA + "/raiz/home", acao=lambda: j._pedir_remoto(PASTA + "/raiz/home"))
    selecionar(j.remoto, ["fulano"])
    antes = sftp.caminhos()
    esperar(j, lambda: "Recusado por segurança" in texto(j), acao=j.apagar)
    ocioso(j)
    assert sftp.caminhos() == antes
    assert "ERRO:" in texto(j)


def test_apagar_sem_conseguir_descobrir_a_home_e_recusado(ambiente):
    j, fake, comandos, respostas = ambiente
    sftp = fake._sftp
    conectar(j)
    selecionar(j.remoto, ["x.py"])
    fake.falhar_home = True
    antes = sftp.caminhos()
    esperar(j, lambda: "pasta pessoal" in texto(j), acao=j.apagar)
    ocioso(j)
    assert sftp.caminhos() == antes
    assert "ERRO:" in texto(j)


# ---------- ciclo de vida da conexão
class _Transporte:
    def __init__(self):
        self.ativo = True

    def is_active(self):
        return self.ativo


class _Cli:
    def __init__(self, sftp):
        self.transporte, self._sftp, self.fechado = _Transporte(), sftp, False

    def get_transport(self):
        return self.transporte

    def open_sftp(self):
        return self._sftp

    def close(self):
        self.fechado = True


def test_conectar_e_desconectar_logo_em_seguida_nao_reaplica_o_estado(ambiente):
    j, fake, comandos, respostas = ambiente
    fake.trava = threading.Event()

    def clicar():
        j.conectar()
        j.desconectar()
        fake.trava.set()
    ocioso(j, acao=clicar)
    assert j.sessao is None
    assert j.barra.estado.get() == "Desconectado"
    assert str(j.barra.botao_conectar.cget("state")) == "normal"
    assert j.remoto.caminho_atual() == ""
    assert "Conectado." not in texto(j)


def test_conexao_que_falha_nao_abre_segunda_conexao_para_operacao_enfileirada(ambiente, monkeypatch):
    from app.ui import janela
    from app.sessao import Sessao
    j, fake, comandos, respostas = ambiente
    chamadas = []

    def abrir():
        chamadas.append(1)
        raise TimeoutError("fora")
    monkeypatch.setattr(janela, "Sessao", lambda a: Sessao(abrir))

    def clicar():
        j.conectar()
        j._listar_remoto("~")       # operação enfileirada atrás da conexão que vai falhar
    ocioso(j, acao=clicar)
    assert len(chamadas) == 1
    assert j.sessao is None and j.barra.estado.get() == "Desconectado"
    assert "ERRO:" in texto(j)


def test_transporte_caido_e_reconexao_que_falha_volta_a_desconectado(ambiente, monkeypatch):
    from app.ui import janela
    from app.sessao import Sessao
    j, fake, comandos, respostas = ambiente
    clis = []

    def abrir():
        if clis:
            raise TimeoutError("fora")
        clis.append(_Cli(fake._sftp))
        return clis[0]
    monkeypatch.setattr(janela, "Sessao", lambda a: Sessao(abrir))
    conectar(j)
    clis[0].transporte.ativo = False
    esperar(j, lambda: j.sessao is None, acao=j._atualizar_remoto)
    ocioso(j)
    assert j.barra.estado.get() == "Desconectado"
    assert j.remoto.caminho_atual() == ""
    assert "Conexão perdida. Clique em Conectar." in texto(j)
    assert "Não consegui alcançar o PC" in texto(j)
    assert str(j.barra.botao_conectar.cget("state")) == "normal"


def test_operacoes_durante_a_conexao_sao_recusadas(ambiente, tmp_path):
    j, fake, comandos, respostas = ambiente
    sftp = fake._sftp
    origem = tmp_path / "origem"
    origem.mkdir()
    (origem / "a.txt").write_text("um")
    j._pedir_local(str(origem))
    selecionar(j.local, ["a.txt"])
    antes = sftp.caminhos()
    fake.trava = threading.Event()

    def clicar():
        j.conectar()                   # sessao definida, mas o painel remoto ainda está vazio
        for acao in (j.enviar, j.nova_pasta, j.mover_para, j.enviar_e_rodar,
                     lambda: j._ao_soltar_do_sistema([str(origem / "a.txt")])):
            acao()
    esperar(j, lambda: texto(j).count("Aguarde a conexão terminar.") == 5, acao=clicar)
    assert j.remoto.caminho_atual() == ""
    esperar(j, lambda: "Conectado:" in j.barra.estado.get(), acao=fake.trava.set)
    ocioso(j)
    assert sftp.caminhos() == antes
    assert comandos == []


def test_enviar_e_rodar_avisa_quando_pular_mantem_o_script_antigo(ambiente, tmp_path, monkeypatch):
    from app.ui import dialogos
    j, fake, comandos, respostas = ambiente
    monkeypatch.setattr(dialogos, "perguntar_conflito", lambda *a, **k: ("pular", False))
    conectar(j)
    origem = tmp_path / "origem"
    origem.mkdir()
    (origem / "x.py").write_text("print(2)")
    j._pedir_local(str(origem))
    ocioso(j)
    selecionar(j.local, ["x.py"])
    esperar(j, lambda: "[terminou com código 0]" in texto(j), acao=j.enviar_e_rodar)
    assert "O script já existia no PC remoto e NÃO foi substituído; rodando a versão que já estava lá." in texto(j)
    assert fake._sftp.conteudo(PASTA + "/x.py") == b"print(1)"
    assert comandos == [f"cd {PASTA} && python3 ./x.py"]
