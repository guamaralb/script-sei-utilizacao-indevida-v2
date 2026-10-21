import pytest
import tags
from rede_propria import ErroAvaliacao
from Registro import RegistroMain


@pytest.fixture
def registro(monkeypatch):
    monkeypatch.setattr(tags, 'adicionar_marcador', lambda driver, tag: None)
    monkeypatch.setattr(tags, 'remover_marcador', lambda driver, tag: None)
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


def test_mais_de_um_estado_e_erro(registro):
    registro.marcadores_atuais.append(tags.TAG_MEMO_DISA_USO_REDE_PROPRIA)

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
