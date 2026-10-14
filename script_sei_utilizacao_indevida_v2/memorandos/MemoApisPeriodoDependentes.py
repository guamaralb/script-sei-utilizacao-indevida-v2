import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto (ainda sem modelo) e trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = '[TODO: assunto do memo à APIS - período específico dos dependentes]'

# TODO: buscar o memo pelo assunto antes de criar (retomada, como o memo de
# matrículas não encontradas)
PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = re.compile(re.escape(ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES), flags=re.IGNORECASE)


class MemoApisPeriodoDependentes(Memorando):
    """Memo à APIS-Utilização: pede que informe o período específico de
    apuração dos dependentes."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, dependentes: tuple[str, ...]):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (período dos dependentes)')
        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                f'[TODO: texto do memo. Dependentes: {", ".join(dependentes) or "-"}]',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
