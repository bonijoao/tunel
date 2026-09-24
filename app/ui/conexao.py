import tkinter as tk
from tkinter import ttk

from app import perfis
from app.perfis import Perfil


class BarraConexao(ttk.Frame):
    """Perfis salvos, campos de conexão e botões Conectar/Desconectar. Só usar na thread da interface."""

    def __init__(self, master, ao_conectar, ao_desconectar, ao_mensagem):
        super().__init__(master)
        self._msg = ao_mensagem
        try:
            self.lista = perfis.carregar()
            aviso = None
        except Exception:
            self.lista = []
            aviso = "Aviso: o arquivo de perfis está corrompido ou em formato desconhecido; começando com a lista vazia."
        self.v = {k: tk.StringVar() for k in ("nome", "host", "login", "senha", "pasta")}
        self.v["pasta"].set("~")
        self.lembrar = tk.BooleanVar(value=True)
        self.estado = tk.StringVar(value="Desconectado")

        topo = ttk.Frame(self)
        topo.pack(fill="x")
        ttk.Label(topo, text="Perfil:").pack(side="left")
        self.combo = ttk.Combobox(topo, state="readonly", width=26)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._escolher())
        for texto, cmd in (("Novo", self._novo), ("Salvar", self._salvar), ("Excluir perfil", self._excluir)):
            ttk.Button(topo, text=texto, command=cmd).pack(side="left", padx=2)
        self.botao_desconectar = ttk.Button(topo, text="Desconectar", command=ao_desconectar, state="disabled")
        self.botao_desconectar.pack(side="right", padx=2)
        self.botao_conectar = ttk.Button(topo, text="Conectar", command=ao_conectar)
        self.botao_conectar.pack(side="right", padx=2)
        ttk.Label(topo, textvariable=self.estado).pack(side="right", padx=10)

        campos = ttk.Frame(self)
        campos.pack(fill="x", pady=(6, 0))
        rotulos = (("Nome", "nome", 14), ("Host / IP", "host", 18), ("Login", "login", 12),
                   ("Senha", "senha", 12), ("Pasta remota", "pasta", 22))
        for i, (rotulo, chave, largura) in enumerate(rotulos):
            ttk.Label(campos, text=rotulo).grid(row=0, column=2 * i, sticky="e", padx=(8, 2))
            entrada = ttk.Entry(campos, textvariable=self.v[chave], width=largura,
                                show="*" if chave == "senha" else "")
            entrada.grid(row=0, column=2 * i + 1, sticky="we")
            if chave == "senha":
                entrada.bind("<Return>", lambda _e: ao_conectar())
        ttk.Checkbutton(campos, text="Lembrar senha neste PC (cofre do sistema)",
                        variable=self.lembrar).grid(row=1, column=1, columnspan=6, sticky="w", pady=(4, 0))
        self._atualizar_combo()
        if aviso:
            self._msg(aviso)

    # ---------- leitura (thread da interface)
    def perfil(self) -> Perfil:
        return Perfil(self.v["nome"].get().strip() or self.v["host"].get().strip(),
                      self.v["host"].get().strip(), self.v["login"].get().strip(),
                      self.v["pasta"].get().strip() or "~")

    def senha(self):
        return self.v["senha"].get() or None

    def perfil_valido(self):
        p = self.perfil()
        erro = perfis.validar(p)
        if erro:
            self._msg(erro)
            return None
        return p

    def marcar_conectado(self, texto):
        if texto:
            self.estado.set("Conectado: " + texto)
            self.botao_conectar.configure(state="disabled")
            self.botao_desconectar.configure(state="normal")
        else:
            self.estado.set("Desconectado")
            self.botao_conectar.configure(state="normal")
            self.botao_desconectar.configure(state="disabled")

    # ---------- perfis
    def _atualizar_combo(self):
        self.combo["values"] = [p.nome for p in self.lista]

    def _escolher(self):
        p = next((x for x in self.lista if x.nome == self.combo.get()), None)
        if not p:
            return
        self.v["nome"].set(p.nome)
        self.v["host"].set(p.host)
        self.v["login"].set(p.login)
        self.v["pasta"].set(p.pasta_remota)
        self.v["senha"].set(perfis.ler_senha(p) or "")

    def _novo(self):
        for chave in self.v:
            self.v[chave].set("")
        self.v["pasta"].set("~")
        self.combo.set("")

    def _salvar(self):
        p = self.perfil_valido()
        if p is None:
            return
        self.lista = [x for x in self.lista if x.nome != p.nome] + [p]
        try:
            perfis.salvar(self.lista)
        except OSError as e:
            self._msg(f"Não consegui salvar os perfis: {e}")
            return
        if self.lembrar.get() and self.v["senha"].get():
            if not perfis.guardar_senha(p, self.v["senha"].get()):
                self._msg("Aviso: este sistema não tem cofre de senhas; a senha não foi guardada.")
        self._atualizar_combo()
        self.combo.set(p.nome)
        self._msg(f"Perfil '{p.nome}' salvo.")

    def _excluir(self):
        nome = self.combo.get()
        p = next((x for x in self.lista if x.nome == nome), None)
        if p is None:
            self._msg("Selecione na lista o perfil que deseja excluir.")
            return
        self.lista = [x for x in self.lista if x.nome != nome]
        try:
            perfis.salvar(self.lista)
        except OSError as e:
            self._msg(f"Não consegui salvar os perfis: {e}")
            return
        if not any(x.login == p.login and x.host == p.host for x in self.lista):
            perfis.apagar_senha(p)
        self._atualizar_combo()
        self._novo()
        self._msg(f"Perfil '{nome}' excluído.")
