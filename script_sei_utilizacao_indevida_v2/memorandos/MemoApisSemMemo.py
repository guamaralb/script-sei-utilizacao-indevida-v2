import re

from sei_automacao.classes.Memorando import Memorando

from script_sei_utilizacao_indevida_v2.memorandos.TextoPendente import verificar_texto_definido

# TODO: definir o texto a partir do modelo Despacho 2 (SEI 150644870) e
# trocar para True. O modelo é um Despacho: avaliar criar o documento com
# incluir_doc_sei_simples(tipo_doc='Despacho') em vez de Memorando.
TEXTO_DEFINIDO = False

# Não altere o assunto depois de criar memos: é por ele que o script os
# encontra na árvore
ASSUNTO_MEMO_APIS_SEM_MEMO = '[TODO: assunto do memo à APIS - sem memorando para a GEACS]'

# TODO: buscar o memo pelo assunto antes de criar (retomada, como o memo de
# matrículas não encontradas)
PADRAO_ASSUNTO_MEMO_APIS_SEM_MEMO = re.compile(re.escape(ASSUNTO_MEMO_APIS_SEM_MEMO), flags=re.IGNORECASE)


class MemoApisSemMemo(Memorando):
    """Memo à APIS-Utilização: não há memorando da APIS destinado à GEACS no
    processo."""

    def __init__(self, *, nome_signatario: str, cargo_signatario: str):
        verificar_texto_definido(TEXTO_DEFINIDO, 'à APIS (sem memorando)')
        super().__init__(
            destinatario_nome='IPSEMG/APIS-Utilização',
            assunto=ASSUNTO_MEMO_APIS_SEM_MEMO,
            vocativo='Prezados',
            nome_signatario=nome_signatario,
            cargo_signatario=cargo_signatario,
            nivel_acesso='Restrito',
            hipotese_legal='Informação Pessoal (Art. 31 da Lei nº 12.527/2011)',
            paragrafos=[
                '[TODO: texto do modelo Despacho 2 (SEI 150644870)]',
                '',
                '',
                '',
                'Atenciosamente,',
            ],
        )
