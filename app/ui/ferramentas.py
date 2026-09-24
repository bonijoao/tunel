import os
import subprocess
import webbrowser
from pathlib import Path
from tkinter import messagebox, simpledialog

from app import preparar, ssh, tailscale

DICA_LOGIN = ("Abra o app na bandeja e faça login." if os.name == "nt"
              else "Rode 'sudo tailscale up' num terminal e faça login.")


class Ferramentas:
    """Ações avançadas do menu Ferramentas. Toda função de trabalho se chama `tarefa` e não lê Tk."""

    def __init__(self, janela):
        self.j = janela

    def instalar_chave(self):
        perfil = self.j.barra.perfil_valido()
        senha = self.j.barra.senha() or ""
        if perfil is None:
            return
        if not senha:
            self.j.log.linha("Informe a senha para instalar a chave (ela só é usada agora).")
            return

        def tarefa():
            ssh.instalar_chave(perfil, senha)

        self.j.fila.enfileirar(
            tarefa,
            lambda _r: self.j.log.linha("Chave instalada. Você já pode entrar sem senha e abrir o terminal."),
            self.j.log.linha_erro)

    def abrir_terminal(self):
        perfil = self.j.barra.perfil_valido()
        if perfil is None:
            return
        try:
            existente = Path.home() / ".ssh" / "id_ed25519"
            ssh.abrir_terminal(perfil, existente if existente.exists() else None)
        except Exception as e:
            self.j.log.linha_erro(ssh.traduzir_erro(e))

    def informacoes(self):
        if not self.j.conectado():
            return
        sessao = self.j.sessao

        def tarefa():
            _, saida, _ = sessao.obter().exec_command(
                "hostname; whoami; Rscript --version 2>&1 | head -1; python3 --version")
            return saida.read().decode(errors="replace")

        self.j.fila.enfileirar(tarefa, self.j.log.linha, self.j.log.linha_erro)

    def estado_tailscale(self):
        def tarefa():
            return tailscale.status()

        def mostrar(estado):
            mensagens = {
                "nao_instalado": "Tailscale não instalado. Abrindo https://tailscale.com/download",
                "deslogado": "Tailscale instalado mas deslogado. " + DICA_LOGIN,
                "parado": "Tailscale parado. " + DICA_LOGIN,
                "conectado": "Tailscale conectado.",
                "desconhecido": "Não consegui interpretar o estado do Tailscale.",
            }
            self.j.log.linha(mensagens[estado])
            if estado == "nao_instalado":
                webbrowser.open("https://tailscale.com/download")

        self.j.fila.enfileirar(tarefa, mostrar, self.j.log.linha_erro)

    def entrar_tailscale(self):
        chave = simpledialog.askstring("Auth key", "Cole a auth key do Tailscale (tskey-auth-...):",
                                       show="*", parent=self.j.raiz)
        if not chave:
            return

        def tarefa():
            if not tailscale.caminho():
                return "Tailscale não instalado. Baixe em https://tailscale.com/download"
            try:
                r = subprocess.run(tailscale.comando_up(chave), capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                return "O Tailscale demorou demais para responder (60 s). Tente de novo."
            except OSError as e:
                return tailscale.mascarar(f"Não consegui executar o Tailscale: {e}", chave)
            saida = tailscale.mascarar((r.stdout or "") + (r.stderr or ""), chave).strip()
            linhas = [saida] if saida else []
            if r.returncode == 0:
                linhas.append("Tailscale: login concluído.")
            else:
                linhas.append(f"O Tailscale terminou com código {r.returncode}.")
                if os.name != "nt":
                    linhas.append("Dica: em Linux pode ser preciso rodar 'sudo tailscale up' num terminal.")
            return "\n".join(linhas)

        self.j.fila.enfileirar(tarefa, self.j.log.linha, self.j.log.linha_erro)

    def preparar_remoto(self):
        if not self.j.conectado():
            return
        chave = simpledialog.askstring("Auth key", "Cole a auth key do Tailscale (tskey-auth-...):",
                                       show="*", parent=self.j.raiz)
        if not chave:
            return
        pasta = simpledialog.askstring("Pasta", "Pasta no PC remoto para o Tailscale:",
                                       initialvalue="~/tailscale", parent=self.j.raiz)
        if not pasta:
            return
        login = (self.j.barra.perfil().login or "pc")
        host = simpledialog.askstring("Nome", "Nome desta máquina no Tailscale:",
                                      initialvalue="uni-" + login, parent=self.j.raiz)
        if not host:
            return
        script = preparar.gerar_script(pasta, "********", host)
        if not messagebox.askyesno(
                "Confirmar",
                "Isto vai baixar e iniciar o Tailscale no PC remoto e criar uma linha @reboot no crontab.\n\n"
                + script + "\nExecutar?", parent=self.j.raiz):
            return
        sessao = self.j.sessao

        def tarefa():
            return preparar.preparar(sessao.obter(), pasta, chave, host, self.j.log.escrever)

        self.j.fila.enfileirar(
            tarefa, lambda codigo: self.j.log.linha(f"\n[preparação terminou com código {codigo}]"),
            self.j.log.linha_erro)
