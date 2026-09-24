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

1. Abra o app e clique para criar um novo perfil.
2. Preencha o nome do PC remoto, o usuário e, se quiser, marque para lembrar a senha.
3. Salve e use o perfil para conectar.

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
