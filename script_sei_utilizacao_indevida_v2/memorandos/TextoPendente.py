class TextoMemoPendente(Exception):
    """O texto do memo ainda tem placeholders (TODO). Impede que o memo seja
    criado no SEI com texto provisório; o processo é registrado com erro e
    pode ser reprocessado depois que o texto for definido."""


def verificar_texto_definido(texto_definido: bool, descricao: str) -> None:
    if not texto_definido:
        raise TextoMemoPendente(f'Texto do memo {descricao} ainda não definido (placeholders no código)')
