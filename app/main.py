import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from app import perfis, preparar, ssh, tailscale
from app.perfis import Perfil


DICA_LOGIN = ("Abra o app na bandeja e faça login." if os.name == "nt"
              else "Rode 'sudo tailscale up' num terminal e faça login.")


class App:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        raiz.title("Túnel — acesso ao PC da universidade")
        raiz.geometry("760x620")
        try:
            self.lista = perfis.carregar()
            aviso = None
        except Exception:
            self.lista = []
            aviso = "Aviso: o arquivo de perfis está corrompido ou em formato desconhecido; começando com a lista vazia."
        self.v = {k: tk.StringVar() for k in ("nome", "host", "login", "senha", "pasta")}
        self.v["pasta"].set("~")
        self.lembrar = tk.BooleanVar(value=True)
        self._montar()
        self._atualizar_combo()
        if aviso:
            self.linha(aviso)

    # ---------- interface ----------
    def _montar(self):
        f = ttk.Frame(self.raiz, padding=10)
        f.pack(fill="both", expand=True)
        topo = ttk.Frame(f)
        topo.pack(fill="x")
        ttk.Label(topo, text="Perfil:").pack(side="left")
        self.combo = ttk.Combobox(topo, state="readonly", width=32)
        self.combo.pack(side="left", padx=6)
        self.combo.bind("<<ComboboxSelected>>", lambda _e: self._escolher())
        for txt, cmd in (("Novo", self._novo), ("Salvar", self._salvar), ("Excluir", self._excluir)):
            ttk.Button(topo, text=txt, command=cmd).pack(side="left", padx=2)

        grade = ttk.Frame(f)
        grade.pack(fill="x", pady=8)
        rotulos = (("Nome", "nome"), ("Host / IP", "host"), ("Login", "login"),
                   ("Senha", "senha"), ("Pasta remota", "pasta"))
        for i, (r, k) in enumerate(rotulos):
            ttk.Label(grade, text=r).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Entry(grade, textvariable=self.v[k], width=46,
                      show="*" if k == "senha" else "").grid(row=i, column=1, sticky="we", padx=6)
        grade.columnconfigure(1, weight=1)
        ttk.Checkbutton(grade, text="Lembrar senha neste PC (cofre do sistema)",
                        variable=self.lembrar).grid(row=5, column=1, sticky="w")

        botoes = ttk.Frame(f)
        botoes.pack(fill="x", pady=4)
        acoes = (("Testar", self.testar), ("Instalar minha chave", self.instalar_chave),
                 ("Abrir terminal", self.terminal), ("Enviar arquivo", self.enviar),
                 ("Baixar arquivo", self.baixar), ("Rodar script", self.rodar),
                 ("Estado do Tailscale", self.estado_ts), ("Preparar PC remoto", self.preparar_remoto))
        for i, (t, c) in enumerate(acoes):
            ttk.Button(botoes, text=t, command=c).grid(row=i // 4, column=i % 4, padx=2, pady=2, sticky="we")
        for c in range(4):
            botoes.columnconfigure(c, weight=1)

        self.log = tk.Text(f, height=18, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=6)

    def escrever(self, texto: str):
        def _f():
            self.log.configure(state="normal")
            self.log.insert("end", texto)
            self.log.see("end")
            self.log.configure(state="disabled")
        self.raiz.after(0, _f)

    def linha(self, texto: str):
        self.escrever(texto + "\n")

    # ---------- perfis ----------
    def _perfil_atual(self) -> Perfil:
        return Perfil(self.v["nome"].get().strip() or self.v["host"].get().strip(),
                      self.v["host"].get().strip(), self.v["login"].get().strip(),
                      self.v["pasta"].get().strip() or "~")

    def _atualizar_combo(self):
        self.combo["values"] = [p.nome for p in self.lista]

    def _escolher(self):
        p = next((x for x in self.lista if x.nome == self.combo.get()), None)
        if not p:
            return
        self.v["nome"].set(p.nome); self.v["host"].set(p.host)
        self.v["login"].set(p.login); self.v["pasta"].set(p.pasta_remota)
        self.v["senha"].set(perfis.ler_senha(p) or "")

    def _novo(self):
        for k in self.v:
            self.v[k].set("")
        self.v["pasta"].set("~")
        self.combo.set("")

    def _salvar(self):
        p = self._perfil_atual()
        if not p.host or not p.login:
            messagebox.showwarning("Túnel", "Preencha Host/IP e Login.")
            return
        self.lista = [x for x in self.lista if x.nome != p.nome] + [p]
        perfis.salvar(self.lista)
        if self.lembrar.get() and self.v["senha"].get():
            if not perfis.guardar_senha(p, self.v["senha"].get()):
                self.linha("Aviso: este sistema não tem cofre de senhas; a senha não foi guardada.")
        self._atualizar_combo()
        self.combo.set(p.nome)
        self.linha(f"Perfil '{p.nome}' salvo.")

    def _excluir(self):
        p = self._perfil_atual()
        self.lista = [x for x in self.lista if x.nome != p.nome]
        perfis.salvar(self.lista)
        perfis.apagar_senha(p)
        self._atualizar_combo()
        self._novo()

    # ---------- operações ----------
    def _conexao(self):
        p = self._perfil_atual()
        existente = Path.home() / ".ssh" / "id_ed25519"
        chave = existente if existente.exists() else None
        senha = self.v["senha"].get() or None
        return p, ssh.conectar(p, senha=senha, chave=chave)

    def _thread(self, fn):
        def alvo():
            try:
                fn()
            except Exception as e:
                self.linha("ERRO: " + ssh.traduzir_erro(e))
        threading.Thread(target=alvo, daemon=True).start()

    def testar(self):
        def f():
            self.linha("Testando conexão...")
            _, cli = self._conexao()
            _, out, _ = cli.exec_command("hostname; whoami; Rscript --version 2>&1 | head -1; python3 --version")
            self.linha(out.read().decode())
            cli.close()
            self.linha("Conexão OK.")
        self._thread(f)

    def instalar_chave(self):
        def f():
            senha = self.v["senha"].get()
            if not senha:
                self.linha("Informe a senha para instalar a chave (só é usada agora).")
                return
            ssh.instalar_chave(self._perfil_atual(), senha)
            self.linha("Chave instalada. Você já pode usar o terminal sem senha.")
        self._thread(f)

    def terminal(self):
        try:
            chave, _ = ssh.garantir_chave()
            ssh.abrir_terminal(self._perfil_atual(), chave)
        except Exception as e:
            self.linha("ERRO: " + ssh.traduzir_erro(e))

    def enviar(self):
        local = filedialog.askopenfilename(title="Arquivo para enviar")
        if not local:
            return
        def f():
            p, cli = self._conexao()
            destino = p.pasta_remota.rstrip("/") + "/" + Path(local).name
            ssh.enviar(cli, local, destino)
            cli.close()
            self.linha(f"Enviado: {local} -> {destino}")
        self._thread(f)

    def baixar(self):
        remoto = simpledialog.askstring("Baixar", "Caminho do arquivo no PC remoto:")
        if not remoto:
            return
        local = filedialog.asksaveasfilename(initialfile=Path(remoto).name)
        if not local:
            return
        def f():
            _, cli = self._conexao()
            ssh.baixar(cli, remoto, local)
            cli.close()
            self.linha(f"Baixado: {remoto} -> {local}")
        self._thread(f)

    def rodar(self):
        remoto = simpledialog.askstring("Rodar script", "Caminho do script .R ou .py no PC remoto:")
        if not remoto:
            return
        try:
            cmd = ssh.comando_script(remoto)
        except ValueError as e:
            self.linha(str(e))
            return
        def f():
            _, cli = self._conexao()
            self.linha(f"$ {cmd}")
            codigo = ssh.executar(cli, cmd, self.escrever)
            cli.close()
            self.linha(f"\n[terminou com código {codigo}]")
        self._thread(f)

    def estado_ts(self):
        def f():
            estado = tailscale.status()
            msg = {
                "nao_instalado": "Tailscale não instalado. Baixe em https://tailscale.com/download",
                "deslogado": "Tailscale instalado mas deslogado. " + DICA_LOGIN,
                "parado": "Tailscale parado. " + DICA_LOGIN,
                "conectado": "Tailscale conectado.",
                "desconhecido": "Não consegui interpretar o estado do Tailscale.",
            }[estado]
            self.linha(msg)
        self._thread(f)

    def preparar_remoto(self):
        chave = simpledialog.askstring("Auth key", "Cole a auth key do Tailscale (tskey-auth-...):", show="*")
        if not chave:
            return
        pasta = simpledialog.askstring("Pasta", "Pasta no PC remoto para o Tailscale:",
                                       initialvalue="~/tailscale")
        if not pasta:
            return
        host = simpledialog.askstring("Nome", "Nome desta máquina no Tailscale:",
                                      initialvalue="uni-" + self.v["login"].get())
        if not host:
            return
        script = preparar.gerar_script(pasta, "********", host)
        if not messagebox.askyesno(
                "Confirmar",
                "Isto vai baixar e iniciar o Tailscale no PC remoto e criar uma linha @reboot no crontab.\n\n"
                + script + "\nExecutar?"):
            return
        def f():
            _, cli = self._conexao()
            codigo = preparar.preparar(cli, pasta, chave, host, self.escrever)
            cli.close()
            self.linha(f"\n[preparação terminou com código {codigo}]")
        self._thread(f)


def main():
    raiz = tk.Tk()
    App(raiz)
    raiz.mainloop()
