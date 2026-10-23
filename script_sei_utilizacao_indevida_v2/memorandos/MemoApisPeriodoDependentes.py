import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto (ainda sem modelo) e trocar para True
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = '[TODO: assunto do memo à APIS - período específico dos dependentes]'

# O script procura o memo por este padrão antes de criar (retomada)
PADRAO_ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES = re.compile(re.escape(ASSUNTO_MEMO_APIS_PERIODO_DEPENDENTES), flags=re.IGNORECASE)


def _par_dependentes(dependentes: tuple[str, ...]) -> str:
    return f'[TODO: texto do memo. Dependentes: {", ".join(dependentes) or "-"}]'


class MemoApisPeriodoDependentes(Memorando):
    """Memo à APIS-Utilização: pede que informe o período específico de
    apuração dos dependentes."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, dependentes: tuple[str, ...], memo_apis: DocArvore):
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
                _par_dependentes(dependentes),
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
