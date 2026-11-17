"""Fluxo GEACS TODAS INFOS (main_geacs_todas_infos.py): leitura e conferência
dos valores do retorno final à APIS (MemoApisComTodasAsInformacoes).

Cada valor do memo é lido do SEI e recalculado das bases; se não baterem, o
processo para (ValoresDivergentes), sem criar o memo:

- coparticipação por matrícula e total, e valor total em aberto: lidos do
  memo da DEPROC à GEACS (MemoGeacsCalculoCopa) e recalculados na base DEPROC
  (coparticipacao_deproc.apurar_coparticipacao, como no fluxo DEPROC). No
  memo à APIS entra o valor **em aberto** (o já descontado em folha não é
  somado à utilização);
- rede credenciada e rede própria: o TOTAL de cada PDF do MANTIS da rodada
  (baixado do SEI e lido com pypdf) e o recálculo nas bases do MANTIS, no
  período do memo da APIS (como no geacs_inicial).

Caminho do processo: direto à DEPROC, ou pela DISA antes (memo da GEACS à
DISA na rodada). No caminho direto, a rede própria pode ter uso no MANTIS
(sem constar na base DISA: o processo não vai à DISA); uso na base DISA é
divergência. No caminho com DISA, os valores da rede própria vêm da
resposta da DISA, cuja leitura ainda não foi implementada (TODO): o processo
para com erro.
"""

import base64
import io
import logging
import re
from dataclasses import dataclass

import pandas as pd
from constantes import PREFIXO_UNIDADE_DISA, UNIDADE_DEPROC
from coparticipacao_deproc import DEPENDENTE, TITULAR, ResultadoDeproc, apurar_coparticipacao, formatar_matricula_com_dv, mesma_matricula
from docs_processo import encontrar_doc_por_nome, encontrar_memo_por_assunto, filtrar_memos_geacs, ler_texto_doc, selecionar_doc
from mantis import AvaliacaoMantis, BasesMantis, UsoMantis, avaliar_uso_rede_propria_mantis
from processar_novo import sem_dependentes
from pypdf import PdfReader
from rede_propria import BasesUso, ErroAvaliacao, MatriculasProcesso, avaliar_uso_rede_propria_disa, normalizar_matricula, verificar_base_apis
from relatorios_mantis import REDE_CREDENCIADA, REDE_PROPRIA, TIPO_DOC, inicio_nome_relatorio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI, iniciais_nome
from script_sei_utilizacao_indevida_v2.memorandos.MemoApisComTodasAsInformacoes import ValoresBeneficiario, formatar_reais
from script_sei_utilizacao_indevida_v2.memorandos.MemoDisa import (
    PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA,
    PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA,
)
from script_sei_utilizacao_indevida_v2.memorandos.MemoGeacsCalculoCopa import PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA

logger = logging.getLogger(__name__)

CAMINHO_DEPROC = 'DEPROC'
CAMINHO_DISA = 'DISA'

# Diferença aceita entre o valor lido no SEI e o recalculado (arredondamento)
TOLERANCIA = 0.005

# Tempo para o documento externo aparecer no visualizador e para o download
TEMPO_VISUALIZACAO = 30
TEMPO_DOWNLOAD = 60

