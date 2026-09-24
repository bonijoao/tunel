import os
import posixpath
import stat
from dataclasses import dataclass
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class Entrada:
    nome: str
    caminho: str
    eh_pasta: bool
    tamanho: int = 0
    mtime: float | None = None


class Cancelado(Exception):
    """O usuário cancelou a operação em andamento."""


class OperacaoRecusada(RuntimeError):
    """Operação recusada por regra de segurança ou de consistência."""


class PoliticaConflito:
    """Decide o que fazer quando o destino já existe; lembra a escolha se o usuário pediu 'a todos'."""

    def __init__(self, perguntar: Callable[[str], tuple]):
        self._perguntar = perguntar
        self._padrao = None

    def __call__(self, caminho: str) -> str:
        if self._padrao:
            return self._padrao
        acao, todos = self._perguntar(caminho)
        if acao != "cancelar" and todos:
            self._padrao = acao
        return acao


# ---------- listagem e formatação
def _ordenar(entradas):
    return sorted(entradas, key=lambda e: (not e.eh_pasta, e.nome.casefold()))


def listar_local(caminho: str) -> list[Entrada]:
    saida = []
    with os.scandir(caminho) as it:
        for e in it:
            try:
                st = e.stat()
                eh_pasta = e.is_dir()
            except OSError:
                continue
            saida.append(Entrada(e.name, os.path.join(caminho, e.name), eh_pasta,
                                 0 if eh_pasta else st.st_size, st.st_mtime))
    return _ordenar(saida)


def listar_remoto(sftp, caminho: str) -> list[Entrada]:
    saida = []
    for a in sftp.listdir_attr(caminho):
        completo = posixpath.join(caminho, a.filename)
        modo = a.st_mode or 0
        if stat.S_ISLNK(modo):
            try:
                eh_pasta = stat.S_ISDIR(sftp.stat(completo).st_mode or 0)
            except OSError:
                eh_pasta = False
        else:
            eh_pasta = stat.S_ISDIR(modo)
        saida.append(Entrada(a.filename, completo, eh_pasta,
                             0 if eh_pasta else (a.st_size or 0), a.st_mtime))
    return _ordenar(saida)


def formatar_tamanho(n: int) -> str:
    valor = float(n)
    for unidade in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1024 or unidade == "TB":
            return f"{int(valor)} B" if unidade == "B" else f"{valor:.1f} {unidade}"
        valor /= 1024


def formatar_data(ts) -> str:
    if ts is None:
        return ""
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")


# ---------- nomes e caminhos remotos
def validar_nome(nome: str):
    if not nome or not nome.strip():
        return "O nome não pode ficar vazio."
    if nome in (".", ".."):
        return "Nome inválido."
    if "/" in nome or "\\" in nome or "\x00" in nome:
        return "O nome não pode conter / ou \\."
    return None


_INVALIDOS_NT = set('<>:"|?*')
_RESERVADOS_NT = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                  *(f"LPT{i}" for i in range(1, 10))}


def nome_local_invalido(nome: str, sistema: str | None = None):
    """Motivo pelo qual `nome` não pode virar arquivo neste computador, ou None se puder."""
    erro = validar_nome(nome)
    if erro:
        return erro
    if (sistema or os.name) == "nt":
        if any(ch in _INVALIDOS_NT or ord(ch) < 0x20 for ch in nome):
            return "O nome tem caracteres que o Windows não aceita."
        if nome.endswith((".", " ")):
            return "O Windows não aceita nomes que terminam em ponto ou espaço."
        if nome.split(".")[0].rstrip(" ").upper() in _RESERVADOS_NT:
            return "Nome reservado do Windows."
    return None


def _normalizar(caminho: str) -> str:
    """normpath que colapsa barras iniciais (POSIX mantém '//' como está, mas no Linux é igual a '/')."""
    c = posixpath.normpath(caminho)
    if c.startswith("/"):
        c = "/" + c.lstrip("/")
    return c


