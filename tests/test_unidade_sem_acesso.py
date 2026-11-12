"""Unidade sem acesso ao processo (UnidadeSemAcessoException em
acessar_processo): em todos os fluxos, erro na planilha de controle, sem
nenhuma ação no SEI."""

import fluxo_resposta
import main_deproc_calcula_copa
import main_deproc_excluir_docs
import main_geacs_adc_pdf_ant_aut
import main_geacs_canc_memo_deproc_ant
import main_geacs_inicial
import main_geacs_resp_disa
import main_geacs_verificar_marcadores
import pytest
from Registro import ProxAcao
from sei_automacao.exceptions import UnidadeSemAcessoException

FLUXOS = [
    pytest.param(main_geacs_inicial, (None, None), 'registrar_tags', id='geacs_inicial'),
    pytest.param(main_deproc_calcula_copa, (None, '06/11/2026'), 'processar_deproc', id='deproc_calcula_copa'),
    pytest.param(main_geacs_adc_pdf_ant_aut, (), 'registrar_tags', id='adc_pdf_ant'),
    pytest.param(main_geacs_canc_memo_deproc_ant, (), 'cancelar_memos_deproc_antigos', id='canc_memo_deproc_ant'),
    pytest.param(main_deproc_excluir_docs, (), 'excluir_docs_deproc', id='deproc_excluir_docs'),
    pytest.param(main_geacs_verificar_marcadores, (), 'verificar_marcadores', id='geacs_verificar_marcadores'),
]


def test_unidade_sem_acesso_nos_fluxos_de_resposta(monkeypatch):
    def sem_acesso(driver, num):
        raise UnidadeSemAcessoException(num)

    def nao_chamar(*_args, **_kwargs):
        raise AssertionError('o fluxo seguiu depois do processo sem acesso')

    monkeypatch.setattr(fluxo_resposta, 'acessar_processo', sem_acesso)
    monkeypatch.setattr(fluxo_resposta, 'listar_marcadores', nao_chamar)
    monkeypatch.setattr(fluxo_resposta, 'restaurar_navegador', nao_chamar)

    registro = fluxo_resposta.processar_linha(object(), 'PROC', main_geacs_resp_disa.FLUXO, nao_chamar, 'AGORA')

    assert registro.tipo_erro == 'UnidadeSemAcessoException'
    assert registro.prox_acao == ProxAcao.VERIFICAR_ACESSO_UNIDADE


@pytest.mark.parametrize(('modulo', 'args', 'proxima_etapa'), FLUXOS)
def test_unidade_sem_acesso_registra_erro_sem_seguir(modulo, args, proxima_etapa, monkeypatch):
    def sem_acesso(driver, num):
        raise UnidadeSemAcessoException(num)

    def nao_chamar(*_args, **_kwargs):
        raise AssertionError('o fluxo seguiu depois do processo sem acesso')

    monkeypatch.setattr(modulo, 'acessar_processo', sem_acesso)
    monkeypatch.setattr(modulo, proxima_etapa, nao_chamar)
    monkeypatch.setattr(modulo, 'restaurar_navegador', nao_chamar, raising=False)

    registro = modulo._processar_linha(object(), 'PROC', *args)

    assert registro.tipo_erro == 'UnidadeSemAcessoException'
    assert registro.erro == 'Unidade atual não possui acesso ao processo PROC'
    assert registro.prox_acao == ProxAcao.VERIFICAR_ACESSO_UNIDADE