# Memos da GEACS à DISA (os três casos da comparação base DISA x MANTIS)
_PADROES_MEMO_DISA = (PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_CONSTA, PADRAO_ASSUNTO_MEMO_DISA_VALIDAR_NAO_CONSTA, PADRAO_ASSUNTO_MEMO_DISA_SEM_MANTIS_RELATORIO)
_PADRAO_ASSINADO = re.compile(r'assinado\s+eletronicamente\s+por', re.IGNORECASE)
_PADRAO_SEM_COPARTICIPACAO = re.compile(r'Não\s+foram\s+identificados\s+atendimentos\s+com\s+coparticipação', re.IGNORECASE)
_VALOR = r'R\$\s*(-?[\d.]+,\d{2})'
# Linha da tabela do MemoGeacsCalculoCopa: iniciais, matrícula, vínculo, valor
_PADRAO_LINHA_COPART = re.compile(rf'(\d[\d.\s/-]*?)\s+(Titular|Dependente)\s+{_VALOR}', re.IGNORECASE)
_PADRAO_TOTAL_COPART = re.compile(rf'Total\s+consolidado\s+{_VALOR}', re.IGNORECASE)
# Tabela de totais do MemoGeacsCalculoCopa (apurado, descontado e em aberto)
_PADRAO_EM_ABERTO = re.compile(rf'Valor\s+total\s+em\s+aberto\s+{_VALOR}', re.IGNORECASE)
# Linha TOTAL dos PDFs do MANTIS (transformar_xls_em_pdf): valor sem "R$"
_PADRAO_TOTAL_PDF = re.compile(r'\bTOTAL\b[^\d-]*(-?[\d.]+,\d{2})')
_PREFIXO_RELATORIO_DEPROC = f'{TIPO_DOC} Coparticipação - '


class RespostaDisaPendente(ErroAvaliacao):
    """Processo com memo da GEACS à DISA e sem a resposta da DISA."""


class LeituraDisaNaoImplementada(ErroAvaliacao):
    """Processo que passou pela DISA: a leitura da resposta ainda não existe."""


class ValoresDivergentes(ErroAvaliacao):
    """Valor lido no SEI diferente do recalculado nas bases."""

    def __init__(self, divergencias: list[str]):
        self.divergencias = divergencias
        super().__init__(f'Valores do SEI diferentes do recálculo: {"; ".join(divergencias)}')


def _reais(texto: str) -> float:
    """'1.234,56' -> 1234.56."""
    return float(texto.replace('.', '').replace(',', '.'))


def _difere(a: float, b: float) -> bool:
    return abs(round(a, 2) - round(b, 2)) > TOLERANCIA


# ---------------------------------------------------------------------------
# Caminho: direto à DEPROC ou pela DISA antes
# ---------------------------------------------------------------------------


def identificar_caminho(driver: webdriver.Remote, registro) -> str:
    """DISA: há memo da GEACS à DISA na rodada. Sem resposta da DISA depois
    dele: RespostaDisaPendente. Com resposta: LeituraDisaNaoImplementada
    (TODO: ler os valores da rede própria da resposta da DISA)."""
    memo_disa = None
    for memo in reversed(filtrar_memos_geacs(registro.docs_rodada)):
        texto = ler_texto_doc(driver, memo)
        if any(padrao.search(texto) for padrao in _PADROES_MEMO_DISA):
            memo_disa = memo
            break
    if memo_disa is None:
        registro.caminho_todas_infos = CAMINHO_DEPROC
        logger.info('Caminho: direto à DEPROC (nenhum memo da GEACS à DISA na rodada)')
        return CAMINHO_DEPROC

    registro.caminho_todas_infos = CAMINHO_DISA
    registro.memo_disa_geacs_sei = memo_disa['numero_sei']
    indice = next(i for i, doc in enumerate(registro.docs_rodada) if doc['numero_sei'] == memo_disa['numero_sei'])
    respostas = [doc for doc in registro.docs_rodada[indice + 1 :] if doc['unidade'].upper().startswith(PREFIXO_UNIDADE_DISA)]
    logger.info(f'Caminho: pela DISA (memo da GEACS à DISA {memo_disa["numero_sei"]}); resposta(s) da DISA: {[d["numero_sei"] for d in respostas] or "nenhuma"}')
    if not respostas:
        raise RespostaDisaPendente(f'Processo com memo da GEACS à DISA ({memo_disa["numero_sei"]}) e sem resposta da DISA na árvore')
    registro.resposta_disa_sei = respostas[-1]['numero_sei']
    # TODO: ler da resposta da DISA o valor da rede própria por beneficiário
    # (doc_levantamento_disa do memo) e conferir com o recálculo
    raise LeituraDisaNaoImplementada(f'Processo que passou pela DISA (resposta {registro.resposta_disa_sei}): leitura da resposta da DISA ainda não implementada')


