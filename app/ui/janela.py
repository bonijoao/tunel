import os
import posixpath
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog, ttk

from app import arquivos, ssh
from app.arquivos import PoliticaConflito
from app.recursos import NOME_APP, VERSAO, aplicar_icone
from app.sessao import Fila, Sessao
from app.ui import dialogos
from app.ui.arrasto import decidir_arrasto
from app.ui.conexao import BarraConexao
from app.ui.dnd import registrar_soltar_arquivos
from app.ui.ferramentas import Ferramentas
from app.ui.log import PainelLog
from app.ui.painel import PainelArquivos


class JanelaPrincipal:
    def __init__(self, raiz, dnd_files=None):
        self.raiz = raiz
        raiz.title(NOME_APP)
        raiz.geometry("1180x760")
        raiz.minsize(940, 580)
        aplicar_icone(raiz)
        self.sessao = None
        self.perfil_conectado = None
        self._pasta_perfil = None

        corpo = ttk.Frame(raiz, padding=8)
        corpo.pack(fill="both", expand=True)
        self.log = PainelLog(corpo, raiz)
        self.fila = Fila(lambda f: raiz.after(0, f), ao_ocupado=self.log.ocupado)
        self.barra = BarraConexao(corpo, self.conectar, self.desconectar, self.log.linha)
        self.barra.pack(fill="x")

        meio = ttk.Frame(corpo)
        meio.pack(fill="both", expand=True, pady=8)
        meio.columnconfigure(0, weight=1)
        meio.columnconfigure(2, weight=1)
        meio.rowconfigure(0, weight=1)
        self.local = PainelArquivos(
            meio, "Local (este computador)", "local", pai_fn=lambda c: str(Path(c).parent),
            ao_pedir_caminho=self._pedir_local, ao_soltar=self._ao_soltar,
            acoes=[("Enviar", self.enviar, None), ("Enviar e rodar", self.enviar_e_rodar, None),
                   ("Atualizar", self._atualizar_local, "<F5>")])
        self.local.grid(row=0, column=0, sticky="nsew")
        botoes = ttk.Frame(meio, padding=6)
        botoes.grid(row=0, column=1, sticky="ns")
        for texto, cmd in (("Enviar ►", self.enviar), ("◄ Baixar", self.baixar), ("Rodar ▶", self.rodar)):
            ttk.Button(botoes, text=texto, command=cmd, width=10).pack(pady=6)
        self.remoto = PainelArquivos(
            meio, "Remoto (PC da universidade)", "remoto", pai_fn=posixpath.dirname,
            ao_pedir_caminho=self._pedir_remoto, ao_soltar=self._ao_soltar,
            acoes=[("Baixar", self.baixar, None), ("Rodar", self.rodar, None),
                   ("Renomear (F2)", self.renomear, "<F2>"), ("Mover para…", self.mover_para, None),
                   ("Nova pasta", self.nova_pasta, None), ("Apagar (Delete)", self.apagar, "<Delete>"),
                   ("Atualizar", self._atualizar_remoto, "<F5>")])
        self.remoto.grid(row=0, column=2, sticky="nsew")
        self.log.pack(fill="both", expand=False)

        self.ferramentas = Ferramentas(self)
        self._montar_menu()
        self.dnd_ativo = bool(dnd_files) and registrar_soltar_arquivos(
            self.remoto.arvore, dnd_files, self._ao_soltar_do_sistema)
        self._pedir_local(str(Path.home()))
        self.log.linha("Arrastar do sistema para o painel Remoto: "
                       + ("ativado." if self.dnd_ativo else "indisponível neste ambiente (use os painéis)."))
        raiz.protocol("WM_DELETE_WINDOW", self._fechar)

    # ---------- menu
    def _montar_menu(self):
        menu = tk.Menu(self.raiz)
        f = self.ferramentas
        ferr = tk.Menu(menu, tearoff=0)
        for rotulo, cmd in (("Instalar minha chave SSH", f.instalar_chave), ("Abrir terminal", f.abrir_terminal),
                            ("Informações do PC remoto", f.informacoes), ("Estado do Tailscale", f.estado_tailscale),
                            ("Entrar no Tailscale (auth key)", f.entrar_tailscale),
                            ("Preparar PC remoto", f.preparar_remoto)):
            ferr.add_command(label=rotulo, command=cmd)
        menu.add_cascade(label="Ferramentas", menu=ferr)
        ajuda = tk.Menu(menu, tearoff=0)
        ajuda.add_command(label="Sobre", command=lambda: self.log.linha(f"{NOME_APP} {VERSAO}"))
        menu.add_cascade(label="Ajuda", menu=ajuda)
        self.raiz.configure(menu=menu)

    # ---------- estado
    def conectado(self) -> bool:
        if self.sessao is None:
            self.log.linha("Conecte-se primeiro (botão Conectar).")
            return False
        return True

    def _chave_existente(self):
        p = Path.home() / ".ssh" / "id_ed25519"
        return p if p.exists() else None

    def conectar(self):
        perfil = self.barra.perfil_valido()
        if perfil is None:
            return
        senha = self.barra.senha()
        chave = self._chave_existente()
        if self.sessao is not None:
            self.desconectar()
        sessao = Sessao(lambda: ssh.conectar(perfil, senha=senha, chave=chave))
        self.sessao = sessao
        self.perfil_conectado = perfil
        self.log.linha(f"Conectando a {perfil.login}@{perfil.host}...")

        def tarefa():
            sessao.conectar()
            home = sessao.home()
            pasta = arquivos.expandir_remoto(perfil.pasta_remota, home)
            sftp = sessao.sftp()
            try:
                itens = arquivos.listar_remoto(sftp, pasta)
            except (FileNotFoundError, PermissionError):
                self.log.linha(f"Aviso: não consegui abrir '{pasta}'; abrindo a pasta pessoal.")
                pasta = home
                itens = arquivos.listar_remoto(sftp, pasta)
            return pasta, itens

        def pronto(resultado):
            self._pasta_perfil = resultado[0]
            self.remoto.mostrar(*resultado)
            self.barra.marcar_conectado(f"{perfil.login}@{perfil.host}")
            self.log.linha("Conectado.")

        def falhou(mensagem):
            self.log.linha_erro(mensagem)
            self.sessao = None
            self.perfil_conectado = None
            self.barra.marcar_conectado(None)

        self.fila.enfileirar(tarefa, self._se_atual(sessao, pronto), self._se_atual(sessao, falhou))

    def desconectar(self):
        if self.sessao is not None:
            sessao, self.sessao = self.sessao, None
            self.fila.enfileirar(sessao.fechar)
        self.perfil_conectado = None
        self._pasta_perfil = None
        self.remoto.limpar()
        self.barra.marcar_conectado(None)
        self.log.linha("Desconectado.")

    def _fechar(self):
        if self.sessao is not None:
            try:
                self.sessao.fechar()
            except Exception:
                pass
        self.raiz.destroy()

    # ---------- navegação
    def _pedir_local(self, caminho):
        caminho = os.path.abspath(os.path.expanduser(caminho))
        try:
            entradas = arquivos.listar_local(caminho)
        except OSError as e:
            self.log.linha(f"Não consegui abrir '{caminho}': {e}")
            return
        self.local.mostrar(caminho, entradas)

    def _atualizar_local(self):
        if self.local.caminho_atual():
            self._pedir_local(self.local.caminho_atual())

    def _pedir_remoto(self, caminho):
        if not self.conectado():
            return
        self._listar_remoto(caminho)

    def _atualizar_remoto(self):
        if self.remoto.caminho_atual():
            self._pedir_remoto(self.remoto.caminho_atual())

    def _listar_remoto(self, caminho):
        sessao = self.sessao

        def tarefa():
            destino = arquivos.expandir_remoto(caminho, sessao.home())
            return destino, arquivos.listar_remoto(sessao.sftp(), destino)

        self.fila.enfileirar(tarefa, self._se_atual(sessao, lambda r: self.remoto.mostrar(*r)),
                             self._erro_de(sessao, recarregar=False))

    def _se_atual(self, sessao, callback):
        """Só deixa o callback mexer na janela se `sessao` ainda for a conexão atual."""
        def _f(arg):
            if self.sessao is sessao:
                callback(arg)
        return _f

    def _depois_remoto(self, mensagem, sessao):
        def _f(resultado):
            pasta, itens = resultado
            self.log.linha(mensagem)
            if self.remoto.caminho_atual() == pasta:
                self.remoto.mostrar(pasta, itens)
        return self._se_atual(sessao, _f)

    def _erro_de(self, sessao, recarregar=True):
        """Callback de erro de uma operação da conexão `sessao`; se a conexão caiu, volta a Desconectado."""
        def _f(mensagem):
            self.log.linha_erro(mensagem)
            if not sessao.conectado():
                self._perdeu_conexao(sessao)
            elif recarregar and self.remoto.caminho_atual():
                self._listar_remoto(self.remoto.caminho_atual())
        return self._se_atual(sessao, _f)

    def _perdeu_conexao(self, sessao):
        self.sessao = None
        self.perfil_conectado = None
        self._pasta_perfil = None
        self.fila.enfileirar(sessao.fechar)
        self.remoto.limpar()
        self.barra.marcar_conectado(None)
        self.log.linha("Conexão perdida. Clique em Conectar.")

    def _remoto_pronto(self):
        if not self.remoto.caminho_atual():
            self.log.linha("Aguarde a conexão terminar.")
            return False
        return True

    def _politica(self):
        return PoliticaConflito(lambda caminho: dialogos.na_thread_principal(
            self.raiz, lambda: dialogos.perguntar_conflito(self.raiz, caminho)))

    # ---------- transferência
    def enviar(self):
        self._enviar([e.caminho for e in self.local.selecionados()], self.remoto.caminho_atual())

    def _enviar(self, locais, destino):
        if not self.conectado() or not self._remoto_pronto():
            return
        if not locais:
            self.log.linha("Selecione arquivos ou pastas no painel Local.")
            return
        sessao, politica = self.sessao, self._politica()

        def tarefa():
            arquivos.enviar_itens(sessao.sftp(), locais, destino, politica, self.log.definir_progresso)
            return destino, arquivos.listar_remoto(sessao.sftp(), destino)

        self.fila.enfileirar(tarefa, self._depois_remoto(f"Enviado(s): {len(locais)} item(ns).", sessao),
                             self._erro_de(sessao))

    def baixar(self):
        self._baixar(self.remoto.selecionados(), self.local.caminho_atual())

    def _baixar(self, entradas, destino):
        if not self.conectado():
            return
        if not entradas:
            self.log.linha("Selecione arquivos ou pastas no painel Remoto.")
            return
        sessao, politica = self.sessao, self._politica()

        def tarefa():
            arquivos.baixar_itens(sessao.sftp(), entradas, destino, politica, self.log.definir_progresso)
            return destino

        def pronto(pasta):
            self.log.linha(f"Baixado(s): {len(entradas)} item(ns) para {pasta}")
            if self.local.caminho_atual() == pasta:
                self._pedir_local(pasta)

        self.fila.enfileirar(tarefa, self._se_atual(sessao, pronto), self._erro_de(sessao, recarregar=False))

    def _ao_soltar_do_sistema(self, caminhos):
        if self.sessao is None:
            self.log.linha("Conecte-se primeiro para enviar arquivos arrastados.")
            return
        if not self._remoto_pronto():
            return
        self._enviar(caminhos, self.remoto.caminho_atual())

    def _ao_soltar(self, origem, entradas, alvo, entrada_alvo):
        decisao = decidir_arrasto(origem.lado, alvo.lado, alvo.caminho_atual(), origem.caminho_atual(),
                                  entrada_alvo, entradas)
        if decisao is None:
            return
        acao, destino = decisao
        if acao == "enviar":
            self._enviar([e.caminho for e in entradas], destino)
        elif acao == "baixar":
            self._baixar(entradas, destino)
        elif acao == "mover":
            self._mover([e.caminho for e in entradas], destino)

    # ---------- rodar script
    def rodar(self):
        sel = self.remoto.selecionados()
        if len(sel) != 1 or sel[0].eh_pasta:
            self.log.linha("Selecione UM script (.R ou .py) no painel Remoto.")
            return
        self._rodar_caminho(sel[0].caminho)

    def enviar_e_rodar(self):
        sel = self.local.selecionados()
        if len(sel) != 1 or sel[0].eh_pasta:
            self.log.linha("Selecione UM script (.R ou .py) no painel Local.")
            return
        if not self.conectado() or not self._remoto_pronto():
            return
        destino = self.remoto.caminho_atual()
        remoto = posixpath.join(destino, sel[0].nome)
        self._rodar_caminho(remoto, enviar_antes=(sel[0].caminho, destino))

    def _rodar_caminho(self, caminho, enviar_antes=None):
        if not self.conectado():
            return
        try:
            cmd = ssh.comando_script_na_pasta(caminho)
        except ValueError as e:
            self.log.linha(str(e))
            return
        sessao, politica = self.sessao, self._politica()
        atual = self.remoto.caminho_atual()

        def tarefa():
            if enviar_antes:
                arquivos.enviar_itens(sessao.sftp(), [enviar_antes[0]], enviar_antes[1], politica)
            self.log.linha(f"$ {cmd}")
            codigo = ssh.executar(sessao.obter(), cmd, self.log.escrever)
            return atual, arquivos.listar_remoto(sessao.sftp(), atual), codigo

        def pronto(resultado):
            pasta, itens, codigo = resultado
            self.log.linha(f"\n[terminou com código {codigo}]")
            if self.remoto.caminho_atual() == pasta:
                self.remoto.mostrar(pasta, itens)

        self.fila.enfileirar(tarefa, self._se_atual(sessao, pronto), self._erro_de(sessao))

    # ---------- operações remotas
    def renomear(self):
        sel = self.remoto.selecionados()
        if not self.conectado():
            return
        if len(sel) != 1:
            self.log.linha("Selecione UM item para renomear.")
            return
        item = sel[0]
        novo = simpledialog.askstring("Renomear", "Novo nome:", initialvalue=item.nome, parent=self.raiz)
        if not novo or novo == item.nome:
            return
        erro = arquivos.validar_nome(novo)
        if erro:
            self.log.linha(erro)
            return
        sessao, atual = self.sessao, self.remoto.caminho_atual()

        def tarefa():
            arquivos.renomear(sessao.sftp(), item.caminho, novo)
            return atual, arquivos.listar_remoto(sessao.sftp(), atual)

        self.fila.enfileirar(tarefa, self._depois_remoto(f"Renomeado: {item.nome} -> {novo}", sessao),
                             self._erro_de(sessao))

    def mover_para(self):
        sel = self.remoto.selecionados()
        if not self.conectado() or not self._remoto_pronto():
            return
        if not sel:
            self.log.linha("Selecione itens no painel Remoto.")
            return
        destino = simpledialog.askstring("Mover para…", "Pasta de destino no PC remoto:",
                                         initialvalue=self.remoto.caminho_atual(), parent=self.raiz)
        if destino:
            self._mover([e.caminho for e in sel], destino)

    def _mover(self, caminhos, destino):
        if not self.conectado() or not self._remoto_pronto():
            return
        sessao, atual = self.sessao, self.remoto.caminho_atual()

        def tarefa():
            alvo = arquivos.expandir_remoto(destino, sessao.home())
            movidos, ignorados = arquivos.mover(sessao.sftp(), caminhos, alvo)
            for c, motivo in ignorados:
                self.log.linha(f"Ignorado {posixpath.basename(c)}: {motivo}.")
            return atual, arquivos.listar_remoto(sessao.sftp(), atual)

        self.fila.enfileirar(tarefa, self._depois_remoto(f"Mover: {len(caminhos)} item(ns) processado(s).", sessao),
                             self._erro_de(sessao))

    def nova_pasta(self):
        if not self.conectado() or not self._remoto_pronto():
            return
        nome = simpledialog.askstring("Nova pasta", "Nome da nova pasta:", parent=self.raiz)
        if not nome:
            return
        erro = arquivos.validar_nome(nome)
        if erro:
            self.log.linha(erro)
            return
        sessao, atual = self.sessao, self.remoto.caminho_atual()

        def tarefa():
            arquivos.criar_pasta_remota(sessao.sftp(), atual, nome)
            return atual, arquivos.listar_remoto(sessao.sftp(), atual)

        self.fila.enfileirar(tarefa, self._depois_remoto(f"Pasta criada: {nome}", sessao), self._erro_de(sessao))

    def apagar(self):
        if not self.conectado():
            return
        sel = self.remoto.selecionados()
        if not sel:
            self.log.linha("Selecione itens no painel Remoto.")
            return
        if not dialogos.confirmar_apagar(self.raiz, [e.nome for e in sel], any(e.eh_pasta for e in sel)):
            return
        caminhos = [e.caminho for e in sel]
        sessao, pasta_perfil, atual = self.sessao, self._pasta_perfil, self.remoto.caminho_atual()

        def tarefa():
            home = sessao.home()
            arquivos.apagar_itens(sessao.sftp(), caminhos, home, pasta_perfil or home,
                                  self.log.definir_progresso)
            return atual, arquivos.listar_remoto(sessao.sftp(), atual)

        self.fila.enfileirar(tarefa, self._depois_remoto(f"Apagado(s): {len(caminhos)} item(ns).", sessao),
                             self._erro_de(sessao))
