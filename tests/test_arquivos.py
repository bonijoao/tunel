import os

import pytest

from app import arquivos
from app.arquivos import Cancelado, Entrada, OperacaoRecusada, PoliticaConflito
from tests.fakes import FakeSftp

HOME = "/home/fulano"
PERFIL = "/home/fulano/projeto"


# ---------- listagem
def test_listar_local_pastas_primeiro_e_sem_diferenciar_maiusculas(tmp_path):
    (tmp_path / "b.txt").write_text("1")
    (tmp_path / "A.txt").write_text("22")
    (tmp_path / "zeta").mkdir()
    (tmp_path / "alfa").mkdir()
    nomes = [e.nome for e in arquivos.listar_local(str(tmp_path))]
    assert nomes == ["alfa", "zeta", "A.txt", "b.txt"]
    tam = {e.nome: e.tamanho for e in arquivos.listar_local(str(tmp_path))}
    assert tam["A.txt"] == 2 and tam["alfa"] == 0


def test_listar_remoto_ordem_e_link_para_pasta_e_pasta():
    s = FakeSftp()
    s.pasta("/d/sub")
    s.arquivo("/d/b.txt", b"12")
    s.arquivo("/d/A.txt", b"1")
    s.link("/d/atalho", "/d/sub")
    s.link("/d/quebrado", "/nao/existe")
    lista = arquivos.listar_remoto(s, "/d")
    assert [e.nome for e in lista] == ["atalho", "sub", "A.txt", "b.txt", "quebrado"]
    por_nome = {e.nome: e for e in lista}
    assert por_nome["atalho"].eh_pasta is True
    assert por_nome["quebrado"].eh_pasta is False
    assert por_nome["b.txt"].caminho == "/d/b.txt" and por_nome["b.txt"].tamanho == 2


def test_formatadores():
    assert arquivos.formatar_tamanho(0) == "0 B"
    assert arquivos.formatar_tamanho(1536) == "1.5 KB"
    assert arquivos.formatar_tamanho(5 * 1024 ** 2) == "5.0 MB"
    assert arquivos.formatar_data(None) == ""
    assert len(arquivos.formatar_data(1700000000)) == 16


@pytest.mark.parametrize("nome,ok", [
    ("relatório final.txt", True), ("a'b\"c", True), ("", False), ("   ", False),
    (".", False), ("..", False), ("a/b", False), ("a\\b", False), ("a\x00b", False),
])
def test_validar_nome(nome, ok):
    assert (arquivos.validar_nome(nome) is None) is ok


@pytest.mark.parametrize("entrada,esperado", [
    ("~", HOME), ("", HOME), ("~/x/y", HOME + "/x/y"), ("x", HOME + "/x"),
    ("/etc/", "/etc"), ("/a/../b", "/b"), ("~/x/../y", HOME + "/y"),
])
def test_expandir_remoto(entrada, esperado):
    assert arquivos.expandir_remoto(entrada, HOME) == esperado


@pytest.mark.parametrize("caminho,barrado", [
    ("/", True), ("/home", True), (HOME, True), (HOME + "/", True), (PERFIL, True),
    ("/home/fulano/../..", True), ("relativo/x", True), ("~", True), (".", True),
    ("//home/fulano", True), ("//home", True), ("//home/fulano/projeto", True), ("///", True),
    ("/home//fulano", True),
    (PERFIL + "/dados", False), ("/tmp/x", False), (HOME + "/outra", False),
])
def test_protegido(caminho, barrado):
    assert arquivos.protegido(caminho, HOME, PERFIL) is barrado


# ---------- renomear / mover / criar
def test_renomear_ok_existente_e_invalido():
    s = FakeSftp()
    s.arquivo("/d/a b.txt", b"x")
    s.arquivo("/d/c.txt", b"y")
    assert arquivos.renomear(s, "/d/a b.txt", "ç 'x'.txt") == "/d/ç 'x'.txt"
    assert "/d/ç 'x'.txt" in s.caminhos() and "/d/a b.txt" not in s.caminhos()
    with pytest.raises(FileExistsError):
        arquivos.renomear(s, "/d/c.txt", "ç 'x'.txt")
    with pytest.raises(ValueError):
        arquivos.renomear(s, "/d/c.txt", "a/b")
    assert arquivos.renomear(s, "/d/c.txt", "c.txt") == "/d/c.txt"