# ---------------------------------------------------------------------------
# Memo da DEPROC à GEACS (MemoGeacsCalculoCopa)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CopartDoMemo:
    """Coparticipação lida do texto do MemoGeacsCalculoCopa."""

    # Matrícula normalizada (com DV, como no memo) -> valor apurado
    por_matricula: dict[str, float]
    total: float
    sem_coparticipacao: bool = False
    # "Valor total em aberto" da tabela de totais. Memo sem essa linha (sem
    # desconto informado): o total apurado
    em_aberto: float = 0.0
    em_aberto_no_memo: bool = False


def memo_calculo_copa(driver: webdriver.Remote, registro) -> tuple[dict, str]:
    """O MemoGeacsCalculoCopa da rodada, assinado, com o texto."""
    encontrado = encontrar_memo_por_assunto(driver, registro.docs_rodada, PADRAO_ASSUNTO_MEMO_GEACS_CALCULO_COPA, 'de resultado da DEPROC', UNIDADE_DEPROC)
    if encontrado is None:
        raise ErroAvaliacao('Memo de resultado da DEPROC (cálculo da coparticipação) não encontrado depois do último memo da APIS destinado à GEACS')
    memo, texto = encontrado
    registro.memo_calculo_copa_sei = memo['numero_sei']
    registro.memo_calculo_copa_assinado = _PADRAO_ASSINADO.search(texto) is not None
    if not registro.memo_calculo_copa_assinado:
        raise ErroAvaliacao(f'Memo de resultado da DEPROC ({memo["numero_sei"]}) ainda não assinado')
    return memo, texto


def ler_coparticipacao_do_memo(texto: str) -> CopartDoMemo:
    """Tabela por matrícula e total consolidado do MemoGeacsCalculoCopa (texto
    do SEI ou HTML). Sem coparticipação, o memo diz que não há atendimentos."""
    texto = re.sub(r'<[^>]+>', ' ', texto)
    if _PADRAO_SEM_COPARTICIPACAO.search(texto):
        return CopartDoMemo({}, 0.0, sem_coparticipacao=True)
    linhas = _PADRAO_LINHA_COPART.findall(texto)
    total = _PADRAO_TOTAL_COPART.search(texto)
    if not linhas or total is None:
        raise ErroAvaliacao('Tabela de coparticipação por matrícula não encontrada no texto do memo de resultado da DEPROC')
    por_matricula: dict[str, float] = {}
    for matricula, _, valor in linhas:
        chave = normalizar_matricula(matricula)
        por_matricula[chave] = round(por_matricula.get(chave, 0.0) + _reais(valor), 2)
    total_apurado = _reais(total.group(1))
    em_aberto = _PADRAO_EM_ABERTO.search(texto)
    if em_aberto is None:
        return CopartDoMemo(por_matricula, total_apurado, em_aberto=total_apurado)
    return CopartDoMemo(por_matricula, total_apurado, em_aberto=_reais(em_aberto.group(1)), em_aberto_no_memo=True)


def conferir_coparticipacao(memo: CopartDoMemo, resultado: ResultadoDeproc) -> list[str]:
    """Coparticipação do memo x recálculo na base DEPROC."""
    recalculo = {normalizar_matricula(b.matricula): round(b.valor, 2) for b in resultado.beneficiarios if round(b.valor, 2) != 0}
    total = resultado.totais.coparticipacao if resultado.tem_coparticipacao else 0.0
    if memo.sem_coparticipacao:
        if resultado.tem_coparticipacao:
            return [f'memo da DEPROC sem coparticipação, recálculo {formatar_reais(total)}']
        return []
    divergencias = []
    for matricula in sorted(memo.por_matricula.keys() | recalculo.keys()):
        lido, calculado = memo.por_matricula.get(matricula, 0.0), recalculo.get(matricula, 0.0)
        if _difere(lido, calculado):
            divergencias.append(f'coparticipação de {matricula}: memo da DEPROC {formatar_reais(lido)}, recálculo {formatar_reais(calculado)}')
    if _difere(memo.total, total):
        divergencias.append(f'coparticipação total: memo da DEPROC {formatar_reais(memo.total)}, recálculo {formatar_reais(total)}')
    em_aberto = resultado.totais.em_aberto
    if _difere(memo.em_aberto, em_aberto):
        lido = 'memo da DEPROC' if memo.em_aberto_no_memo else 'memo da DEPROC sem o valor em aberto (considerado o total apurado)'
        divergencias.append(f'coparticipação em aberto: {lido} {formatar_reais(memo.em_aberto)}, recálculo {formatar_reais(em_aberto)}')
    return divergencias


