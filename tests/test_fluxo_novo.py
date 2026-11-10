"""Fluxo dos processos (main.py e processar_novo.py) em várias passagens,
com o SEI simulado."""

from dataclasses import replace

import main
import pandas as pd
import processar_novo
from Registro import ProxAcao, RegistroMain, registrar_erro
from relatorios_mantis import REDE_CREDENCIADA, inicio_nome_relatorio
from selenium.common.exceptions import InvalidSessionIdException
from tags import (
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_MANUAL,
    TAG_MAT_NAO_ENCONTRADAS_APIS,
    TAG_MEMO_DEPROC_COPARTICIPACAO,
    TAG_MEMO_DEPROC_NO_BLOCO,
    TAG_MEMO_DISA_USO_REDE_PROPRIA,
    TAG_MEMOS_DISA_DEPROC_NO_BLOCO,
    TAG_PROCESSO_NOVO,
)

from script_sei_utilizacao_indevida_v2.memorandos.MemoApisMatNaoEncontradas import ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisSemUso import ASSUNTO_MEMO_APIS_SEM_USO
from script_sei_utilizacao_indevida_v2.memorandos.MemoDeproc import ASSUNTO_MEMO_DEPROC
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
    ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
)
from tests.sei_falso import (
    MANTIS_CREDENCIADA_TITULAR_USOU,
    MANTIS_DEPENDENTE_USOU,
    MANTIS_DUAS_REDES,
    MEMO_APIS_NOVO_VELHO,
    MEMO_APIS_PERIODO_POR_DEPENDENTE,
    TITULAR,
    bases,
    curto,
)

VELHO = '0 - Processo VELHO'
NOVO = '1 - Tratado pelo Script'
DISA = '1.6 - Avaliado Uso Rede Própria DISA'
MANTIS = '1.8 - Avaliado Uso Rede Própria MANTIS'
DISA_SIM = '1.6.2 - Base DISA: Usou RP'
DISA_NAO = '1.6.2 - Base DISA: Não Usou RP'
MANTIS_SIM = '1.8.2 - MANTIS: Usou RP'
MANTIS_NAO = '1.8.2 - MANTIS: Não Usou RP'
RC_SIM = '1.8.3 - MANTIS: Usou RC'
RC_NAO = '1.8.3 - MANTIS: Não Usou RC'
AGUARDA_CONSTA = '1.9 - Aguarda DISA: Validar (Consta)'
AGUARDA_N_CONSTA = '1.9 - Aguarda DISA: Validar (N Consta)'
AGUARDA_RELATORIO = '1.9 - Aguarda DISA: Relat. s/ MANTIS'
CONCLUIDO_DEPROC = '1.10 - Concluído: Memo DEPROC'
AGUARDA_SEM_USO = '1.10 - Aguarda APIS: Sem Uso'

PDF_DEP_RP = f'PDF Utilização Dep. RP - {TITULAR}'
PDF_TIT_RC = f'PDF Utilização Tit. RC - {TITULAR}'

DISA_UTI_INDEV = 'IPSEMG/DISA-UTI-INDEV'
DEPROC = 'IPSEMG/DEPROC'

# Só a rede credenciada: com base DISA não, vai para a DEPROC
SO_RC = MANTIS_CREDENCIADA_TITULAR_USOU


# --- Base DISA x MANTIS -------------------------------------------------------


def test_disa_nao_rp_nao_rc_sim_memo_deproc(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False), SO_RC)

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DEPROC]
    assert sei.pdfs == [PDF_TIT_RC]
    assert sei.nomes[-2].startswith(PDF_TIT_RC)
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert registro.caso_disa_mantis == 'DISA não, MANTIS RP não, MANTIS RC sim'
    assert [curto(t) for t in registro.marcadores_removidos] == [DISA, MANTIS]
    assert registro.memo_deproc_sei


