import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto (ainda sem modelo) e trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_DISA_VALIDAR_USOS_MANTIS = '[TODO: assunto do memo à DISA - validar usos da rede própria do MANTIS]'

# TODO: buscar o memo pelo assunto antes de criar (retomada, como o memo de
# matrículas não encontradas)
PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_USOS_MANTIS = re.compile(re.escape(ASSUNTO_MEMO_DISA_VALIDAR_USOS_MANTIS), flags=re.IGNORECASE)


class MemoDisaValidarUsosMantis(Memorando):
    """Memo à DISA: o MANTIS mostra uso da rede própria por beneficiário que
    a base DISA marca como não uso. Pede a validação desses usos."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, matriculas: list[str]):
        if not matriculas:
            raise ValueError('Memo à DISA de validação dos usos do MANTIS criado sem matrículas')
        verificar_texto_definido(TEXTO_DEFINIDO, 'à DISA (validar usos do MANTIS)')
        super().__init__(
            destinatario_nome='IPSEMG/DISA-UTI-INDEV',
            assunto=ASSUNTO_MEMO_DISA_VALIDAR_USOS_MANTIS,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'[TODO: texto do memo. Uso no MANTIS sem uso na base DISA: {", ".join(matriculas)}]',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