def doc_coparticipacao(registro, sem_coparticipacao: bool) -> str:
    """Detalhamento da coparticipação citado no memo: o relatório da DEPROC
    na rodada ou, sem coparticipação, o próprio memo da DEPROC."""
    if sem_coparticipacao:
        return registro.memo_calculo_copa_sei
    relatorios = [doc for doc in registro.docs_rodada if doc['unidade'] == UNIDADE_DEPROC and doc['nome_arvore'].startswith(_PREFIXO_RELATORIO_DEPROC)]
    if not relatorios:
        raise ErroAvaliacao('Relatório de coparticipação da DEPROC não encontrado depois do último memo da APIS destinado à GEACS')
    return relatorios[-1]['numero_sei']


# ---------------------------------------------------------------------------
# MANTIS: recálculo e PDFs da rodada
# ---------------------------------------------------------------------------


def recalcular_mantis(dados_ui: DadosUI, bases: BasesUso, bases_mantis: BasesMantis) -> tuple[DadosUI, MatriculasProcesso, AvaliacaoMantis]:
    """Uso das redes no MANTIS, como no geacs_inicial: dependente fora da base
    APIS e do MANTIS dos dependentes não encontrados é ignorado. Devolve os
    dados do memo da APIS sem os ignorados."""
    if dados_ui.periodo_dependentes:
        raise ErroAvaliacao('Memo da APIS com período variável para dependentes: sem período de cada dependente para o MANTIS')
    matriculas = verificar_base_apis(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    nao_encontradas = matriculas.nao_encontradas_apis
    if nao_encontradas.titular:
        raise ErroAvaliacao(f'Titular {nao_encontradas.titular} não encontrado na base APIS')
    ignorados = tuple(d for d in nao_encontradas.dependentes if not bases_mantis.tem_dependente_nao_encontrado(d))
    if ignorados:
        logger.warning(f'Dependente(s) fora da base APIS e do MANTIS dos dependentes não encontrados: {", ".join(ignorados)}. Ignorado(s), como no geacs_inicial')
        dados_ui = sem_dependentes(dados_ui, ignorados)
        matriculas = verificar_base_apis(dados_ui.matricula_titular, dados_ui.matriculas_dependentes, bases)
    avaliacao = avaliar_uso_rede_propria_mantis(
        matriculas.titular,
        matriculas.dependentes,
        dados_ui.periodo_titular,
        bases_mantis,
        matriculas.periodos_dos_dependentes(dados_ui.periodos_por_dependente),
        deps_nao_encontrados=matriculas.nao_encontradas_apis.dependentes,
    )
    return dados_ui, matriculas, avaliacao


@dataclass(frozen=True)
class RelatoriosRede:
    """PDFs do MANTIS de uma rede na rodada (número SEI ou None)."""

    titular: str | None
    dependentes: str | None

    @property
    def numeros(self) -> list[str]:
        return [n for n in (self.titular, self.dependentes) if n]


_JS_BAIXAR = """
const [url, pronto] = arguments;
fetch(url, {credentials: 'include'})
  .then(r => r.ok ? r.arrayBuffer() : Promise.reject('HTTP ' + r.status))
  .then(b => {
    const a = new Uint8Array(b);
    let s = '';
    for (let i = 0; i < a.length; i += 32768) s += String.fromCharCode.apply(null, a.subarray(i, i + 32768));
    pronto(btoa(s));
  })
  .catch(e => pronto('ERRO: ' + e));
"""
# URL do último anexo buscado: ao abrir o próximo PDF, a moldura pode ainda
# mostrar o anterior por um instante
_ultimo_anexo: str | None = None


def _src_iframe(id_iframe: str, diferente_de: str | None = None):
    """Condição do WebDriverWait: a URL (src) do iframe, carregada e
    diferente de diferente_de."""

    def src(driver: webdriver.Remote) -> str | bool:
        iframes = driver.find_elements(By.ID, id_iframe)
        valor = iframes[0].get_attribute('src') if iframes else None
        return valor if valor and valor not in {'about:blank', diferente_de} else False

    return src


def _buscar(driver: webdriver.Remote, url: str, numero_sei: str) -> bytes:
    resposta = driver.execute_async_script(_JS_BAIXAR, url)
    if not isinstance(resposta, str) or resposta.startswith('ERRO'):
        raise ErroAvaliacao(f'Documento {numero_sei} não baixado ({resposta})')
    return base64.b64decode(resposta)


def baixar_pdf(driver: webdriver.Remote, doc: dict) -> bytes:
    """Conteúdo do documento externo em PDF. O Chrome abre o PDF no
    visualizador (não baixa): o arquivo é buscado, na sessão do navegador,
    pela URL do anexo (acao=documento_download_anexo). Ela está no iframe
    ifrArvoreHtml, dentro de ifrVisualizacao, dentro de
    ifrConteudoVisualizacao, e é inserida pelo JavaScript do SEI (não está no
    HTML da URL de ifrVisualizacao; conferido no SEI real em 13/11/2026)."""
    global _ultimo_anexo  # noqa: PLW0603
    selecionar_doc(driver, doc)
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame('ifrConteudoVisualizacao')
        WebDriverWait(driver, TEMPO_VISUALIZACAO).until(_src_iframe('ifrVisualizacao'))
        driver.switch_to.frame(driver.find_element(By.ID, 'ifrVisualizacao'))
        url = WebDriverWait(driver, TEMPO_VISUALIZACAO).until(_src_iframe('ifrArvoreHtml', _ultimo_anexo))
        driver.set_script_timeout(TEMPO_DOWNLOAD)
        conteudo = _buscar(driver, url, doc['numero_sei'])
    finally:
        driver.switch_to.default_content()
    if not conteudo.startswith(b'%PDF'):
        raise ErroAvaliacao(f'Documento {doc["numero_sei"]} não veio como PDF')
    _ultimo_anexo = url
    logger.info(f'PDF baixado: {doc["nome_arvore"]} (SEI {doc["numero_sei"]}, {len(conteudo)} bytes)')
    return conteudo


def total_do_pdf(conteudo: bytes) -> float:
    """Valor da linha TOTAL de um PDF do MANTIS (transformar_xls_em_pdf)."""
    texto = '\n'.join(pagina.extract_text() or '' for pagina in PdfReader(io.BytesIO(conteudo)).pages)
    totais = _PADRAO_TOTAL_PDF.findall(texto)
    if not totais:
        raise ErroAvaliacao('Linha TOTAL não encontrada no PDF')
    return _reais(totais[-1])


def relatorios_da_rede(registro, uso: UsoMantis, rede: tuple[str, str], matricula_titular: str) -> tuple[RelatoriosRede, list[str]]:
    """PDFs da rede na rodada (o mais recente de titular e de dependentes) e
    as divergências de existência: atendimento recalculado sem PDF, ou PDF
    sem atendimento recalculado."""
    numeros = {}
    divergencias = []
    for tipo_curto, descricao, usou in (('Tit.', 'titular', bool(uso.tit_atendimentos)), ('Dep.', 'dependentes', bool(uso.deps_atendimentos))):
        doc = encontrar_doc_por_nome(registro.docs_rodada, f'{TIPO_DOC} {inicio_nome_relatorio(rede, tipo_curto, matricula_titular)}')
        numeros[descricao] = doc['numero_sei'] if doc else None
        if usou and doc is None:
            divergencias.append(f'{rede[1]} ({descricao}): atendimento no recálculo do MANTIS, mas sem PDF na rodada')
        elif doc is not None and not usou:
            divergencias.append(f'{rede[1]} ({descricao}): PDF {doc["numero_sei"]} na rodada, mas nenhum atendimento no recálculo do MANTIS')
    return RelatoriosRede(numeros['titular'], numeros['dependentes']), divergencias


def conferir_pdfs(driver: webdriver.Remote, registro, relatorios: RelatoriosRede, uso: UsoMantis, rede: tuple[str, str]) -> list[str]:
    """TOTAL de cada PDF x total recalculado (titular / dependentes)."""
    divergencias = []
    for numero, descricao, esperado in ((relatorios.titular, 'titular', uso.tit_valor_total), (relatorios.dependentes, 'dependentes', uso.deps_valor_total)):
        if numero is None:
            continue
        doc = next(d for d in registro.docs_rodada if d['numero_sei'] == numero)
        lido = total_do_pdf(baixar_pdf(driver, doc))
        logger.info(f'{rede[1]} ({descricao}): PDF {numero} TOTAL {formatar_reais(lido)}, recálculo {formatar_reais(esperado)}')
        if _difere(lido, esperado):
            divergencias.append(f'{rede[1]} ({descricao}): PDF {numero} {formatar_reais(lido)}, recálculo {formatar_reais(esperado)}')
    return divergencias


# ---------------------------------------------------------------------------
# Linhas das tabelas do memo
# ---------------------------------------------------------------------------


def _valor_dependente(uso: UsoMantis, dependente: str) -> float:
    return round(sum(a.valor for m, a in uso.deps_atendimentos if m == dependente), 2)


def _usou(uso: UsoMantis, dependente: str) -> bool:
    return any(m == dependente for m, _ in uso.deps_atendimentos)


def _nome_dependente_mantis(avaliacao: AvaliacaoMantis, dependente: str) -> str:
    atendimentos = (*avaliacao.rede_credenciada.deps_atendimentos, *avaliacao.rede_propria.deps_atendimentos)
    return next((a.nome_dependente for m, a in atendimentos if m == dependente and a.nome_dependente), '')


def montar_beneficiarios(
    dados_ui: DadosUI,
    matriculas: MatriculasProcesso,
    avaliacao: AvaliacaoMantis,
    resultado: ResultadoDeproc,
    rc: RelatoriosRede,
    rp: RelatoriosRede,
) -> tuple[ValoresBeneficiario, ...]:
    """Titular e cada dependente do memo da APIS (sem os ignorados), com as
    iniciais e a matrícula, os valores recalculados e o PDF de cada rede
    (o de titular ou o de dependentes) de quem usou. A coparticipação é a
    em aberto (o já descontado em folha não é somado à utilização)."""
    credenciada, propria = avaliacao.rede_credenciada, avaliacao.rede_propria
    copart_titular = sum(b.em_aberto for b in resultado.beneficiarios if b.categoria == TITULAR)
    beneficiarios = [
        ValoresBeneficiario(
            identificacao=f'{dados_ui.nome_titular_iniciais} / {formatar_matricula_com_dv(matriculas.titular)}',
            valor_rede_credenciada=credenciada.tit_valor_total,
            valor_rede_propria=propria.tit_valor_total,
            coparticipacao=round(copart_titular, 2),
            doc_rede_credenciada=rc.titular if credenciada.tit_atendimentos else None,
            doc_rede_propria=rp.titular if propria.tit_atendimentos else None,
        )
    ]
    for dependente in matriculas.dependentes:
        da_deproc = [b for b in resultado.beneficiarios if b.categoria == DEPENDENTE and mesma_matricula(dependente, normalizar_matricula(b.matricula))]
        nome = da_deproc[0].nome if da_deproc else _nome_dependente_mantis(avaliacao, dependente)
        matricula = da_deproc[0].matricula if da_deproc else dependente
        valor_rc, valor_rp = _valor_dependente(credenciada, dependente), _valor_dependente(propria, dependente)
        beneficiarios.append(
            ValoresBeneficiario(
                identificacao=f'{iniciais_nome(nome) or "Dependente"} / {matricula}',
                valor_rede_credenciada=valor_rc,
                valor_rede_propria=valor_rp,
                coparticipacao=round(sum(b.em_aberto for b in da_deproc), 2),
                doc_rede_credenciada=rc.dependentes if _usou(credenciada, dependente) else None,
                doc_rede_propria=rp.dependentes if _usou(propria, dependente) else None,
            )
        )
    return tuple(beneficiarios)


def apurar_todas_infos(
    driver: webdriver.Remote,
    registro,
    dados_ui: DadosUI,
    texto_memo_copa: str,
    bases: BasesUso,
    bases_mantis: BasesMantis,
    base_deproc: pd.DataFrame,
) -> tuple[DadosUI, tuple[ValoresBeneficiario, ...], str]:
    """Lê e recalcula os valores (caminho direto à DEPROC). Divergência:
    ValoresDivergentes, antes de qualquer ação no SEI. Devolve os dados do
    memo da APIS (sem os dependentes ignorados), as linhas das tabelas e o
    documento da coparticipação."""
    copart = ler_coparticipacao_do_memo(texto_memo_copa)
    resultado = apurar_coparticipacao(base_deproc, registro.num_processo, dados_ui)
    divergencias = conferir_coparticipacao(copart, resultado)

    dados_memo, matriculas, avaliacao = recalcular_mantis(dados_ui, bases, bases_mantis)
    if avaliar_uso_rede_propria_disa(matriculas, bases).alguem_usou:
        # Com uso na base DISA, o processo deveria ter ido à DISA
        divergencias.append('uso da rede própria na base DISA sem passagem pela DISA')
    rc, faltando_rc = relatorios_da_rede(registro, avaliacao.rede_credenciada, REDE_CREDENCIADA, matriculas.titular)
    rp, faltando_rp = relatorios_da_rede(registro, avaliacao.rede_propria, REDE_PROPRIA, matriculas.titular)
    divergencias += faltando_rc + faltando_rp
    registro.relatorios_rc_sei, registro.relatorios_rp_sei = rc.numeros, rp.numeros
    if not divergencias:
        divergencias += conferir_pdfs(driver, registro, rc, avaliacao.rede_credenciada, REDE_CREDENCIADA)
        divergencias += conferir_pdfs(driver, registro, rp, avaliacao.rede_propria, REDE_PROPRIA)

    beneficiarios = montar_beneficiarios(dados_memo, matriculas, avaliacao, resultado, rc, rp)
    registro.valores_todas_infos = [
        f'{b.identificacao}: RC {formatar_reais(b.valor_rede_credenciada)}; RP {formatar_reais(b.valor_rede_propria)}; copart. em aberto {formatar_reais(b.coparticipacao)}' for b in beneficiarios
    ]
    registro.valor_total_rc_todas_infos = round(sum(b.valor_rede_credenciada for b in beneficiarios), 2)
    registro.valor_total_rp_todas_infos = round(sum(b.valor_rede_propria for b in beneficiarios), 2)
    registro.valor_total_copart_todas_infos = round(sum(b.coparticipacao for b in beneficiarios), 2)
    if divergencias:
        registro.divergencias_todas_infos = divergencias
        raise ValoresDivergentes(divergencias)
    if _difere(registro.valor_total_copart_todas_infos, copart.em_aberto):
        # Coparticipação de matrícula fora do memo da APIS (não acontece: a
        # base DEPROC confere as matrículas)
        raise ValoresDivergentes([f'coparticipação em aberto nas tabelas {formatar_reais(registro.valor_total_copart_todas_infos)}, memo da DEPROC {formatar_reais(copart.em_aberto)}'])
    logger.info(
        f'Valores conferidos | RC {formatar_reais(registro.valor_total_rc_todas_infos)} | RP {formatar_reais(registro.valor_total_rp_todas_infos)} | '
        f'Coparticipação em aberto {formatar_reais(registro.valor_total_copart_todas_infos)} (apurada {formatar_reais(copart.total)})'
    )
    return dados_memo, beneficiarios, doc_coparticipacao(registro, copart.sem_coparticipacao)