def test_memo_deproc_cita_o_relatorio_rc(sei):
    sei.novo_processo()
    sei.passar(bases(tit_usou=False), SO_RC)

    pdf = next(doc for doc in sei.docs if doc['nome_arvore'].startswith(PDF_TIT_RC))
    assert f'constantes do documento {pdf["numero_sei"]}' in sei.textos[sei.docs[-1]['numero_sei']]


def test_nenhum_uso_memo_a_apis_sem_deproc(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False))

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_NAO, AGUARDA_SEM_USO]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_APIS_SEM_USO]
    assert sei.pdfs == []
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_SEM_USO
    assert registro.memo_apis_sem_uso_sei
    assert not registro.memo_deproc_criado

    registro = sei.passar(bases(tit_usou=False))
    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO


def test_disa_nao_mantis_sim_valida_com_rc_e_sem_deproc(sei):
    # Também usou a rede credenciada: o relatório RC entra, mas quem vai
    # para a DISA não vai para a DEPROC
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False), MANTIS_DUAS_REDES)

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_SIM, RC_SIM, AGUARDA_N_CONSTA]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA]
    assert sei.pdfs == [PDF_DEP_RP, PDF_TIT_RC]
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_NAO_CONSTA
    assert registro.mats_uso_mantis_alem_disa == ['555 (dependente)']
    assert registro.memo_disa_sei
    assert not registro.memo_deproc_criado
    # O memo cita o memo da APIS e o relatório RP pelo número SEI
    texto = sei.texto_ultimo_memo_geacs
    assert f'Memorando IPSEMG/APIS-UTILIZAÇÃO nº 7 ({sei.numero_sei("Memorando 7")})' in texto
    assert f'no documento {sei.numero_sei(PDF_DEP_RP)}' in texto
    assert sei.numero_sei(PDF_TIT_RC) not in texto


def test_disa_sim_mantis_sim_valida_e_complementa(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=True), MANTIS_DEPENDENTE_USOU)

    assert sei.tags_curtas == [NOVO, DISA_SIM, MANTIS_SIM, RC_NAO, AGUARDA_CONSTA]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DISA_VALIDAR_CONSTA]
    assert sei.pdfs == [PDF_DEP_RP]
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_CONSTA


def test_disa_sim_mantis_nao_solicita_relatorio_com_rc(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=True), SO_RC)

    assert sei.tags_curtas == [NOVO, DISA_SIM, MANTIS_NAO, RC_SIM, AGUARDA_RELATORIO]
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO]
    assert sei.pdfs == [PDF_TIT_RC]
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_DISA_SEM_MANTIS_RELATORIO


def test_memo_a_disa_para_o_processo(sei):
    sei.novo_processo()
    sei.passar(bases(tit_usou=True))
    registro = sei.passar(bases(tit_usou=True))

    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
    assert registro.memos_criados == []
    assert sei.qnt_memos_geacs == 1


def test_bloco_nao_configurado_para_antes_dos_documentos(sei, monkeypatch):
    monkeypatch.setattr(processar_novo, '_DISA_VALIDAR_NAO_CONSTA', replace(processar_novo._DISA_VALIDAR_NAO_CONSTA, bloco=None))
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)

    assert 'Bloco do memo à DISA' in registro.erro
    assert sei.tags_curtas == [NOVO, DISA_NAO, DISA]
    assert sei.pdfs == []
    assert sei.qnt_memos_geacs == 0


def test_concluido_e_conferido_na_passagem_seguinte(sei):
    sei.novo_processo()
    sei.passar(bases(tit_usou=False), SO_RC)
    registro = sei.passar(bases(tit_usou=False), SO_RC)

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert registro.memos_criados == []
    assert sei.qnt_memos_geacs == 1


def test_titular_fora_da_base_disa_conta_como_nao_uso(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_na_disa=False), SO_RC)

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]
    assert registro.erro is None