def expandir_remoto(caminho: str, home: str) -> str:
    c = caminho.strip() or "~"
    if c == "~":
        return home
    if c.startswith("~/"):
        return _normalizar(posixpath.join(home, c[2:]))
    if not c.startswith("/"):
        return _normalizar(posixpath.join(home, c))
    return _normalizar(c)


def protegido(caminho: str, home: str, pasta_perfil: str) -> bool:
    """True se apagar `caminho` é proibido: raiz, home, pasta do perfil, ancestrais delas, ou caminho não absoluto."""
    c = _normalizar(caminho)
    if not c.startswith("/") or c == "/":
        return True
    for ref in (home, pasta_perfil):
        r = _normalizar(ref)
        if r == c or r.startswith(c.rstrip("/") + "/"):
            return True
    return False


def _existe_remoto(sftp, caminho):
    try:
        return sftp.stat(caminho)
    except OSError:
        return None


# ---------- operações remotas
def renomear(sftp, caminho: str, novo_nome: str) -> str:
    erro = validar_nome(novo_nome)
    if erro:
        raise ValueError(erro)
    destino = posixpath.join(posixpath.dirname(caminho), novo_nome)
    if destino == caminho:
        return destino
    if _existe_remoto(sftp, destino) is not None:
        raise FileExistsError(f"Já existe um item chamado '{novo_nome}' nesta pasta.")
    sftp.rename(caminho, destino)
    return destino


def mover(sftp, caminhos: list[str], pasta_destino: str):
    """Devolve (movidos, ignorados); ignorados é uma lista de (caminho, motivo)."""
    dest_dir = _normalizar(pasta_destino)
    alvo = _existe_remoto(sftp, dest_dir)
    if alvo is None or not stat.S_ISDIR(alvo.st_mode or 0):
        raise OperacaoRecusada(f"A pasta de destino '{dest_dir}' não existe.")
    movidos, ignorados = [], []
    for c in caminhos:
        c = _normalizar(c)
        destino = posixpath.join(dest_dir, posixpath.basename(c))
        if dest_dir == c or dest_dir.startswith(c + "/"):
            ignorados.append((c, "não é possível mover uma pasta para dentro dela mesma"))
        elif posixpath.dirname(c) == dest_dir:
            ignorados.append((c, "já está nesta pasta"))
        elif _existe_remoto(sftp, destino) is not None:
            ignorados.append((c, "já existe um item com esse nome no destino"))
        else:
            sftp.rename(c, destino)
            movidos.append(destino)
    return movidos, ignorados


def criar_pasta_remota(sftp, pasta_pai: str, nome: str) -> str:
    erro = validar_nome(nome)
    if erro:
        raise ValueError(erro)
    destino = posixpath.join(pasta_pai, nome)
    if _existe_remoto(sftp, destino) is not None:
        raise FileExistsError(f"Já existe um item chamado '{nome}' nesta pasta.")
    sftp.mkdir(destino)
    return destino


def _apagar_rec(sftp, caminho):
    if stat.S_ISDIR(sftp.lstat(caminho).st_mode or 0):
        for filho in sftp.listdir_attr(caminho):
            _apagar_rec(sftp, posixpath.join(caminho, filho.filename))
        sftp.rmdir(caminho)
    else:
        sftp.remove(caminho)


def apagar_itens(sftp, caminhos: list[str], home: str, pasta_perfil: str, progresso=None) -> None:
    """Apaga só se NADA for protegido, olhando o texto digitado e o caminho real no servidor."""
    try:
        home_r = sftp.normalize(home)
        perfil_r = sftp.normalize(pasta_perfil)
    except Exception:
        raise OperacaoRecusada("Recusado por segurança: não consegui confirmar a pasta pessoal e a pasta do "
                               "perfil no PC remoto.") from None
    homes, perfis = {home, home_r}, {pasta_perfil, perfil_r}
    alvos, barrados = [], []
    for c in caminhos:
        cn = _normalizar(c)
        try:
            pai_r = sftp.normalize(posixpath.dirname(cn))
        except Exception:
            raise OperacaoRecusada(f"Recusado por segurança: não consegui confirmar o caminho real de {c}.") from None
        alvo_r = posixpath.join(pai_r, posixpath.basename(cn))    # o último componente não é seguido
        if any(protegido(x, h, p) for x in {cn, alvo_r} for h in homes for p in perfis):
            barrados.append(c)
        alvos.append(alvo_r)
    if barrados:
        raise OperacaoRecusada("Recusado por segurança: " + ", ".join(barrados))
    for i, alvo in enumerate(alvos, 1):
        if progresso:
            progresso(i, len(alvos), posixpath.basename(alvo.rstrip("/")))
        _apagar_rec(sftp, alvo)


