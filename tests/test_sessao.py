import threading
import time

import pytest

from app.arquivos import Cancelado
from app.sessao import Fila, Sessao


class FakeTransporte:
    def __init__(self):
        self.ativo = True
        self.keepalive = None

    def is_active(self):
        return self.ativo

    def set_keepalive(self, s):
        self.keepalive = s


class FakeCli:
    def __init__(self):
        self.transporte = FakeTransporte()
        self.fechado = False
        self.comandos = []
        self.sftps = 0

    def get_transport(self):
        return self.transporte

    def close(self):
        self.fechado = True

    def open_sftp(self):
        self.sftps += 1
        return object()

    def exec_command(self, cmd):
        self.comandos.append(cmd)

        class Saida:
            def read(self):
                return b"/home/fulano\n"
        return None, Saida(), None


def _sessao():
    abertos = []

    def abrir():
        c = FakeCli()
        abertos.append(c)
        return c
    return Sessao(abrir), abertos


def test_conectar_liga_keepalive_e_conectado():
    s, abertos = _sessao()
    assert not s.conectado()
    s.conectar()
    assert s.conectado() and abertos[0].transporte.keepalive == 30


def test_obter_reconecta_uma_vez_quando_a_transporte_caiu():
    s, abertos = _sessao()
    s.conectar()
    abertos[0].transporte.ativo = False
    novo = s.obter()
    assert len(abertos) == 2 and novo is abertos[1] and abertos[0].fechado
    assert s.obter() is novo and len(abertos) == 2


def test_falha_ao_reconectar_propaga_sem_laco():
    chamadas = []

    def abrir():
        chamadas.append(1)
        if len(chamadas) > 1:
            raise TimeoutError("fora")
        return FakeCli()
    s = Sessao(abrir)
    s.conectar()
    s._cli.transporte.ativo = False
    with pytest.raises(TimeoutError):
        s.obter()
    assert len(chamadas) == 2


def test_sftp_e_home_em_cache_e_resetam_ao_reconectar():
    s, abertos = _sessao()
    s.conectar()
    assert s.sftp() is s.sftp() and abertos[0].sftps == 1
    assert s.home() == "/home/fulano" and s.home() == "/home/fulano"
    assert abertos[0].comandos == ["echo $HOME"]
    abertos[0].transporte.ativo = False
    s.sftp()
    assert abertos[1].sftps == 1


def test_fechar_fecha_e_desconecta():
    s, abertos = _sessao()
    s.conectar()
    s.fechar()
    assert abertos[0].fechado and not s.conectado()
    s.fechar()


# ---------- fila
def _fila():
    eventos = []
    return Fila(lambda f: f(), ao_ocupado=lambda b: eventos.append(b)), eventos


def test_fila_executa_em_ordem_e_uma_por_vez():
    fila, _ = _fila()
    ordem, simultaneas, maximo = [], [0], [0]
    trava = threading.Lock()

    def tarefa(n):
        def f():
            with trava:
                simultaneas[0] += 1
                maximo[0] = max(maximo[0], simultaneas[0])
            time.sleep(0.02)
            ordem.append(n)
            with trava:
                simultaneas[0] -= 1
            return n
        return f

    resultados = []
    for n in range(5):
        fila.enfileirar(tarefa(n), resultados.append)
    fila.aguardar()
    assert ordem == [0, 1, 2, 3, 4] and resultados == [0, 1, 2, 3, 4] and maximo[0] == 1


def test_erro_vira_mensagem_em_portugues_e_nao_trava_a_fila():
    fila, _ = _fila()
    msgs, ok = [], []

    def quebra():
        raise FileNotFoundError("/x")
    fila.enfileirar(quebra, ao_erro=msgs.append)
    fila.enfileirar(lambda: "depois", ok.append)
    fila.aguardar()
    assert "não encontrado" in msgs[0] and ok == ["depois"]


def test_cancelado_vira_mensagem_propria():
    fila, _ = _fila()
    msgs = []

    def cancela():
        raise Cancelado()
    fila.enfileirar(cancela, ao_erro=msgs.append)
    fila.aguardar()
    assert msgs == ["Operação cancelada."]


def test_ocupado_liga_e_desliga():
    fila, eventos = _fila()
    fila.enfileirar(lambda: 1)
    fila.aguardar()
    assert eventos[0] is True and eventos[-1] is False


def test_callback_que_levanta_nao_mata_a_thread():
    fila, _ = _fila()
    ok = []

    def ruim(_r):
        raise RuntimeError("ui")
    fila.enfileirar(lambda: 1, ruim)
    fila.enfileirar(lambda: 2, ok.append)
    fila.aguardar()
    assert ok == [2]