def test_base_disa_mudou_troca_o_par(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 1
    sei.passar(bases(tit_usou=False), SO_RC)
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, MANTIS]

    sei.falhar_memo_n = None
    registro = sei.passar(bases(tit_usou=True), SO_RC)
    assert sei.tags_curtas == [NOVO, MANTIS_NAO, RC_SIM, DISA_SIM, AGUARDA_RELATORIO]
    assert curto(registro.marcadores_removidos[0]) == DISA_NAO


def test_falha_ao_criar_deproc_retoma_pelo_estado(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 1
    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, MANTIS]
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO

    sei.falhar_memo_n = None
    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]
    assert sei.qnt_memos_geacs == 1
    assert sei.pdfs == [PDF_TIT_RC]
    assert registro.memos_criados == ['memo_deproc']


def test_falha_depois_do_relatorio_nao_duplica_o_pdf(sei):
    sei.novo_processo()
    sei.falhar_memo_n = 1
    sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_SIM, RC_NAO, MANTIS]
    assert sei.pdfs == [PDF_DEP_RP]

    sei.falhar_memo_n = None
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)
    assert registro.erro is None
    assert sei.pdfs == [PDF_DEP_RP]
    assert registro.relatorios_na_arvore == [sei.numero_sei(PDF_DEP_RP)]
    assert registro.relatorios_incluidos == []
    assert sei.tags_curtas[-1] == AGUARDA_N_CONSTA
    # Na retomada, o memo cita o relatório que já estava na árvore
    assert f'no documento {sei.numero_sei(PDF_DEP_RP)}' in sei.texto_ultimo_memo_geacs


# --- Memo da APIS e base APIS ---------------------------------------------------


def test_base_apis_para_com_memo_a_apis(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_na_apis=False))
    assert sei.tags_curtas == [NOVO, '1.2.1 - Mat. N Encontradas Base APIS', '1.6.1 - Aguarda APIS: Matrículas']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_MAT_NAO_ENCONTRADAS
    assert registro.titular_nao_encontrado_base_geral == TITULAR

    registro = sei.passar(bases(tit_na_apis=False))
    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
    assert sei.qnt_memos_geacs == 1


def test_base_apis_corrigida_remove_o_1_2_1_e_segue(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MAT_NAO_ENCONTRADAS_APIS]
    registro = sei.passar(bases(tit_usou=False), SO_RC)

    assert registro.erro is None
    assert registro.marcadores_removidos[0] == TAG_MAT_NAO_ENCONTRADAS_APIS
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]


def test_sem_memo_da_apis(sei):
    sei.novo_processo(com_memo_apis=False)
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Aguarda APIS: Sem Memo p/ GEACS']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_SEM_MEMO


def test_modelo_novo_velho_e_formato_invalido(sei):
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_NOVO_VELHO)
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Aguarda APIS: Formato Inválido']
    assert 'novo_velho' in registro.motivo_formato_invalido


def test_usa_o_ultimo_memo_da_apis(sei, monkeypatch):
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_NOVO_VELHO)
    ultimo = sei.memo_apis()
    memos = []
    incluir_memo = processar_novo.incluir_memo
    monkeypatch.setattr(processar_novo, 'incluir_memo', lambda driver, registro, memo, *args, **kwargs: memos.append(memo) or incluir_memo(driver, registro, memo, *args, **kwargs))
    registro = sei.passar(bases(tit_usou=False), SO_RC)

    doc_ultimo = next(doc for doc in sei.docs if doc['numero_sei'] == ultimo)
    assert registro.memo_apis_sei == ultimo
    assert registro.memo_apis == doc_ultimo
    assert [memo.memo_apis for memo in memos] == [doc_ultimo]
    assert registro.modelo_memo_apis == 'novo_novo'
    assert sei.tags_curtas[-1] == CONCLUIDO_DEPROC


def test_periodo_variavel_para_dependentes(sei):
    sei.novo_processo(extra='Dependente 555: 01/02/2024 a 01/03/2024')
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, DISA_SIM, '1.1 - Período Variável p/ Dependentes', '1.7 - Aguarda APIS: Período Deps']
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_APIS_PERIODO_DEPS


