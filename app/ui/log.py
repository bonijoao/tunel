import tkinter as tk
from tkinter import ttk


class PainelLog(ttk.Frame):
    """Log rolável, indicador de operação e barra de progresso. Métodos seguros para qualquer thread."""

    def __init__(self, master, raiz):
        super().__init__(master)
        self._raiz = raiz
        self.texto = tk.Text(self, height=9, state="disabled", wrap="word")
        barra = ttk.Scrollbar(self, command=self.texto.yview)
        self.texto.configure(yscrollcommand=barra.set)
        self.texto.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        rodape = ttk.Frame(self)
        rodape.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self._status = tk.StringVar(value="Pronto.")
        ttk.Label(rodape, textvariable=self._status).pack(side="left")
        self._barra = ttk.Progressbar(rodape, length=200, mode="determinate", maximum=100)
        self._barra.pack(side="right")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def _na_ui(self, fn):
        self._raiz.after(0, fn)

    def escrever(self, texto: str) -> None:
        def _f():
            self.texto.configure(state="normal")
            self.texto.insert("end", texto)
            self.texto.see("end")
            self.texto.configure(state="disabled")
        self._na_ui(_f)

    def linha(self, texto: str) -> None:
        self.escrever(texto + "\n")

    def linha_erro(self, texto: str) -> None:
        self.linha("ERRO: " + texto)

    def definir_progresso(self, i: int, n: int, nome: str) -> None:
        def _f():
            self._barra["value"] = 100 * (i - 1) / n if n else 0
            self._status.set(f"{i} de {n}: {nome}")
        self._na_ui(_f)

    def ocupado(self, sim: bool) -> None:
        def _f():
            if not sim:
                self._barra["value"] = 0
                self._status.set("Pronto.")
            elif self._status.get() == "Pronto.":
                self._status.set("Trabalhando...")
        self._na_ui(_f)
