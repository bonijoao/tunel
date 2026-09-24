def decidir_arrasto(lado_origem, lado_alvo, pasta_alvo, pasta_origem, entrada_alvo, itens):
    """Traduz um arrastar-e-soltar em (ação, pasta de destino), ou None se não deve acontecer nada."""
    destino = entrada_alvo.caminho if entrada_alvo is not None and entrada_alvo.eh_pasta else pasta_alvo
    if lado_origem == "local" and lado_alvo == "remoto":
        return ("enviar", destino)
    if lado_origem == "remoto" and lado_alvo == "local":
        return ("baixar", destino)
    if lado_origem == "remoto" and lado_alvo == "remoto":
        caminhos = {i.caminho for i in itens}
        if destino in caminhos or destino == pasta_origem:
            return None
        return ("mover", destino)
    return None