def test_modelo_periodo_por_dependente_usa_o_periodo_de_cada_um(sei):
    # O dependente tem atendimento em 03/2024, fora do período dele
    # (01/01/2023 a 28/02/2023) e dentro do período do titular: não usou. O
    # fluxo não para pelo período variável (sem 1.1 e 1.7)
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_PERIODO_POR_DEPENDENTE)
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)

    assert registro.modelo_memo_apis == 'periodo_por_dependente'
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_NAO, AGUARDA_SEM_USO]
    assert registro.to_dict()['periodos_por_dependente'] == '555: 01/01/2023 a 28/02/2023'
    assert 'Período de apuração do dependente 555:' in sei.texto_ultimo_memo_geacs


def test_atendimento_no_periodo_do_dependente_conta_como_uso(sei):
    # Atendimento em 03/2024, dentro do período próprio do dependente
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_PERIODO_POR_DEPENDENTE.replace('01/01/2023 a 28/02/2023', '01/03/2024 a 31/03/2024'))
    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_SIM, RC_NAO, AGUARDA_N_CONSTA]
    assert registro.prox_acao == ProxAcao.ASSINAR_MEMO_DISA_VALIDAR_NAO_CONSTA


def test_matriculas_do_memo_com_e_sem_dv(sei):
    # Titular sem DV e dependente com DV no memo: as bases são consultadas
    # do mesmo jeito, e o período do dependente continua valendo
    texto = MEMO_APIS_PERIODO_POR_DEPENDENTE.replace('01/01/2023 a 28/02/2023', '01/03/2024 a 31/03/2024')
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(texto.replace('Matrícula: 1234567 / 8', 'Matrícula: 1234567').replace('Matrícula do dependente: 555', 'Matrícula do dependente: 5559'))
    registro = sei.passar(bases(), MANTIS_DEPENDENTE_USOU)

    assert sei.tags_curtas == [NOVO, DISA_SIM, MANTIS_SIM, RC_NAO, AGUARDA_CONSTA]
    assert registro.tit_usou
    assert registro.deps_que_usaram_mantis_rede_propria == ['555']


def test_dependente_sem_periodo_no_modelo_por_dependente_para_com_memo_a_apis(sei):
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_apis(MEMO_APIS_PERIODO_POR_DEPENDENTE, extra='Matrícula do dependente: 666')
    registro = sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Aguarda APIS: Formato Inválido']
    assert 'fora de dupla' in registro.motivo_formato_invalido


# --- Marcadores -----------------------------------------------------------------


def test_falha_na_remocao_deixa_dois_estados_e_gera_erro(sei):
    sei.novo_processo()
    sei.falhar_remocao = True
    sei.passar(bases(tit_usou=False), SO_RC)
    assert sei.tags_curtas == [NOVO, DISA_NAO, DISA, MANTIS_NAO, RC_SIM, MANTIS]

    sei.falhar_remocao = False
    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert 'mais de um marcador de estado' in registro.erro
    assert registro.prox_acao == ProxAcao.VERIFICAR_MARCADORES


def test_marcadores_inconsistentes_param_antes_de_qualquer_acao(sei):
    # Concluído (1.10) com matrícula fora da base APIS (1.2.1): impossível
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MAT_NAO_ENCONTRADAS_APIS, TAG_MEMO_DEPROC_COPARTICIPACAO]
    registro = sei.passar(bases())

    assert registro.tipo_erro == 'MarcadoresInconsistentes'
    assert registro.prox_acao == ProxAcao.VERIFICAR_MARCADORES
    assert registro.marcadores_adicionados == []
    assert sei.qnt_memos_geacs == 0


