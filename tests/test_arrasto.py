from app.arquivos import Entrada
from app.ui.arrasto import decidir_arrasto

A = Entrada("a.txt", "/r/a.txt", False)
PASTA = Entrada("sub", "/r/sub", True)


def test_local_para_remoto_envia_para_pasta_aberta_ou_pasta_alvo():
    assert decidir_arrasto("local", "remoto", "/r", "C:/x", None, [A]) == ("enviar", "/r")
    assert decidir_arrasto("local", "remoto", "/r", "C:/x", PASTA, [A]) == ("enviar", "/r/sub")
    assert decidir_arrasto("local", "remoto", "/r", "C:/x", A, [A]) == ("enviar", "/r")


def test_remoto_para_local_baixa():
    assert decidir_arrasto("remoto", "local", "C:/x", "/r", None, [A]) == ("baixar", "C:/x")


def test_mover_dentro_do_remoto():
    assert decidir_arrasto("remoto", "remoto", "/r", "/r", PASTA, [A]) == ("mover", "/r/sub")


def test_arrastes_sem_efeito():
    assert decidir_arrasto("remoto", "remoto", "/r", "/r", None, [A]) is None      # mesma pasta
    assert decidir_arrasto("remoto", "remoto", "/r", "/r", A, [A]) is None         # solta sobre arquivo
    assert decidir_arrasto("remoto", "remoto", "/r", "/r", PASTA, [PASTA]) is None  # sobre si mesma
    assert decidir_arrasto("local", "local", "C:/x", "C:/y", None, [A]) is None
