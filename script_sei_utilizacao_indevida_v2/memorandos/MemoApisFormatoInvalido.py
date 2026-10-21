import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto a partir do modelo Memorando 2019 (SEI 150646384) e
# trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = '[TODO: assunto do memo à APIS - formato do memorando inválido]'

# O script procura o memo por este padrão antes de criar (retomada)
PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = re.compile(re.escape(ASSUNTO_MEMO_APIS_FORMATO_INVALIDO), flags=re.IGNORECASE)


class MemoApisFormatoInvalido(Memorando):
    """Memo à APIS-Utilização: o memorando da APIS destinado à GEACS não
    está no modelo esperado."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, memo_apis_sei: str):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (formato inválido)')
        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_APIS_FORMATO_INVALIDO,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'[TODO: texto do modelo Memorando 2019 (SEI 150646384). Memorando da APIS: SEI {memo_apis_sei}]',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