def test_processo_com_documentos_antigos_da_geacs_e_tratado_como_novo(sei):
    # Memo DEPROC de um pedido anterior da APIS, antes do último memo da
    # APIS. Não é reaproveitado (é de outra rodada)
    sei.novo_doc('E-mail', 'IPSEMG/APIS-Utilização', 'e-mail')
    sei.memo_geacs(ASSUNTO_MEMO_DEPROC)
    sei.tags = ['Script v2 - 2 - Processo VELHO']
    sei.memo_apis()

    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert registro.erro is None
    assert registro.memo_deproc_criado
    assert sei.assuntos_memos_geacs == [ASSUNTO_MEMO_DEPROC, ASSUNTO_MEMO_DEPROC]
    assert sei.tags_curtas[-1] == CONCLUIDO_DEPROC


def test_memo_disa_da_versao_anterior_e_parada(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMO_DISA_USO_REDE_PROPRIA]
    registro = sei.passar(bases())

    assert registro.prox_acao == ProxAcao.AGUARDAR_RESPOSTA_MEMO
    assert registro.marcadores_adicionados == []


# --- Retomada pelo assunto (memo criado sem marcador) -------------------------


def test_memo_deproc_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + t for t in (NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, MANTIS)]
    numero_deproc = sei.memo_geacs(ASSUNTO_MEMO_DEPROC)

    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert registro.erro is None
    assert sei.qnt_memos_geacs == 1
    assert registro.memo_deproc_na_arvore
    assert registro.memo_deproc_sei == numero_deproc
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]


def test_memo_deproc_com_assunto_anterior_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + t for t in (NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, MANTIS)]
    sei.memo_geacs('Levantamento de coparticipação - utilização indevida da assistência à saúde')

    registro = sei.passar(bases(tit_usou=False), SO_RC)
    assert sei.qnt_memos_geacs == 1
    assert registro.memo_deproc_na_arvore


def test_memo_disa_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = ['Script v2 - ' + NOVO, 'Script v2 - ' + MANTIS]
    sei.memo_geacs(ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA)

    registro = sei.passar(bases(tit_usou=False), MANTIS_DEPENDENTE_USOU)
    assert registro.erro is None
    assert registro.memo_disa_na_arvore
    assert registro.memos_criados == []
    assert sei.qnt_memos_geacs == 1
    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_SIM, RC_NAO, AGUARDA_N_CONSTA]


def test_memo_a_apis_sem_marcador_e_reaproveitado(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MAT_NAO_ENCONTRADAS_APIS]
    sei.memo_geacs(ASSUNTO_MEMO_MAT_NAO_ENCONTRADAS)

    registro = sei.passar(bases(tit_na_apis=False))
    assert registro.erro is None
    assert registro.memo_apis_mat_nao_encontradas_na_arvore
    assert sei.qnt_memos_geacs == 1
    assert sei.tags_curtas[-1] == '1.6.1 - Aguarda APIS: Matrículas'


# --- Vindo do fluxo ALT 1 ------------------------------------------------------


def test_aguardando_fluxo_normal_e_tratado_do_inicio(sei):
    sei.novo_processo()
    sei.novo_doc('PDF Utilização Tit. - 3542985 - SEI 1000', 'IPSEMG/GEACS - Utilização', '')
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]

    registro = sei.passar(bases(tit_usou=False), SO_RC)

    assert sei.tags_curtas == [NOVO, DISA_NAO, MANTIS_NAO, RC_SIM, CONCLUIDO_DEPROC]
    assert TAG_AGUARDA_FLUXO_NORMAL in registro.marcadores_removidos
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC
    assert registro.erro is None
    # O PDF do ALT 1 fica no processo, e o relatório do MANTIS entra também
    assert PDF_TIT_RC in sei.pdfs


def test_aguardando_fluxo_normal_parado_troca_o_estado(sei):
    sei.novo_processo(com_memo_apis=False)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]

    sei.passar(bases())

    assert sei.tags_curtas == [NOVO, '1.5 - Aguarda APIS: Sem Memo p/ GEACS']


