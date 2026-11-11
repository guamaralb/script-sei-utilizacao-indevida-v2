"""Fluxo GEACS RESP APIS (task run_geacs_resp_apis): resposta da APIS ao
memo à APIS assinado e encaminhado: sem memorando para a GEACS,
formato inválido, matrículas não encontradas, período dos dependentes ou
nenhum uso nas bases.

TODO: fluxo ainda não montado. Hoje, para cada processo da aba
geacs_resp_apis de processos_a_processar.xlsx, só confere se ele tem um dos
marcadores "Aguarda" da APIS (TAGS_AGUARDA_RESPOSTA_APIS, em tags.py) e termina
com erro (FluxoNaoMontado), sem nenhuma ação no SEI. Ver fluxo_resposta.py.
"""

from fluxo_resposta import FluxoResposta, executar, fluxo_nao_montado
from Registro import RegistroResposta
from selenium import webdriver
from tags import TAGS_AGUARDA_RESPOSTA_APIS

FLUXO = FluxoResposta(
    script='geacs_resp_apis',
    fluxo='RESP APIS - RESPOSTA DA APIS',
    unidade_resposta='APIS',
    tags_aguarda=TAGS_AGUARDA_RESPOSTA_APIS,
)


def tratar_resposta(driver: webdriver.Remote, registro: RegistroResposta, tag_aguarda: str) -> None:
    """Chamada depois de conferido o marcador "Aguarda" (tag_aguarda)."""
    # TODO: definir o que fazer com a resposta da APIS, por marcador:
    # - 01.05.1 Sem Memo p/ GEACS / Formato Inválido: a APIS mandou um memo
    #   novo? Seguir o fluxo inicial (processar_novo) a partir dele?
    # - 01.06.1.1 Matrículas: matrículas corrigidas ou base APIS atualizada?
    # - 01.07.1 Período Deps: memo corrigido no modelo com período por
    #   dependente?
    # - 01.10.1 Sem Uso: o que a APIS responde e como o processo termina?
    # Para cada caso: o que ler na árvore (rodada), que memo ou documento
    # criar (bloco), que marcador adicionar (e se o "Aguarda" sai) e a
    # prox_acao (Registro.ProxAcao)
    raise fluxo_nao_montado(FLUXO)


def main():
    executar(FLUXO, tratar_resposta)


if __name__ == '__main__':
    main()
