"""Fluxo dos processos (main.py e processar_novo.py) em várias passagens,
com o SEI simulado."""

from Registro import ProxAcao
from relatorios_mantis import REDE_CREDENCIADA, inicio_nome_relatorio
from tags import TAG_MANUAL, TAG_MEMO_DEPROC_NO_BLOCO, TAG_MEMOS_DISA_DEPROC_NO_BLOCO, TAG_PROCESSO_NOVO

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeprocRedeCredenciada import ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import ASSUNTO_MEMO_DISA
from tests.sei_falso import (
    MANTIS_CREDENCIADA_TITULAR_USOU,
    MANTIS_DEPENDENTE_USOU,
    MANTIS_DUAS_REDES,
    MEMO_APIS_NOVO_VELHO,
    TITULAR,
    bases,
    curto,
)

NOVO = '1 - Processo NOVO'
DISA = '1.6 - Avaliado Uso Rede Própria DISA'
MANTIS = '1.8 - Avaliado Uso Rede Própria MANTIS'
MEMO_DISA = '1.9 - Memo DISA Uso Rede Própria'
CONCLUIDO_DISA_DEPROC = '1.10 - Memos DISA e DEPROC no Bloco'
CONCLUIDO_DEPROC = '1.10 - Memo DEPROC Coparticipação'
VELHO_DISA = '1.11 - VELHO Memo DISA no Bloco'
VELHO_DEPROC = '1.11 - VELHO Memo DEPROC no Bloco'

PDF_DEP_RP = f'PDF Utilização Dep. RP - {TITULAR}'
PDF_TIT_RC = f'PDF Utilização Tit. RC - {TITULAR}'


def _velho(sei):
    """Processo enviado à DISA e à DEPROC antes da avaliação."""
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMOS_DISA_DEPROC_NO_BLOCO]
    sei.memo_geacs('disa (versão anterior)')
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC)


# --- Fluxo normal -------------------------------------------------------------


def test_sem_uso_no_mantis_so_memo_deproc(sei):
    # A base DISA marca uso, mas sem atendimento no MANTIS não há memo à DISA
    sei.novo_processo()
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, CONCLUIDO_DEPROC]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DEPROC]
    assert sei.pdfs == []
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert [curto(t) for t in registro.marcadores_removidos] == [DISA, MANTIS]
    assert registro.memo_deproc_sei


def test_uso_no_mantis_relatorio_e_memo_disa(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)

    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DISA, ASSUNTO_MEMO_DEPROC]
    assert sei.pdfs == [PDF_DEP_RP]
    assert registro.prox_acao == ProxAcao.ASSINAR_DISA_DEPROC
    assert [curto(t) for t in registro.marcadores_removidos] == [DISA, MANTIS, MEMO_DISA]
    assert registro.mats_uso_mantis_alem_disa == ['555 (dependente)']
    assert registro.memo_disa_sei
    assert registro.memo_deproc_sei


def test_rede_credenciada_anexada_antes_do_memo_deproc(sei):
    sei.novo_processo()
    sei.passar(bases(), MANTIS_CREDENCIADA_TITULAR_USOU)

    assert sei.tags_curtas == [NOVO, CONCLUIDO_DEPROC]
    assert sei.pdfs == [PDF_TIT_RC]
    assert sei.nomes[-2].startswith(PDF_TIT_RC)
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DEPROC]


def test_concluido_e_conferido_na_passagem_seguinte(sei):
    sei.novo_processo()
    sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DISA_DEPROC
    assert registro.memos_criados == []
    assert sei.qnt_memos_geacs == 2


def test_titular_fora_da_base_disa_mantem_informativo(sei):
    sei.novo_processo()
    sei.passar(bases(tit_na_disa=False))

    assert sei.tags_curtas == [NOVO, '1.2.2 - Mat. N Encontradas Base DISA', CONCLUIDO_DEPROC]


def test_falha_ao_criar_deproc_retoma_pelo_estado(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 2
    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    assert sei.tags_curtas == [NOVO, MEMO_DISA]
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO

    sei.falhar_memo_n = None
    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]
    assert sei.qnt_memos_geacs == 2
    assert sei.pdfs == [PDF_DEP_RP]
    assert registro.memos_criados == ['memo_deproc']


def test_falha_depois_do_relatorio_nao_duplica_o_pdf(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 1
    sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    assert sei.tags_curtas == [NOVO, MANTIS]
    assert sei.pdfs == [PDF_DEP_RP]

    sei.falhar_memo_n = None
    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    assert registro.erro is None
    assert sei.pdfs == [PDF_DEP_RP]
    assert registro.relatorios_na_arvore
    assert registro.relatorios_incluidos == []


def test_base_geral_para_com_memo_a_apis(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_na_geral=False))
    assert sei.tags_curtas == [NOVO, '1.2.1 - Mat. N Encontradas Base Geral', '1.6.1 - Memo APIS Mat. N Encontradas']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS

    registro = sei.passar(bases(tit_na_geral=False))
    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
    assert sei.qnt_memos_geacs == 1


def test_sem_memo_da_apis(sei):
    sei.novo_processo(com_memo_apis=False)
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Memo APIS Sem Memo p/ GEACS']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO


def test_modelo_novo_velho_e_formato_invalido(sei):
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_NOVO_VELHO)
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Memo APIS Formato Inválido']
    assert 'novo_velho' in registro.motivo_formato_invalido