# --- VELHO (enviado à DISA e à DEPROC antes de 01/10/2026) ---------------------


def _memos_disa_deproc(sei, data_disa='18 de setembro de 2026', data_deproc='19 de setembro de 2026'):
    sei.novo_processo()
    disa = sei.memo_geacs_para(DISA_UTI_INDEV, data_disa)
    deproc = sei.memo_geacs_para(DEPROC, data_deproc)
    return [disa, deproc]


def test_velho_pelos_memos_disa_e_deproc_nao_e_processado(sei):
    memos = _memos_disa_deproc(sei)
    registro = sei.passar(bases(), MANTIS_DUAS_REDES)

    assert registro.velho
    assert registro.memos_velho_sei == memos
    assert registro.prox_acao == ProxAcao.VELHO_AGUARDAR_DEFINICAO
    assert sei.tags_curtas == [VELHO]
    assert registro.memos_criados == []
    assert sei.pdfs == []

    registro = sei.passar(bases(), MANTIS_DUAS_REDES)
    assert registro.prox_acao == ProxAcao.VELHO_AGUARDAR_DEFINICAO
    assert registro.marcadores_adicionados == []


def test_velho_pelos_memos_prevalece_sobre_o_aguardo_do_fluxo_normal(sei):
    _memos_disa_deproc(sei)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL]

    registro = sei.passar(bases(), MANTIS_DUAS_REDES)

    assert registro.prox_acao == ProxAcao.VELHO_AGUARDAR_DEFINICAO
    assert sei.tags_curtas == [NOVO, VELHO]
    assert registro.memos_criados == []


def test_velho_tratado_manualmente_sai_do_aguardo_do_fluxo_normal(sei):
    _memos_disa_deproc(sei)
    sei.tags = [TAG_PROCESSO_NOVO, TAG_AGUARDA_FLUXO_NORMAL, TAG_MANUAL]

    registro = sei.passar(bases(), MANTIS_DUAS_REDES)

    assert registro.prox_acao == ProxAcao.FORA_DO_ESCOPO
    assert TAG_AGUARDA_FLUXO_NORMAL not in sei.tags


def test_velho_pelo_marcador_1_3_da_versao_anterior(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMOS_DISA_DEPROC_NO_BLOCO]
    registro = sei.passar(bases())

    assert registro.prox_acao == ProxAcao.VELHO_AGUARDAR_DEFINICAO
    assert sei.tags_curtas[-1] == VELHO
    assert registro.memos_criados == []


def test_velho_tratado_manualmente_fica_fora_do_escopo(sei):
    _memos_disa_deproc(sei)
    sei.tags.append(TAG_MANUAL)
    registro = sei.passar(bases())

    assert registro.prox_acao == ProxAcao.FORA_DO_ESCOPO
    assert registro.marcadores_adicionados == []


def test_memos_disa_e_deproc_depois_da_data_de_corte_nao_sao_velho(sei):
    _memos_disa_deproc(sei, '1 de outubro de 2026', '1 de outubro de 2026')
    registro = sei.passar(bases(tit_usou=False), SO_RC)

    assert not registro.velho
    assert sei.tags_curtas[-1] == CONCLUIDO_DEPROC


def test_memos_deproc_e_disa_na_ordem_inversa_nao_sao_velho(sei):
    sei.novo_processo()
    sei.memo_geacs_para(DEPROC)
    sei.memo_geacs_para(DISA_UTI_INDEV)
    registro = sei.passar(bases(tit_usou=False))

    assert not registro.velho


def test_memos_disa_e_deproc_nao_seguidos_nao_sao_velho(sei):
    sei.novo_processo()
    sei.memo_geacs_para(DISA_UTI_INDEV)
    sei.memo_geacs('outro memo')
    sei.memo_geacs_para(DEPROC)
    registro = sei.passar(bases(tit_usou=False))

    assert not registro.velho


