"""Unidade sem acesso ao processo (UnidadeSemAcessoException em
acessar_processo): em todos os fluxos, erro na planilha de controle, sem
nenhuma ação no SEI."""

import main_deproc
import main_geacs
import main_geacs_adc_pdf_ant_aut
import main_geacs_canc_memo_deproc_ant
import pytest
from Registro import ProxAcao
from sei_automacao.exceptions import UnidadeSemAcessoException

FLUXOS = [
    pytest.param(main_geacs, (None, None), 'registrar_tags', id='geacs'),
    pytest.param(main_deproc, (None,), 'processar_deproc', id='deproc'),
    pytest.param(main_geacs_adc_pdf_ant_aut, (), 'registrar_tags', id='adc_pdf_ant'),
    pytest.param(main_geacs_canc_memo_deproc_ant, (), 'cancelar_memo_deproc_antigo', id='canc_memo_deproc_ant'),
]


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
