"""Fluxos de resposta (main_geacs_resp_*): ainda não montados. Conferem o
marcador "Aguarda" do fluxo e terminam com erro, sem nenhuma ação no SEI."""

import fluxo_resposta
import main_geacs_resp_apis
import main_geacs_resp_deproc
import main_geacs_resp_disa
import pytest
import tags
from Registro import ProxAcao

FLUXOS = [
    pytest.param(main_geacs_resp_apis, tags.TAGS_AGUARDA_RESPOSTA_APIS, id='apis'),
    pytest.param(main_geacs_resp_disa, tags.TAGS_AGUARDA_RESPOSTA_DISA, id='disa'),
    pytest.param(main_geacs_resp_deproc, tags.TAGS_AGUARDA_RESPOSTA_DEPROC, id='deproc'),
]


def _passar(monkeypatch, modulo, marcadores):
    acoes = []
    monkeypatch.setattr(fluxo_resposta, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo_resposta, 'listar_marcadores', lambda driver: list(marcadores))
    monkeypatch.setattr(fluxo_resposta, 'restaurar_navegador', lambda driver: acoes.append('restaurar'))
    registro = fluxo_resposta.processar_linha(object(), 'PROC', modulo.FLUXO, modulo.tratar_resposta, 'AGORA')
    assert acoes == []
    return registro


def test_os_marcadores_aguarda_sao_todos_os_aguarda_manuais():
    por_fluxo = [*tags.TAGS_AGUARDA_RESPOSTA_APIS, *tags.TAGS_AGUARDA_RESPOSTA_DISA, *tags.TAGS_AGUARDA_RESPOSTA_DEPROC]
    assert sorted(por_fluxo) == sorted(tags.AGUARDA_POR_NO_BLOCO.values())
    assert all(' - Aguarda ' in tag for tag in por_fluxo)


@pytest.mark.parametrize(('modulo', 'tags_aguarda'), FLUXOS)
def test_com_o_marcador_aguarda_erro_de_fluxo_nao_montado(monkeypatch, modulo, tags_aguarda):
    for tag in tags_aguarda:
        registro = _passar(monkeypatch, modulo, [tags.TAG_PROCESSO_NOVO, tag])

        assert registro.tipo_erro == 'FluxoNaoMontado'
        assert 'ainda não montado' in registro.erro
        assert registro.marcador_aguarda == tag
        # Continua aguardando a resposta (a prox_acao não vira Verificar erro)
        assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
        assert registro.marcadores_adicionados == []
        assert registro.marcadores_removidos == []


@pytest.mark.parametrize(('modulo', 'tags_aguarda'), FLUXOS)
def test_sem_o_marcador_aguarda_do_fluxo_para_antes(monkeypatch, modulo, tags_aguarda):
    outros = [tag for tag in tags.AGUARDA_POR_NO_BLOCO.values() if tag not in tags_aguarda]
    for marcadores in ([tags.TAG_PROCESSO_NOVO], [tags.TAG_PROCESSO_NOVO, tags.TAG_NO_BLOCO_DISA_VALIDAR_CONSTA], [tags.TAG_PROCESSO_NOVO, outros[0]]):
        registro = _passar(monkeypatch, modulo, marcadores)

        assert registro.tipo_erro == 'SemMarcadorAguarda'
        assert registro.marcador_aguarda is None
        assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO


def test_planilha_de_controle_nao_apaga_resultados_do_fluxo_inicial(monkeypatch):
    registro = _passar(monkeypatch, main_geacs_resp_disa, [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA])
    colunas = registro.to_dict()

    assert colunas['fluxo'] == 'RESP DISA - RESPOSTA DA DISA'
    assert colunas['marcador_aguarda'] == tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA
    assert 'tit_usou' not in colunas
    assert 'processo_reaberto' not in colunas


def test_execucao_registra_na_planilha_e_no_resumo(monkeypatch, tmp_path):
    registrados = []

    class Controle:
        def __init__(self, script, agora):
            assert script == 'geacs_resp_deproc'

        @staticmethod
        def registrar(dados):
            registrados.append(dados)

    class Driver:
        @staticmethod
        def quit():
            registrados.append('quit')

    monkeypatch.setattr(fluxo_resposta, 'DIR_LOG', tmp_path)
    monkeypatch.setattr(fluxo_resposta, 'DIR_INPUTS', tmp_path)
    monkeypatch.setattr(fluxo_resposta, 'DIR_CONTROLE', tmp_path)
    monkeypatch.setattr(fluxo_resposta, 'configurar_logging', lambda arq: None)
    monkeypatch.setattr(fluxo_resposta, 'ler_processos_a_processar', lambda aba: ['PROC'])
    monkeypatch.setattr(fluxo_resposta, 'PlanilhaControleGeral', Controle)
    monkeypatch.setattr(fluxo_resposta, 'abrir_sei', lambda unidade: Driver())
    monkeypatch.setattr(fluxo_resposta, 'acessar_processo', lambda driver, num: None)
    monkeypatch.setattr(fluxo_resposta, 'listar_marcadores', lambda driver: [tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DEPROC_COPARTICIPACAO])

    main_geacs_resp_deproc.main()

    assert registrados[0]['tipo_erro'] == 'FluxoNaoMontado'
    assert registrados[-1] == 'quit'
