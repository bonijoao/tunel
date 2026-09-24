import queue
import threading
from typing import Callable

from app import ssh
from app.arquivos import Cancelado


class Sessao:
    """Uma conexão SSH/SFTP reaproveitada; reconecta (uma vez por uso) se a transporte tiver caído."""

    def __init__(self, abrir: Callable):
        self._abrir = abrir
        self._cli = None
        self._sftp = None
        self._home = None

    def _vivo(self) -> bool:
        if self._cli is None:
            return False
        transporte = self._cli.get_transport()
        return transporte is not None and transporte.is_active()

    def conectado(self) -> bool:
        return self._vivo()

    def conectar(self) -> None:
        self.fechar()
        cli = self._abrir()
        try:
            cli.get_transport().set_keepalive(30)
        except AttributeError:
            pass
        self._cli = cli

    def obter(self):
        if not self._vivo():
            self.conectar()
        return self._cli

    def sftp(self):
        cli = self.obter()
        if self._sftp is None:
            self._sftp = cli.open_sftp()
        return self._sftp

    def home(self) -> str:
        if self._home is None:
            try:
                valor = self.sftp().normalize(".")
            except Exception:
                valor = None
            if (not isinstance(valor, str) or not valor.startswith("/")
                    or any(ch in valor for ch in "\n\r\x00")):
                raise RuntimeError("Não consegui descobrir a pasta pessoal no PC remoto.")
            self._home = valor
        return self._home

    def fechar(self) -> None:
        for obj in (self._sftp, self._cli):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        self._cli = self._sftp = self._home = None


class Fila:
    """Executa uma tarefa de rede por vez numa thread; devolve resultados pela função `despachar`."""

    def __init__(self, despachar: Callable[[Callable], None], ao_ocupado=None):
        self._q = queue.Queue()
        self._despachar = despachar
        self._ao_ocupado = ao_ocupado
        threading.Thread(target=self._loop, daemon=True).start()

    def enfileirar(self, tarefa, ao_terminar=None, ao_erro=None) -> None:
        self._q.put((tarefa, ao_terminar, ao_erro))

    def aguardar(self) -> None:
        self._q.join()

    def _chamar(self, cb, arg) -> None:
        if cb is None:
            return
        try:
            self._despachar(lambda: cb(arg))
        except Exception:
            pass

    def _sinalizar(self, ocupado: bool) -> None:
        if self._ao_ocupado is None:
            return
        try:
            self._despachar(lambda: self._ao_ocupado(ocupado))
        except Exception:
            pass

    def _loop(self) -> None:
        while True:
            tarefa, ok, erro = self._q.get()
            self._sinalizar(True)
            try:
                resultado = tarefa()
            except Cancelado:
                self._chamar(erro, "Operação cancelada.")
            except Exception as exc:
                self._chamar(erro, ssh.traduzir_erro(exc))
            else:
                self._chamar(ok, resultado)
            finally:
                self._sinalizar(not self._q.empty())
                self._q.task_done()
