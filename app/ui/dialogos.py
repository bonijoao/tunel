import threading
import tkinter as tk
from tkinter import ttk


def na_thread_principal(raiz, fn):
    """Roda `fn` na thread da interface e devolve o resultado para a thread de trabalho que chamou."""
    resultado = {}
    pronto = threading.Event()

    def _f():
        try:
            resultado["v"] = fn()
        except BaseException as exc:  # repassa para quem esperava
            resultado["e"] = exc
        finally:
            pronto.set()

    raiz.after(0, _f)
    pronto.wait()
    if "e" in resultado:
        raise resultado["e"]
    return resultado["v"]


def confirmar_apagar(raiz, nomes: list[str], tem_pasta: bool) -> bool:
    janela = tk.Toplevel(raiz)
    janela.title("Apagar do PC remoto")
    janela.transient(raiz)
    janela.resizable(False, False)
    resposta = {"ok": False}
    mostrados = nomes[:10]
    texto = "Apagar permanentemente:\n\n" + "\n".join("• " + n for n in mostrados)
    if len(nomes) > len(mostrados):
        texto += f"\n… e mais {len(nomes) - len(mostrados)}"
    texto += "\n\nNão existe lixeira: a exclusão é permanente."
    if tem_pasta:
        texto += "\nInclui todo o conteúdo das pastas."
    ttk.Label(janela, text=texto, justify="left", padding=12).pack()
    barra = ttk.Frame(janela, padding=(12, 0, 12, 12))
    barra.pack(fill="x")

    def fechar(v):
        resposta["ok"] = v
        janela.destroy()

    cancelar = ttk.Button(barra, text="Cancelar", command=lambda: fechar(False))
    cancelar.pack(side="right")
    ttk.Button(barra, text="Apagar", command=lambda: fechar(True)).pack(side="right", padx=6)
    cancelar.focus_set()
    janela.bind("<Return>", lambda _e: fechar(False))
    janela.bind("<Escape>", lambda _e: fechar(False))
    janela.protocol("WM_DELETE_WINDOW", lambda: fechar(False))
    janela.grab_set()
    raiz.wait_window(janela)
    return resposta["ok"]


def perguntar_conflito(raiz, caminho: str):
    """Devolve (acao, aplicar_a_todos); acao é 'substituir', 'pular' ou 'cancelar'."""
    janela = tk.Toplevel(raiz)
    janela.title("Item já existe")
    janela.transient(raiz)
    janela.resizable(False, False)
    resposta = {"acao": "cancelar"}
    todos = tk.BooleanVar(value=False)
    ttk.Label(janela, text=f"Já existe:\n{caminho}", justify="left", padding=12).pack()
    ttk.Checkbutton(janela, text="Aplicar a todos os próximos", variable=todos).pack(anchor="w", padx=12)
    barra = ttk.Frame(janela, padding=12)
    barra.pack(fill="x")

    def escolher(acao):
        resposta["acao"] = acao
        janela.destroy()

    for rotulo, acao in (("Cancelar tudo", "cancelar"), ("Pular", "pular"), ("Substituir", "substituir")):
        ttk.Button(barra, text=rotulo, command=lambda a=acao: escolher(a)).pack(side="right", padx=3)
    janela.protocol("WM_DELETE_WINDOW", lambda: escolher("cancelar"))
    janela.grab_set()
    raiz.wait_window(janela)
    return resposta["acao"], bool(todos.get())
