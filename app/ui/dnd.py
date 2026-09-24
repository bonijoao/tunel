import tkinter as tk


def separar_caminhos(splitlist, dados: str) -> list[str]:
    return [c for c in splitlist(dados) if c]


def criar_raiz():
    """Cria a janela raiz; devolve (raiz, DND_FILES). Sem o componente de arrastar do sistema, DND_FILES é None."""
    raiz = tk.Tk()
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        TkinterDnD._require(raiz)
        return raiz, DND_FILES
    except Exception:
        return raiz, None


def registrar_soltar_arquivos(widget, dnd_files, ao_soltar) -> bool:
    """Liga 'soltar arquivos do sistema' no widget. Devolve False (sem erro) se não for possível."""
    try:
        def _soltou(ev):
            caminhos = separar_caminhos(widget.tk.splitlist, ev.data)
            if caminhos:
                ao_soltar(caminhos)
            return ev.action
        widget.drop_target_register(dnd_files)
        widget.dnd_bind("<<Drop>>", _soltou)
        return True
    except Exception:
        return False
