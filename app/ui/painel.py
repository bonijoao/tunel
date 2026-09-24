import tkinter as tk
from tkinter import ttk

from app.arquivos import Entrada, formatar_data, formatar_tamanho

_MODIFICADORES = 0x0001 | 0x0004  # Shift | Control


class PainelArquivos(ttk.Frame):
    """Lista de arquivos de um lado (local ou remoto). É passivo: quem manda navegar é o dono."""

    def __init__(self, master, titulo, lado, pai_fn, ao_pedir_caminho, ao_soltar=None, acoes=None):
        super().__init__(master)
        self.lado = lado
        self._pai_fn = pai_fn
        self._ao_pedir = ao_pedir_caminho
        self._ao_soltar = ao_soltar
        self._acoes = acoes or []
        self._entradas = {}
        self._caminho = ""
        self._arrastando = False
        self._pendente = None
        self._inicio = (0, 0)

        ttk.Label(self, text=titulo, font=("", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        barra = ttk.Frame(self)
        barra.grid(row=1, column=0, columnspan=2, sticky="we", pady=2)
        ttk.Button(barra, text="Subir", width=6, command=self._subir).pack(side="left")
        ttk.Button(barra, text="Atualizar", width=9, command=self._atualizar).pack(side="left", padx=3)
        self.var_caminho = tk.StringVar()
        entrada = ttk.Entry(barra, textvariable=self.var_caminho)
        entrada.pack(side="left", fill="x", expand=True)
        entrada.bind("<Return>", lambda _e: self._ao_pedir(self.var_caminho.get()))

        self.arvore = ttk.Treeview(self, columns=("tamanho", "data"), selectmode="extended")
        self.arvore.heading("#0", text="Nome")
        self.arvore.heading("tamanho", text="Tamanho")
        self.arvore.heading("data", text="Modificado")
        self.arvore.column("#0", width=230)
        self.arvore.column("tamanho", width=80, anchor="e")
        self.arvore.column("data", width=125)
        rolagem = ttk.Scrollbar(self, command=self.arvore.yview)
        self.arvore.configure(yscrollcommand=rolagem.set)
        self.arvore.grid(row=2, column=0, sticky="nsew")
        rolagem.grid(row=2, column=1, sticky="ns")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        self.arvore.bind("<Double-1>", self._duplo_clique)
        self.arvore.bind("<ButtonPress-1>", self._pressionou)
        self.arvore.bind("<B1-Motion>", self._moveu)
        self.arvore.bind("<ButtonRelease-1>", self._soltou)
        self.arvore.bind("<Button-3>", self._menu)
        for _rotulo, funcao, sequencia in self._acoes:
            if sequencia:
                self.arvore.bind(sequencia, lambda _e, f=funcao: f())

    # ---------- API
    def mostrar(self, caminho, entradas):
        self._caminho = caminho
        self.var_caminho.set(caminho)
        self.arvore.delete(*self.arvore.get_children())
        self._entradas = {}
        for e in entradas:
            iid = self.arvore.insert(
                "", "end", text=("▸ " if e.eh_pasta else "   ") + e.nome,
                values=("" if e.eh_pasta else formatar_tamanho(e.tamanho), formatar_data(e.mtime)))
            self._entradas[iid] = e

    def caminho_atual(self) -> str:
        return self._caminho

    def selecionados(self) -> list[Entrada]:
        return [self._entradas[i] for i in self.arvore.selection() if i in self._entradas]

    def limpar(self):
        self.mostrar("", [])

    # ---------- navegação
    def _subir(self):
        if self._caminho:
            self._ao_pedir(self._pai_fn(self._caminho))

    def _atualizar(self):
        if self._caminho:
            self._ao_pedir(self._caminho)

    def _duplo_clique(self, ev):
        e = self._entradas.get(self.arvore.identify_row(ev.y))
        if e is not None and e.eh_pasta:
            self._ao_pedir(e.caminho)

    # ---------- arrastar entre painéis
    def _pressionou(self, ev):
        iid = self.arvore.identify_row(ev.y)
        self._arrastando = False
        self._pendente = None
        self._inicio = (ev.x_root, ev.y_root)
        self.arvore.focus_set()
        if iid and iid in self.arvore.selection() and not (ev.state & _MODIFICADORES):
            self._pendente = iid
            return "break"

    def _moveu(self, ev):
        if self._arrastando or self._ao_soltar is None or not self.arvore.selection():
            return
        if max(abs(ev.x_root - self._inicio[0]), abs(ev.y_root - self._inicio[1])) > 6:
            self._arrastando = True
            self.arvore.configure(cursor="hand2")

    def _soltou(self, ev):
        if self._arrastando:
            self._arrastando = False
            self.arvore.configure(cursor="")
            self._terminar_arrasto(ev)
        elif self._pendente:
            self.arvore.selection_set(self._pendente)
        self._pendente = None

    def _terminar_arrasto(self, ev):
        entradas = self.selecionados()
        if not entradas:
            return
        widget = self.winfo_containing(ev.x_root, ev.y_root)
        painel = widget
        while painel is not None and not isinstance(painel, PainelArquivos):
            painel = getattr(painel, "master", None)
        if painel is None:
            return
        y = ev.y_root - painel.arvore.winfo_rooty()
        alvo = painel._entradas.get(painel.arvore.identify_row(y))
        self._ao_soltar(self, entradas, painel, alvo)

    # ---------- menu de contexto
    def _menu(self, ev):
        iid = self.arvore.identify_row(ev.y)
        if iid and iid not in self.arvore.selection():
            self.arvore.selection_set(iid)
        if not self._acoes:
            return
        menu = tk.Menu(self, tearoff=0)
        for rotulo, funcao, _sequencia in self._acoes:
            menu.add_command(label=rotulo, command=funcao)
        menu.tk_popup(ev.x_root, ev.y_root)
