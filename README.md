# Tunel-LAD

App de mesa (Windows e Linux) para acessar o PC remoto do laboratório usando o
Tailscale, sem precisar mexer no terminal. Mostra os arquivos do seu computador e
do PC remoto lado a lado, envia e baixa pastas, roda scripts e guarda perfis de
conexão. Também prepara o PC remoto (instala o Tailscale em modo userspace, sem sudo).

## Pré-requisito

Instale o [Tailscale](https://tailscale.com/download) no seu computador e entre
com a sua conta antes de abrir o app.

## Download

Baixe o arquivo da versão mais recente na aba **Releases** do repositório:

- Windows: `Tunel-LAD.exe`
- Linux: `Tunel-LAD`

Não há instalador: dê dois cliques no arquivo e pronto.

### Windows

O antivírus ou o SmartScreen pode exibir um alerta, porque o executável não é
assinado. Confirme que o arquivo veio da aba Releases e permita a execução.

### Linux

```bash
chmod +x Tunel-LAD
./Tunel-LAD
```

As senhas lembradas são guardadas no cofre de senhas do sistema (Secret Service, por
exemplo GNOME Keyring ou KWallet). Se ele não estiver disponível, a senha
simplesmente não é guardada e será pedida a cada uso.

## Como conectar

1. Abra o app. No topo, clique em **Novo** para começar um perfil (ou escolha um
   existente na lista **Perfil**).
2. Preencha **Nome**, **Host / IP** (o IP ou nome do PC remoto no Tailscale), **Login**
   e, se quiser, **Senha** e **Pasta remota** (padrão `~`). Marque **Lembrar senha**
   para guardá-la no cofre do sistema.
3. Clique em **Salvar** para guardar o perfil. **Excluir perfil** remove o perfil
   selecionado (não apaga nada no PC remoto).
4. Clique em **Conectar**. Para encerrar, use **Desconectar**.

## Painéis de arquivos

A janela tem dois painéis: **Local** (seu computador) e **Remoto** (PC da universidade).

- Duplo clique em uma pasta entra nela; **Subir** volta um nível e **Atualizar** relê a lista.
- Selecione vários itens com Ctrl ou Shift.
- **Enviar ►** copia a seleção do painel Local para a pasta aberta no Remoto;
  **◄ Baixar** faz o caminho inverso; **Rodar ▶** executa o script selecionado
  no PC remoto, dentro da pasta em que ele está, e mostra a saída no log.
- Também é possível arrastar itens de um painel para o outro (soltar sobre uma
  pasta envia para dentro dela) e arrastar arquivos do Explorer/gerenciador de
  arquivos para o painel Remoto. Esta última função depende de um componente
  extra e pode estar indisponível em alguns ambientes; o app avisa no log
  ("ativado" ou "indisponível"). Nesse caso, use os painéis normalmente.

### Menu de contexto e atalhos (painel Remoto)

Clique com o botão direito em um item do painel Remoto para ver: **Baixar**,
**Rodar**, **Renomear (F2)**, **Mover para…**, **Nova pasta**, **Apagar (Delete)**
e **Atualizar**.

Atalhos: **F2** renomeia, **Delete** apaga, **F5** atualiza a lista.

### Atenção: apagar no PC remoto é permanente

Não existe lixeira no PC remoto. Tudo o que for apagado com **Apagar (Delete)**
**some para sempre** e não pode ser recuperado. O app pede confirmação, mas
confira a seleção com cuidado antes de confirmar.

Por segurança, o app recusa apagar:

- a raiz (`/`);
- a pasta pessoal (home) do usuário no PC remoto;
- a **Pasta remota** do perfil;
- qualquer pasta que contenha uma dessas (seus ancestrais).

## Menu Ferramentas

- **Instalar minha chave SSH**: instala sua chave pública no PC remoto, para
  não precisar digitar a senha.
- **Abrir terminal**: abre um terminal SSH no PC remoto.
- **Informações do PC remoto**: mostra dados básicos da máquina.
- **Estado do Tailscale**: mostra se o Tailscale do seu computador está ativo.
- **Entrar no Tailscale (auth key)**: entra na rede usando uma auth key.
- **Preparar PC remoto**: baixa o Tailscale para uma pasta escolhida no PC
  remoto, roda-o sem root (modo userspace) e adiciona uma linha `@reboot` no
  crontab para que volte a iniciar após reinicializações. O app mostra o script
  completo e pede confirmação antes de executar. A auth key não aparece na lista
  de processos do PC remoto: ela é gravada num arquivo temporário e apagada em seguida.

Crie uma auth key **de uso único** (não reutilizável) e com validade curta no
painel de administração do Tailscale, e use-a em **Preparar PC remoto** ou em
**Entrar no Tailscale (auth key)**.

## Rodar a partir do código

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python run.py
```

No Linux é preciso ter o `python3-tk` instalado (`sudo apt install python3-tk`)
apenas para rodar do código-fonte. Testes: `python -m pytest`.

## Aviso

Confirme com a TI da universidade que o acesso remoto por esse meio é permitido
pela política de uso da rede.
