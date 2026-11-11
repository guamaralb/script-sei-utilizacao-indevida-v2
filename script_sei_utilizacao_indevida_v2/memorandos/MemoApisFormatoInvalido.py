import re

from sei_automacao.modelos import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.DocArvore import DocArvore
from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# trocar para True
TEXTO_DEFINIDO = True

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = 'Adequação da solicitação ao modelo padronizado de levantamento'

# O script procura o memo por este padrão antes de criar (retomada)
PADRAO_ASSUNTO_MEMO_APIS_FORMATO_INVALIDO = re.compile(re.escape(ASSUNTO_MEMO_APIS_FORMATO_INVALIDO), flags=re.IGNORECASE)


class MemoApisFormatoInvalido(Memorando):
    """Memo à APIS-Utilização: o memorando da APIS destinado à GEACS não
    está no modelo esperado."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str, memo_apis: DocArvore):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (formato inválido)')
        super().__init__(
            # Duas linhas: <br>, pois o texto entra no HTML do memo (um \n vira espaço)
            destinatario_nome='Fernanda de Moura Galantini<br>Assessoria de Políticas e Informações em Saúde - APIS',
            assunto=ASSUNTO_MEMO_APIS_FORMATO_INVALIDO,
            vocativo='Prezada Assessora',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                'Retornamos o processo para <strong>reformulação integral da solicitação no modelo padronizado atualmente utilizado nos encaminhamentos à GEACS.</strong>',
                'O novo memorando deverá conter todos os dados necessários ao levantamento, incluindo a identificação do titular, as matrículas completas do titular e dos dependentes e os períodos de apuração aplicáveis a cada beneficiário, com datas de início e término. Quando houver períodos distintos entre os dependentes, deverão ser apresentados em campos individualizados por matrícula, observada a estrutura padronizada.',
                '<strong>A adequação deverá ser realizada mediante emissão de novo memorando de solicitação com a demanda completa e atualizada, em substituição à solicitação anterior</strong>. Para não comprometer a rotina de automatização, não será suficiente responder pontualmente a este memorando ou informar apenas os dados faltantes, exigindo consulta a outros documentos para recomposição da demanda.',
                'Após o ajuste, solicita-se o reencaminhamento do processo à unidade <strong>IPSEMG/GEACS-Utilização</strong> para realização do levantamento.',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
        self.memo_apis = memo_apis