def test_mover_casos():
    s = FakeSftp()
    s.arquivo("/d/a.txt", b"1")
    s.arquivo("/d/pasta/b.txt", b"2")
    s.pasta("/d/destino")
    s.arquivo("/d/destino/a.txt", b"conflito")
    s.arquivo("/d/c.txt", b"3")
    movidos, ignorados = arquivos.mover(s, ["/d/a.txt", "/d/c.txt", "/d/pasta"], "/d/destino")
    assert sorted(movidos) == ["/d/destino/c.txt", "/d/destino/pasta"]
    assert ignorados == [("/d/a.txt", "já existe um item com esse nome no destino")]
    assert s.conteudo("/d/destino/pasta/b.txt") == b"2"
    assert s.conteudo("/d/a.txt") == b"1"
    m2, ig2 = arquivos.mover(s, ["/d/destino"], "/d/destino/pasta")
    assert m2 == [] and "dentro dela mesma" in ig2[0][1]
    m3, ig3 = arquivos.mover(s, ["/d/destino/c.txt"], "/d/destino")
    assert m3 == [] and ig3[0][1] == "já está nesta pasta"
    with pytest.raises(OperacaoRecusada):
        arquivos.mover(s, ["/d/destino/c.txt"], "/d/nao_existe")
    with pytest.raises(OperacaoRecusada):
        arquivos.mover(s, ["/d/destino/c.txt"], "/d/destino/c.txt")


def test_criar_pasta_remota():
    s = FakeSftp()
    s.pasta("/d")
    assert arquivos.criar_pasta_remota(s, "/d", "nova pasta") == "/d/nova pasta"
    assert "/d/nova pasta" in s.caminhos()
    with pytest.raises(FileExistsError):
        arquivos.criar_pasta_remota(s, "/d", "nova pasta")
    with pytest.raises(ValueError):
        arquivos.criar_pasta_remota(s, "/d", "x/y")


# ---------- apagar
def test_apagar_recursivo_e_link_nao_segue():
    s = FakeSftp()
    s.arquivo(PERFIL + "/lixo/a.txt", b"1")
    s.arquivo(PERFIL + "/lixo/sub/b.txt", b"2")
    s.pasta(PERFIL + "/lixo/vazia")
    s.arquivo(PERFIL + "/fica.txt", b"3")
    s.link(PERFIL + "/lixo/atalho", PERFIL)
    vistos = []
    arquivos.apagar_itens(s, [PERFIL + "/lixo"], HOME, PERFIL, lambda i, n, nome: vistos.append((i, n, nome)))
    assert PERFIL + "/lixo" not in s.caminhos()
    assert PERFIL + "/fica.txt" in s.caminhos() and PERFIL in s.caminhos()
    assert vistos == [(1, 1, "lixo")]


def test_apagar_tudo_ou_nada_quando_ha_caminho_protegido():
    s = FakeSftp()
    s.arquivo(PERFIL + "/a.txt", b"1")
    s.arquivo(PERFIL + "/b.txt", b"2")
    for barrado in ("/", HOME, PERFIL, "/home", "~", "relativo"):
        with pytest.raises(OperacaoRecusada, match="segurança"):
            arquivos.apagar_itens(s, [PERFIL + "/a.txt", barrado, PERFIL + "/b.txt"], HOME, PERFIL)
        assert PERFIL + "/a.txt" in s.caminhos() and PERFIL + "/b.txt" in s.caminhos()


def test_apagar_barra_dupla_inicial_nao_burla_protecao():
    s = FakeSftp()
    s.arquivo(PERFIL + "/a.txt", b"1")
    antes = s.caminhos()
    with pytest.raises(OperacaoRecusada, match="segurança"):
        arquivos.apagar_itens(s, ["//home/fulano/projeto/a.txt", "//home/fulano"], HOME, PERFIL)
    assert s.caminhos() == antes


# ---------- política de conflito
def test_politica_de_conflito_aplica_a_todos_e_cancelar_nao_grava():
    perguntas = []

    def perguntar(caminho):
        perguntas.append(caminho)
        return ("pular", True)

    p = PoliticaConflito(perguntar)
    assert p("/x/1") == "pular" and p("/x/2") == "pular"
    assert perguntas == ["/x/1"]
    q = PoliticaConflito(lambda c: ("cancelar", True))
    assert q("/a") == "cancelar"
    q2 = PoliticaConflito(lambda c: ("substituir", False))
    assert q2("/a") == "substituir"


