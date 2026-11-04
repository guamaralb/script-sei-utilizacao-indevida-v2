import re

import pytest
import tags
from rede_propria import ErroAvaliacao
from Registro import RegistroMain


@pytest.fixture
def registro(monkeypatch):
    monkeypatch.setattr(tags, 'adicionar_marcador', lambda driver, tag: None)
    monkeypatch.setattr(tags, 'remover_marcador', lambda driver, marcadores: None)
    reg = RegistroMain(num_processo='PROC')
    tags.registrar_tags(reg, [f' {tags.TAG_PROCESSO_NOVO} ', tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA])
    return reg


def test_registrar_tags_normaliza(registro):
    assert registro.marcadores_sei == [tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA]
    assert registro.marcadores_atuais == registro.marcadores_sei


def test_novo_estado_remove_o_anterior(registro):
    tags.adicionar_tag(None, registro, tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)

    assert registro.marcadores_atuais == [tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS]
    assert registro.marcadores_removidos == [tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA]
    assert tags.estado_atual(registro, tags.TAGS_ESTADO_NOVO) == tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS


def test_marcador_informativo_se_acumula(registro):
    tags.adicionar_tag(None, registro, tags.TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO)

    assert registro.marcadores_removidos == []
    assert tags.tem_tag(registro, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA)


def test_adicionar_se_ausente_nao_repete(registro):
    tags.adicionar_tag_se_ausente(None, registro, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA)

    assert registro.marcadores_adicionados == []


def test_par_base_disa_troca_o_anterior(registro):
    tags.adicionar_tag(None, registro, tags.TAG_DISA_USOU_RP)
    tags.adicionar_tag(None, registro, tags.TAG_DISA_NAO_USOU_RP)

    assert registro.marcadores_removidos == [tags.TAG_DISA_USOU_RP]
    assert tags.tem_tag(registro, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA)


def test_mais_de_um_estado_e_erro(registro):
    registro.marcadores_atuais.append(tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)

    with pytest.raises(ErroAvaliacao, match='mais de um marcador de estado'):
        tags.estado_atual(registro, tags.TAGS_ESTADO_NOVO)


def test_colunas_tags_refletem_marcadores_finais(registro):
    tags.adicionar_tag(None, registro, tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS)
    dados = registro.to_dict()

    assert dados['tag_processo_novo'] is True
    assert dados['tag_avaliado_uso_rede_propria_disa'] is False
    assert dados['tag_avaliado_uso_rede_propria_mantis'] is True
    assert 'tds_docs' not in dados


@pytest.mark.parametrize('tag', sorted(tags.TAGS_SCRIPT))
def test_nome_do_marcador_cabe_no_sei(tag):
    assert len(tag) <= 50


def _registro_com(*marcadores) -> RegistroMain:
    reg = RegistroMain(num_processo='PROC')
    tags.registrar_tags(reg, list(marcadores))
    return reg


@pytest.mark.parametrize(
    'marcadores',
    [
        (),
        (tags.TAG_PROCESSO_VELHO,),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO, tags.TAG_MEMOS_DISA_DEPROC_COPARTICIPACAO),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_MAT_NAO_ENCONTRADAS_APIS, tags.TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_PERIODO_VAR_DEP, tags.TAG_DISA_USOU_RP, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_MEMOS_DISA_DEPROC_NO_BLOCO, tags.TAG_VELHO_MEMO_DEPROC, tags.TAG_PROCESSO_VELHO),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_USOU_RP, tags.TAG_MANTIS_USOU_RP, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_NAO_USOU_RP, tags.TAG_MANTIS_USOU_RP, tags.TAG_AGUARDA_DISA_VALIDAR_NAO_CONSTA),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_USOU_RP, tags.TAG_MANTIS_NAO_USOU_RP, tags.TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_NAO_USOU_RP, tags.TAG_MANTIS_NAO_USOU_RP, tags.TAG_MANTIS_USOU_RC, tags.TAG_MEMO_DEPROC_COPARTICIPACAO),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_NAO_USOU_RP, tags.TAG_MANTIS_NAO_USOU_RP, tags.TAG_MANTIS_NAO_USOU_RC, tags.TAG_AGUARDA_APIS_SEM_USO),
        (tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_USOU_RP, tags.TAG_MANTIS_USOU_RP, tags.TAG_MANTIS_USOU_RC, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA),
        # Sem estado: versão anterior ou falha antes do memo à APIS
        (tags.TAG_PROCESSO_NOVO, tags.TAG_MAT_NAO_ENCONTRADAS_APIS),
        (tags.TAG_MEMOS_DISA_DEPROC_NO_BLOCO,),
    ],
)
def test_marcadores_consistentes(marcadores):
    tags.conferir_marcadores(_registro_com(*marcadores))