def test_memos_disa_e_deproc_sem_data_geram_erro_sem_acao(sei):
    _memos_disa_deproc(sei, data_deproc=None)
    registro = sei.passar(bases())

    assert 'não foi possível conferir se o processo é VELHO' in registro.erro
    assert registro.marcadores_adicionados == []


def test_versao_anterior_so_deproc_e_concluido(sei):
    sei.novo_processo()
    sei.tags = [TAG_PROCESSO_NOVO, TAG_MEMO_DEPROC_NO_BLOCO]
    registro = sei.passar(bases())

    assert registro.erro is None
    assert registro.prox_acao == ProxAcao.ASSINAR_DEPROC


def test_nome_do_relatorio_cabe_no_sei():
    assert len(f'{inicio_nome_relatorio(REDE_CREDENCIADA, "Dep.", "123456789")} - 20261022_103324') <= 50


def test_processo_fechado_no_setor_e_reaberto_e_segue_o_fluxo(sei):
    sei.novo_processo()
    sei.processo_fechado = True

    registro = sei.passar(bases(tit_usou=False))

    assert sei.reaberturas == 1
    assert registro.processo_reaberto is True
    assert registro.to_dict()['processo_reaberto'] is True
    assert registro.erro is None
    assert TAG_PROCESSO_NOVO in sei.tags


def test_processo_aberto_nao_e_reaberto(sei):
    sei.novo_processo()
    registro = sei.passar(bases(tit_usou=False))

    assert sei.reaberturas == 0
    assert registro.processo_reaberto is False


def test_processo_fechado_que_nao_reabre_e_erro_sem_acao_no_sei(sei):
    sei.processo_fechado = True
    sei.processo_reabrivel = False
    sei.tags.append(TAG_AGUARDA_FLUXO_NORMAL)
    docs_antes = list(sei.nomes)

    registro = sei.passar(bases(tit_usou=False))

    assert registro.tipo_erro == 'ProcessoFechadoNoSetor'
    assert 'não foi possível reabrir' in registro.erro
    assert registro.prox_acao == ProxAcao.VERIFICAR_ERRO
    assert registro.processo_reaberto is False
    assert sei.tags == [TAG_AGUARDA_FLUXO_NORMAL]
    assert sei.nomes == docs_antes


def test_navegador_fechado_registra_o_erro_do_processo_e_para_o_loop(monkeypatch, tmp_path):
    gravados: list[tuple] = []

    class Controle:
        def __init__(self, *args):
            pass

        @staticmethod
        def registrar(linha):
            gravados.append((linha['num_processo'], linha['tipo_erro']))

    class Driver:
        @staticmethod
        def quit():
            return None

    def processar(driver, num_processo, *args):
        registro = RegistroMain(num_processo=num_processo, data_execucao='agora')
        if num_processo != 'P1':
            registrar_erro(registro, InvalidSessionIdException('invalid session id'))
        return registro

    monkeypatch.setattr(main, 'configurar_logging', lambda arquivo: None)
    monkeypatch.setattr(main.pd, 'read_excel', lambda **kwargs: pd.DataFrame({'num_sei': ['P1', 'P2', 'P3']}))
    monkeypatch.setattr(main, 'carregar_bases', lambda *args: None)
    monkeypatch.setattr(main, 'carregar_bases_mantis', lambda *args: None)
    monkeypatch.setattr(main, 'PlanilhaControleGeral', Controle)
    monkeypatch.setattr(main, 'abrir_sei', lambda download_dir=None: Driver())
    monkeypatch.setattr(main, '_processar_linha', processar)
    for constante in ('DIR_DADOS', 'DIR_INPUTS', 'DIR_CONTROLE', 'DIR_LOG', 'DIR_UI_ANTIGAS_XLS', 'DIR_UTILIZACOES_MANTIS_PDF'):
        monkeypatch.setattr(main, constante, tmp_path)

    main.main()

    assert gravados == [('P1', None), ('P2', 'InvalidSessionIdException')]
