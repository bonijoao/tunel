import sys
from pathlib import Path

from app import recursos


def test_constantes():
    assert recursos.NOME_APP == "Tunel-LAD" and recursos.VERSAO


def test_caminho_recurso_no_codigo_fonte():
    p = recursos.caminho_recurso("assets/icone.png")
    assert p == Path(recursos.__file__).resolve().parent.parent / "assets" / "icone.png"


def test_caminho_recurso_congelado(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert recursos.caminho_recurso("assets/icone.ico") == tmp_path / "assets" / "icone.ico"


def test_aplicar_icone_nunca_levanta():
    class RaizQuebrada:
        def iconbitmap(self, *a, **k):
            raise RuntimeError("x")

        def iconphoto(self, *a, **k):
            raise RuntimeError("x")

        def tk(self):
            raise RuntimeError("x")
    recursos.aplicar_icone(RaizQuebrada())