def _resolver(acao):
    return PoliticaConflito(lambda c: (acao, True))


# ---------- enviar
def _arvore_local(tmp_path):
    raiz = tmp_path / "proj"
    (raiz / "sub" / "fundo").mkdir(parents=True)
    (raiz / "vazia").mkdir()
    (raiz / "a.txt").write_bytes(b"AAA")
    (raiz / "sub" / "b ç.txt").write_bytes(b"BBB")
    (raiz / "sub" / "fundo" / "c.txt").write_bytes(b"CCC")
    solto = tmp_path / "solto.txt"
    solto.write_bytes(b"SSS")
    return raiz, solto


def test_enviar_itens_mistos_recursivo_com_pasta_vazia(tmp_path):
    raiz, solto = _arvore_local(tmp_path)
    s = FakeSftp()
    s.pasta("/dest")
    vistos = []
    arquivos.enviar_itens(s, [str(raiz), str(solto)], "/dest", _resolver("substituir"),
                          lambda i, n, nome: vistos.append((i, n, nome)))
    assert s.conteudo("/dest/proj/a.txt") == b"AAA"
    assert s.conteudo("/dest/proj/sub/b ç.txt") == b"BBB"
    assert s.conteudo("/dest/proj/sub/fundo/c.txt") == b"CCC"
    assert "/dest/proj/vazia" in s.caminhos()
    assert s.conteudo("/dest/solto.txt") == b"SSS"
    assert vistos == [(1, 2, "proj"), (2, 2, "solto.txt")]


def test_enviar_conflitos_pular_substituir_cancelar(tmp_path):
    _, solto = _arvore_local(tmp_path)
    s = FakeSftp()
    s.arquivo("/dest/solto.txt", b"VELHO")
    arquivos.enviar_itens(s, [str(solto)], "/dest", _resolver("pular"))
    assert s.conteudo("/dest/solto.txt") == b"VELHO"
    arquivos.enviar_itens(s, [str(solto)], "/dest", _resolver("substituir"))
    assert s.conteudo("/dest/solto.txt") == b"SSS"
    s.arquivo("/dest/solto.txt", b"VELHO")
    with pytest.raises(Cancelado):
        arquivos.enviar_itens(s, [str(solto)], "/dest", _resolver("cancelar"))
    assert s.conteudo("/dest/solto.txt") == b"VELHO"


def test_enviar_tipos_diferentes_no_destino(tmp_path):
    raiz, solto = _arvore_local(tmp_path)
    s = FakeSftp()
    s.pasta("/dest/solto.txt")          # destino é pasta, origem é arquivo
    with pytest.raises(FileExistsError, match="é uma pasta"):
        arquivos.enviar_itens(s, [str(solto)], "/dest", _resolver("substituir"))
    s2 = FakeSftp()
    s2.arquivo("/dest/proj", b"x")      # destino é arquivo, origem é pasta
    with pytest.raises(FileExistsError, match="não é uma pasta"):
        arquivos.enviar_itens(s2, [str(raiz)], "/dest", _resolver("substituir"))


def test_enviar_junta_pasta_existente_e_ignora_link(tmp_path):
    raiz, _ = _arvore_local(tmp_path)
    try:
        os.symlink(str(raiz / "a.txt"), str(raiz / "atalho"))
    except (OSError, NotImplementedError):
        pass
    s = FakeSftp()
    s.arquivo("/dest/proj/velho.txt", b"V")
    arquivos.enviar_itens(s, [str(raiz)], "/dest", _resolver("substituir"))
    assert s.conteudo("/dest/proj/velho.txt") == b"V"
    assert s.conteudo("/dest/proj/a.txt") == b"AAA"
    assert "/dest/proj/atalho" not in s.caminhos()


# ---------- baixar
def _remoto_com_arvore():
    s = FakeSftp()
    s.arquivo("/r/proj/a.txt", b"AAA")
    s.arquivo("/r/proj/sub/b ç.txt", b"BBB")
    s.pasta("/r/proj/vazia")
    s.link("/r/proj/atalho", "/r/proj/a.txt")
    s.arquivo("/r/solto.txt", b"SSS")
    return s