@pytest.mark.parametrize(
    ('marcadores', 'trecho'),
    [
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA, tags.TAG_AVALIADO_USO_REDE_PROPRIA_MANTIS), 'mais de um marcador de estado'),
        ((tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA,), 'sem o marcador'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MEMOS_DISA_DEPROC_NO_BLOCO, tags.TAG_MEMO_DEPROC_NO_BLOCO), 'os dois marcadores 1.3'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_DEPROC_NO_BLOCO, tags.TAG_AVALIADO_USO_REDE_PROPRIA_DISA), 'concluído na versão anterior'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MAT_NAO_ENCONTRADAS_APIS, tags.TAG_MEMO_DEPROC_COPARTICIPACAO), '1.2.1 - Mat. N Encontradas Base APIS com o estado 1.10'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_USOU_RP, tags.TAG_DISA_NAO_USOU_RP), 'são alternativos'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MANTIS_USOU_RC, tags.TAG_MANTIS_NAO_USOU_RC), 'são alternativos'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MANTIS_NAO_USOU_RC, tags.TAG_MEMO_DEPROC_COPARTICIPACAO), '1.8.3 - MANTIS: Não Usou RC com o estado 1.10 - Concluído: Memo DEPROC'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MANTIS_USOU_RC, tags.TAG_AGUARDA_APIS_SEM_USO), '1.8.3 - MANTIS: Usou RC com o estado 1.10 - Aguarda APIS: Sem Uso'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_APIS_SEM_USO), '1.10 - Aguarda APIS: Sem Uso sem 1.6.2 - Base DISA: Não Usou RP e'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_DISA_USOU_RP, tags.TAG_MEMO_DEPROC_COPARTICIPACAO), '1.6.2 - Base DISA: Usou RP com o estado 1.10'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MANTIS_USOU_RP, tags.TAG_AGUARDA_DISA_SEM_MANTIS_RELATORIO), 'MANTIS: Usou RP com o estado 1.9 - Aguarda DISA: Relat. s/ MANTIS'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA), 'sem 1.6.2 - Base DISA: Usou RP e 1.8.2 - MANTIS: Usou RP'),
        ((tags.TAG_PROCESSO_VELHO, tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_DEPROC_COPARTICIPACAO), 'em processo VELHO'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_PERIODO_VAR_DEP, tags.TAG_MEMO_DEPROC_COPARTICIPACAO), '1.1 - Período Variável p/ Dependentes com o estado'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MAT_NAO_ENCONTRADAS_DISA_NOVO, tags.TAG_MEMO_APIS_SEM_MEMO), '1.2.2 - Mat. N Encontradas Base DISA com o estado'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_APIS_MAT_NAO_ENCONTRADAS), '1.6.1 - Aguarda APIS: Matrículas sem 1.2.1'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MEMO_APIS_PERIODO_DEPENDENTES), 'sem 1.1'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_VELHO_MEMO_DISA), 'sem 1.3'),
        ((tags.TAG_PROCESSO_NOVO, tags.TAG_MEMOS_DISA_DEPROC_NO_BLOCO, tags.TAG_AGUARDA_DISA_VALIDAR_CONSTA), 'em processo VELHO'),
    ],
)
def test_marcadores_inconsistentes(marcadores, trecho):
    with pytest.raises(tags.MarcadoresInconsistentes, match=re.escape(trecho)):
        tags.conferir_marcadores(_registro_com(*marcadores))
