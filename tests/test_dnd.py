import tkinter

from app.ui.dnd import separar_caminhos


def test_separar_caminhos_com_espacos_e_chaves():
    dados = "{C:/minha pasta/a b.txt} D:/x.txt {/tmp/ç 'q'.csv}"
    assert separar_caminhos(tkinter.Tcl().splitlist, dados) == [
        "C:/minha pasta/a b.txt", "D:/x.txt", "/tmp/ç 'q'.csv"]


def test_separar_caminhos_vazio():
    assert separar_caminhos(tkinter.Tcl().splitlist, "") == []
