# tunel

App de mesa (Windows e Linux) para abrir túneis SSH até o PC remoto do laboratório
usando o Tailscale, sem precisar mexer no terminal. Também prepara o PC remoto
(instala o Tailscale em modo userspace, sem sudo) e guarda perfis de conexão.

## Pré-requisito

Instale o [Tailscale](https://tailscale.com/download) no seu computador e entre
com a sua conta antes de abrir o app.

## Download

Baixe o arquivo da versão mais recente na aba **Releases** do repositório:

- Windows: `tunel.exe`
- Linux: `tunel`

### Windows

O antivírus ou o SmartScreen pode exibir um alerta, porque o executável não é
assinado. Confirme que o arquivo veio da aba Releases e permita a execução.

### Linux

```bash
chmod +x tunel
./tunel
```

As senhas lembradas são guardadas no cofre do sistema (Secret Service, por
exemplo GNOME Keyring ou KWallet). Se ele não estiver disponível, a senha
simplesmente não é guardada e será pedida a cada uso.

## Como criar um perfil

1. Abra o app e clique em **Novo**.
2. Preencha **Nome**, **Host / IP** (o IP ou nome do PC remoto no Tailscale), **Login**
   e, se quiser, **Senha** e **Pasta remota** (padrão `~`). Marque "Lembrar senha" para guardá-la no cofre do sistema.
3. Clique em **Salvar** e depois em **Testar** para conferir a conexão.

## Preparar PC remoto

O botão **Preparar PC remoto** baixa o Tailscale para uma pasta escolhida no PC
remoto, roda-o sem root (modo userspace) e adiciona uma linha `@reboot` no
crontab para que volte a iniciar após reinicializações. O app mostra o script
completo e pede confirmação antes de executar. A auth key não aparece na lista
de processos do PC remoto: ela é gravada num arquivo temporário e apagada em seguida.

Crie uma auth key **de uso único** (não reutilizável) e com validade curta no
painel de administração do Tailscale, e use-a em **Preparar PC remoto** ou em
**Entrar no Tailscale (auth key)**.

## Pastas e scripts

**Enviar pasta** e **Baixar pasta** copiam diretórios inteiros (recursivamente) para
a Pasta remota do perfil e de volta. **Rodar script remoto** executa um `.R` ou `.py`
que já está no PC remoto; **Rodar script local** envia um script do seu computador
para a Pasta remota, executa-o e mostra a saída na janela.

## Rodar a partir do código

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python run.py
```

No Linux é preciso ter o `python3-tk` instalado (`sudo apt install python3-tk`).
Testes: `python -m pytest`.

## Aviso

Confirme com a TI da universidade que o acesso remoto por esse meio é permitido
pela política de uso da rede.
