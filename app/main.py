from app.ui.dnd import criar_raiz
from app.ui.janela import JanelaPrincipal


def main():
    raiz, dnd_files = criar_raiz()
    JanelaPrincipal(raiz, dnd_files)
    raiz.mainloop()
