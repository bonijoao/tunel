import os
import sys
import tkinter as tk
from pathlib import Path

NOME_APP = "Tunel-LAD"
VERSAO = "1.0.0"


def caminho_recurso(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    raiz = Path(base) if base else Path(__file__).resolve().parent.parent
    return raiz / rel


def aplicar_icone(raiz) -> None:
    """Coloca o ícone na janela; qualquer falha é ignorada (o app funciona sem ícone)."""
    try:
        if os.name == "nt":
            raiz.iconbitmap(default=str(caminho_recurso("assets/icone.ico")))
        else:
            imagem = tk.PhotoImage(file=str(caminho_recurso("assets/icone.png")))
            raiz._icone = imagem
            raiz.iconphoto(True, imagem)
    except Exception:
        pass
