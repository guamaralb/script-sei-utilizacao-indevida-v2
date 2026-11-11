"""Fluxo GEACS RESP DEPROC (task run_geacs_resp_deproc): resposta da DEPROC ao
memo DEPROC assinado e encaminhado (coparticipação). A DEPROC responde
com o MemoGeacsCalculoCopa (fluxo DEPROC, run_deproc_calcula_copa).

TODO: fluxo ainda não montado. Hoje, para cada processo da aba
geacs_resp_deproc de processos_a_processar.xlsx, só confere se ele tem um dos
marcadores "Aguarda" da DEPROC (TAGS_AGUARDA_RESPOSTA_DEPROC, em tags.py) e termina
com erro (FluxoNaoMontado), sem nenhuma ação no SEI. Ver fluxo_resposta.py.
"""

from fluxo_resposta import FluxoResposta, executar, fluxo_nao_montado
from Registro import RegistroResposta
from selenium import webdriver
from tags import TAGS_AGUARDA_RESPOSTA_DEPROC

FLUXO = FluxoResposta(
    script='geacs_resp_deproc',
    fluxo='RESP DEPROC - RESPOSTA DA DEPROC',
    unidade_resposta='DEPROC',
    tags_aguarda=TAGS_AGUARDA_RESPOSTA_DEPROC,
)


def tratar_resposta(driver: webdriver.Remote, registro: RegistroResposta, tag_aguarda: str) -> None:
    """Chamada depois de conferido o marcador "Aguarda" (tag_aguarda)."""
    # TODO: definir o que fazer com a resposta da DEPROC (01.10.1 Aguarda
    # DEPROC: Coparticipação): conferir o MemoGeacsCalculoCopa assinado na
    # rodada (assunto PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA) e o relatório de
    # coparticipação; retorno final à APIS (MemoApisComTodasAsInformacoes)?
    # Definir o que ler na árvore, que memo criar (bloco), que marcador
    # adicionar (e se o "Aguarda" sai) e a prox_acao (Registro.ProxAcao)
    raise fluxo_nao_montado(FLUXO)


def main():
    executar(FLUXO, tratar_resposta)


if __name__ == '__main__':
    main()
