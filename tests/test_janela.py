import tkinter as tk

import pytest


def _raiz():
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("sem display")


def test_janela_constroi_e_navega_no_local(tmp_path):
    raiz = _raiz()
    try:
        from app.ui.janela import JanelaPrincipal
        (tmp_path / "dados.csv").write_text("a,b")
        j = JanelaPrincipal(raiz, None)
        raiz.update()
        j._pedir_local(str(tmp_path))
        raiz.update()
        assert [e.nome for e in j.local.selecionados()] == []
        assert j.local.caminho_atual() == str(tmp_path)
        assert len(j.local.arvore.get_children()) == 1
        assert j.sessao is None and j.conectado() is False
        assert raiz.title() == "Tunel-LAD"
    finally:
        raiz.destroy()