def test_usa_o_ultimo_memo_da_apis(sei):
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_NOVO_VELHO)
    ultimo = sei.memo_apis()
    registro = sei.passar(bases())

    assert registro.memo_apis_sei == ultimo
    assert registro.modelo_memo_apis == 'novo_novo'
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DEPROC]


def test_periodo_variavel_para_dependentes(sei):
    sei.novo_processo(extra='Dependente 555: 01/02/2024 a 01/03/2024')
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.1 - Período Variável p/ Dependentes', '1.7 - Memo APIS Período Dependentes']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_PERIODO_DEPS


def test_falha_na_remocao_deixa_dois_estados_e_gera_erro(sei):
    sei.novo_processo()
    sei.falhar_remocao = True
    sei.passar(bases())
    assert sei.tags_curtas == [NOVO, DISA, MANTIS]

    sei.falhar_remocao = False
    registro = sei.passar(bases())
    assert 'mais de um marcador de estado' in registro.erro


def test_processo_com_documentos_antigos_da_geacs_e_tratado_como_novo(sei):
    # Antigo VELHO: memo DEPROC de um pedido anterior da APIS, antes do
    # último memo da APIS. Não é reaproveitado (é de outra rodada)
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC)
    sei.tags = ['Script v2 - 2 - Processo VELHO']
    sei.memo_apis()

    registro = sei.passar(bases())
    assert registro.erro is None
    assert registro.memo_deproc_criado
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DEPROC, ASSUNTO_MEMO_DEPROC]
    assert sei.tags_curtas[-2:] == [NOVO, CONCLUIDO_DEPROC]


# --- Retomada pelo assunto (memo criado sem marcador) -------------------------


def test_memo_deproc_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MEMO_DISA]
    sei.memo_geacs(ASSUNTO_MEMO_DISA)
    numero_deproc = sei.memo_geacs(ASSUNTO_MEMO_DEPROC)

    registro = sei.passar(bases())
    assert registro.erro is None
    assert sei.qnt_memos_geacs == 2
    assert registro.memo_deproc_na_arvore
    assert registro.memo_deproc_sei == numero_deproc
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]


def test_memo_disa_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MANTIS]
    sei.memo_geacs(ASSUNTO_MEMO_DISA)

    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)
    assert registro.erro is None
    assert registro.memo_disa_na_arvore
    assert registro.memos_criados == ['memo_deproc']
    assert sei.qnt_memos_geacs == 2
    assert sei.tags_curtas == [NOVO, CONCLUIDO_DISA_DEPROC]


def test_memo_a_apis_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + DISA, 'Script v2 - 1.2.1 - Mat. N Encontradas Base Geral']
    sei.memo_geacs(ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS)

    registro = sei.passar(bases(tit_na_geral=False))
    assert registro.erro is None
    assert registro.memo_apis_mat_nao_encontradas_na_arvore
    assert sei.qnt_memos_geacs == 1
    assert sei.tags_curtas[-1] == '1.6.1 - Memo APIS Mat. N Encontradas'


# --- VELHO (enviado à DISA e à DEPROC antes da avaliação) ---------------------


def test_velho_na_base_disa_aguarda_retorno(sei):
    _velho(sei)
    registro = sei.passar(bases(tit_usou=True), MANTIS_DUAS_REDES)

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.VELHO_AGUARDAR_DISA
    assert registro.memos_criados == []
    assert sei.pdfs == []


def test_velho_com_uso_no_mantis_vai_so_para_a_disa(sei):
    _velho(sei)
    registro = sei.passar(bases(tit_usou=False), MANTIS_DUAS_REDES)

    assert registro.prox_acao == ProxAcao.VELHO_ASSINAR_DISA
    assert sei.tags_curtas[-1] == VELHO_DISA
    assert MEMO_DISA not in sei.tags_curtas
    assert sei.pdfs == [PDF_DEP_RP, PDF_TIT_RC]
    assert registro.memos_criados == ['memo_disa']

    registro = sei.passar(bases(tit_usou=False), MANTIS_DUAS_REDES)
    assert registro.prox_acao == ProxAcao.VELHO_ASSINAR_DISA
    assert registro.memos_criados == []


def test_velho_sem_uso_envia_rede_credenciada_a_deproc(sei):
    _velho(sei)
    registro = sei.passar(bases(tit_usou=False), MANTIS_CREDENCIADA_TITULAR_USOU)

    assert registro.prox_acao == ProxAcao.VELHO_ASSINAR_DEPROC
    assert sei.tags_curtas[-1] == VELHO_DEPROC
    assert sei.pdfs == [PDF_TIT_RC]
    assert sei.assuntos_memos_geacs[-1] == ASSUNTO_MEMO_DEPROC_REDE_CREDENCIADA
    assert registro.memo_deproc_credenciada_criado


def test_velho_tratado_manualmente_fica_fora_do_escopo(sei):
    _velho(sei)
    sei.tags.append(TAG_MANUAL)
    registro = sei.passar(bases(tit_usou=False))

    assert registro.prox_acao == ProxAcao.FORA_DO_ESCOPO
    assert registro.memos_criados == []


def test_versao_anterior_so_deproc_e_concluido(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_NO_BLOCO]
    registro = sei.passar(bases())

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC


def test_nome_do_relatorio_cabe_no_sei():
    assert len(f'{inicio_nome_relatorio(REDE_CREDENCIADA, "Dep.", "123456789")} - 20261022_103324') <= 50