# ---------- transferência
def _enviar_um(sftp, origem, destino, resolver):
    if os.path.islink(origem):
        return
    existente = _existe_remoto(sftp, destino)
    if os.path.isdir(origem):
        if existente is None:
            sftp.mkdir(destino)
        elif not stat.S_ISDIR(existente.st_mode or 0):
            raise FileExistsError(f"'{destino}' já existe no PC remoto e não é uma pasta.")
        for nome in sorted(os.listdir(origem)):
            _enviar_um(sftp, os.path.join(origem, nome), posixpath.join(destino, nome), resolver)
    elif os.path.isfile(origem):
        if existente is not None:
            if stat.S_ISDIR(existente.st_mode or 0):
                raise FileExistsError(f"'{destino}' já existe no PC remoto e é uma pasta.")
            acao = resolver(destino)
            if acao == "cancelar":
                raise Cancelado()
            if acao == "pular":
                return
        sftp.put(origem, destino)


def enviar_itens(sftp, locais: list[str], destino_dir: str, resolver, progresso=None) -> None:
    for i, origem in enumerate(locais, 1):
        nome = os.path.basename(origem.rstrip("/\\"))
        if progresso:
            progresso(i, len(locais), nome)
        _enviar_um(sftp, origem, posixpath.join(destino_dir, nome), resolver)


def _exigir_nome_valido(nome):
    if nome_local_invalido(nome):
        raise OperacaoRecusada(f"Nome inválido no PC remoto: {nome!r}")


def _destino_contido(pasta: str, nome: str) -> str:
    """Caminho local de `nome` dentro de `pasta`; recusa se sair dela (qualquer sistema)."""
    _exigir_nome_valido(nome)
    base = os.path.abspath(pasta)
    destino = os.path.abspath(os.path.join(base, nome))
    try:
        dentro = os.path.commonpath([base, destino]) == base and destino != base
    except ValueError:      # unidades diferentes
        dentro = False
    if not dentro:
        raise OperacaoRecusada(f"Nome inválido no PC remoto: {nome!r}")
    return destino


def _baixar_um(sftp, remoto, eh_pasta, destino, resolver):
    if eh_pasta:
        if os.path.exists(destino) and not os.path.isdir(destino):
            raise FileExistsError(f"'{destino}' já existe neste computador e não é uma pasta.")
        os.makedirs(destino, exist_ok=True)
        for a in sftp.listdir_attr(remoto):
            filho = _destino_contido(destino, a.filename)
            modo = a.st_mode or 0
            if not (stat.S_ISDIR(modo) or stat.S_ISREG(modo)):
                continue
            _baixar_um(sftp, posixpath.join(remoto, a.filename), stat.S_ISDIR(modo),
                       filho, resolver)
    else:
        if os.path.exists(destino):
            if os.path.isdir(destino):
                raise FileExistsError(f"'{destino}' já existe neste computador e é uma pasta.")
            acao = resolver(destino)
            if acao == "cancelar":
                raise Cancelado()
            if acao == "pular":
                return
        sftp.get(remoto, destino)


def baixar_itens(sftp, entradas: list[Entrada], destino_dir: str, resolver, progresso=None) -> None:
    destinos = [_destino_contido(destino_dir, e.nome) for e in entradas]     # tudo validado antes de baixar
    for i, (e, destino) in enumerate(zip(entradas, destinos), 1):
        if progresso:
            progresso(i, len(entradas), e.nome)
        _baixar_um(sftp, e.caminho, e.eh_pasta, destino, resolver)