def _entradas(s, *caminhos):
    saida = []
    for c in caminhos:
        a = s.stat(c)
        import stat as _st
        saida.append(Entrada(c.rsplit("/", 1)[1], c, _st.S_ISDIR(a.st_mode), a.st_size))
    return saida


def test_baixar_itens_mistos_recursivo(tmp_path):
    s = _remoto_com_arvore()
    destino = tmp_path / "saida"
    destino.mkdir()
    vistos = []
    arquivos.baixar_itens(s, _entradas(s, "/r/proj", "/r/solto.txt"), str(destino),
                          _resolver("substituir"), lambda i, n, nome: vistos.append((i, n, nome)))
    assert (destino / "proj" / "a.txt").read_bytes() == b"AAA"
    assert (destino / "proj" / "sub" / "b ç.txt").read_bytes() == b"BBB"
    assert (destino / "proj" / "vazia").is_dir()
    assert not (destino / "proj" / "atalho").exists()
    assert (destino / "solto.txt").read_bytes() == b"SSS"
    assert vistos == [(1, 2, "proj"), (2, 2, "solto.txt")]


def test_baixar_conflitos_e_tipos(tmp_path):
    s = _remoto_com_arvore()
    destino = tmp_path / "saida"
    destino.mkdir()
    (destino / "solto.txt").write_bytes(b"VELHO")
    arquivos.baixar_itens(s, _entradas(s, "/r/solto.txt"), str(destino), _resolver("pular"))
    assert (destino / "solto.txt").read_bytes() == b"VELHO"
    with pytest.raises(Cancelado):
        arquivos.baixar_itens(s, _entradas(s, "/r/solto.txt"), str(destino), _resolver("cancelar"))
    arquivos.baixar_itens(s, _entradas(s, "/r/solto.txt"), str(destino), _resolver("substituir"))
    assert (destino / "solto.txt").read_bytes() == b"SSS"
    (destino / "proj").write_bytes(b"arquivo no lugar da pasta")
    with pytest.raises(FileExistsError, match="não é uma pasta"):
        arquivos.baixar_itens(s, _entradas(s, "/r/proj"), str(destino), _resolver("substituir"))
    os.makedirs(destino / "solto2.txt")
    s.arquivo("/r/solto2.txt", b"x")
    with pytest.raises(FileExistsError, match="é uma pasta"):
        arquivos.baixar_itens(s, _entradas(s, "/r/solto2.txt"), str(destino), _resolver("substituir"))


# ---------- nomes remotos maliciosos no download
class _SftpNomesRuins(FakeSftp):
    def __init__(self, nomes):
        super().__init__()
        self._nomes = nomes
        self.pasta("/r/proj")

    def listdir_attr(self, caminho):
        if caminho != "/r/proj":
            return super().listdir_attr(caminho)
        import stat as _st
        import paramiko
        saida = []
        for n in self._nomes:
            a = paramiko.SFTPAttributes()
            a.filename, a.st_mode, a.st_size = n, _st.S_IFDIR | 0o755, 0
            saida.append(a)
        return saida


@pytest.mark.parametrize("nome", ["..", "..\evil", "a\x00b", "../x"])
def test_baixar_recusa_nome_remoto_interno_invalido(tmp_path, nome):
    destino = tmp_path / "saida"
    destino.mkdir()
    antes = sorted(p.name for p in tmp_path.iterdir())
    s = _SftpNomesRuins([nome])
    with pytest.raises(OperacaoRecusada, match="Nome inválido"):
        arquivos.baixar_itens(s, [Entrada("proj", "/r/proj", True)], str(destino), _resolver("substituir"))
    assert sorted(p.name for p in tmp_path.iterdir()) == antes
    assert list(destino.rglob("*")) == [] or [p.name for p in destino.iterdir()] == ["proj"]


def test_baixar_recusa_nome_de_entrada_de_topo_invalido(tmp_path):
    destino = tmp_path / "saida"
    destino.mkdir()
    s = FakeSftp()
    s.arquivo("/r/x", b"x")
    with pytest.raises(OperacaoRecusada, match="Nome inválido"):
        arquivos.baixar_itens(s, [Entrada("../x", "/r/x", False)], str(destino), _resolver("substituir"))
    assert not (tmp_path / "x").exists()
    assert list(destino.iterdir()) == []
