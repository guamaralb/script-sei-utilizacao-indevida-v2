"""Fluxo GEACS RESP DISA (task run_geacs_resp_disa): resposta da DISA ao
memo à DISA assinado e encaminhado: validar e complementar, validar
(não consta na base DISA) ou relatório sem MANTIS.

TODO: fluxo ainda não montado. Hoje, para cada processo da aba
geacs_resp_disa de processos_a_processar.xlsx, só confere se ele tem um dos
marcadores "Aguarda" da DISA (TAGS_AGUARDA_RESPOSTA_DISA, em tags.py) e termina
com erro (FluxoNaoMontado), sem nenhuma ação no SEI. Ver fluxo_resposta.py.
"""

from fluxo_resposta import FluxoResposta, executar, fluxo_nao_montado
from Registro import RegistroResposta
from selenium import webdriver
from tags import TAGS_AGUARDA_RESPOSTA_DISA

FLUXO = FluxoResposta(
    script='geacs_resp_disa',
    fluxo='RESP DISA - RESPOSTA DA DISA',
    unidade_resposta='DISA',
    tags_aguarda=TAGS_AGUARDA_RESPOSTA_DISA,
)


def tratar_resposta(driver: webdriver.Remote, registro: RegistroResposta, tag_aguarda: str) -> None:
    """Chamada depois de conferido o marcador "Aguarda" (tag_aguarda)."""
    # TODO: definir o que fazer com a resposta da DISA, por marcador:
    # - 01.09.1 Validar (Consta) / Validar (N Consta): a DISA validou os
    #   atendimentos do MANTIS (e complementou)?
    # - 01.09.1 Relat. s/ MANTIS: a DISA mandou o relatório da rede própria?
    # Depois: memo DEPROC com as duas redes (MemoDeproc,
    # ASSUNTO_MEMO_DEPROC_DUAS_REDES, com doc_relatorio_disa e
    # doc_manifestacao_disa)? Para cada caso: o que ler na árvore (rodada),
    # que memo ou documento criar (bloco), que marcador adicionar (e se o
    # "Aguarda" sai) e a prox_acao (Registro.ProxAcao)
    raise fluxo_nao_montado(FLUXO)


def main():
    executar(FLUXO, tratar_resposta)


if __name__ == '__main__':
    main()
