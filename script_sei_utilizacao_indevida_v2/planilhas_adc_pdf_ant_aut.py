"""Fluxo alternativo ADC PDF ANT AUT: planilhas de utilização do processo em PDF.

Procura na árvore as planilhas de utilização (Titular, Dependentes e Anexo
RELAÇÃO ATENDIMENTO), baixa cada uma, gera o PDF e o insere no processo.

Retomada: o nome do PDF traz o número SEI da planilha de origem. Planilha
cujo PDF já está na árvore não é baixada nem inserida de novo. O Anexo tem
modelo próprio, por beneficiário, e o nome do PDF traz só a matrícula: se cada
Anexo tem um PDF depois dele na árvore, nada é baixado; senão, os Anexos são
baixados para saber o nome e só então procurados na árvore.

No fim, o processo fica aguardando o fluxo normal (main_geacs_inicial.py). O que já está no
fluxo normal ou é VELHO recebe os PDFs e continua onde estava: adicionar o
marcador apagaria o estado atual.
"""

import logging
import re
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from constantes import DIR_ADC_PDF_ANT_AUT_PDF, DIR_ADC_PDF_ANT_AUT_PLANILHAS
from docs_processo import numero_sei_por_nome
from processo_fechado import reabrir_processo_fechado, tem_incluir_documento
from rede_propria import ErroAvaliacao
from Registro import ProxAcao
from relatorios_mantis import TIPO_DOC, anexar_pdf
from sei_automacao.processo import listar_documentos_arvore, selecionar_doc_arvore
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from tags import (
    TAG_AGUARDA_FLUXO_NORMAL,
    TAG_PROCESSO_NOVO,
    adicionar_tag_se_ausente,
    eh_velho_pelos_marcadores,
    estado_atual,
)
from transformar_xls_em_pdf import transformar_xls_em_pdf

logger = logging.getLogger(__name__)

TIMEOUT_DOWNLOAD = 60
_INTERVALO_DOWNLOAD = 0.5
_SUFIXOS_TEMPORARIOS = ('.crdownload', '.tmp')
_TENTATIVAS_ANEXAR = 3
_ESPERA_NOVA_TENTATIVA = 5

# Maior Anexo visto: 7 beneficiários. Acima do limite é uma base geral, com
# dados de terceiros, e não vira PDF
_MAX_BENEFICIARIOS_ANEXO = 20
_TOLERANCIA_TOTAL = 0.01

# Os nomes são digitados à mão no SEI: variam em acento, plural e digitação
# (ex.: "Anexo RELACAO ANTENDIMENTOS"). Cada palavra é comparada com a esperada
_SIMILARIDADE_MINIMA = 0.8
_PALAVRAS_IGNORADAS = frozenset({'de', 'do', 'dos', 'da', 'das'})
_ABREVIACOES = {'tit': 'titular', 'dep': 'dependentes'}
_NOME_TITULAR = ('planilha', 'utilizacao', 'titular')
_NOME_DEPENDENTES = ('planilha', 'utilizacao', 'dependentes')
_NOME_ANEXO = ('anexo', 'relacao', 'atendimento')

_REFERENCIA = 'REFERENCIA'
_MATRICULA_BENEFICIARIO = 'MATRICULA_BENEFICIARIO'
_NOME_BENEFICIARIO = 'NOME_BENEFICIARIO'
_MATRICULA_DEPENDENTE = 'MATRICULA_DEPENDENTE'
_DATA = 'DAT_ATENDIMENTO'
_VALOR = 'VAL_PAGAR'

# Coluna da planilha -> coluna do PDF (mesmo layout dos relatórios do MANTIS)
_COLUNAS_TITULAR = {
    'NOME_PRESTADOR': 'PRESTADOR',
    _DATA: 'DATA DO ATENDIMENTO',
    'PROCEDIMENTO': 'PROCEDIMENTO',
    _VALOR: 'VALOR PAGO',
}
_COLUNAS_ANEXO = {
    'NOME_PRESTADOR': 'PRESTADOR',
    _MATRICULA_BENEFICIARIO: 'MATRICULA BENEFICIARIO',
    _NOME_BENEFICIARIO: 'NOME BENEFICIARIO',
    _DATA: 'DATA DO ATENDIMENTO',
    _VALOR: 'VALOR PAGO',
}
_COLUNAS_DEPENDENTES = {
    'NOME_PRESTADOR': 'PRESTADOR',
    _MATRICULA_DEPENDENTE: 'MATRICULA DEPENDENTE',
    'NOME_DEPENDENTE': 'NOME DEPENDENTE',
    _DATA: 'DATA DO ATENDIMENTO',
    _VALOR: 'VALOR PAGO',
}


@dataclass(frozen=True)
class TipoPlanilha:
    tipo_pdf: str
    tipo_curto: str
    colunas: tuple[tuple[str, str], ...]


TITULAR = TipoPlanilha('Titular', 'Tit.', tuple(_COLUNAS_TITULAR.items()))
DEPENDENTES = TipoPlanilha('Dependente(s)', 'Dep.', tuple(_COLUNAS_DEPENDENTES.items()))
ANEXO = TipoPlanilha('Beneficiário(s)', 'Ben.', tuple(_COLUNAS_ANEXO.items()))


@dataclass(frozen=True)
class RelatorioPlanilha:
    # Anexo: matrícula do beneficiário ou, com vários, a primeira da planilha e
    # a quantidade dos outros ("3542985 e mais 2"). O nome fica vazio: a
    # planilha não diz quem é o titular
    matricula_titular: str
    nome_titular: str
    df: pd.DataFrame


def _palavras(nome: str) -> list[str]:
    """Palavras do nome, sem acentos, maiúsculas e preposições e com as
    abreviações por extenso."""
    sem_acento = ''.join(c for c in unicodedata.normalize('NFKD', nome) if not unicodedata.combining(c))
    return [_ABREVIACOES.get(palavra, palavra) for palavra in re.findall(r'[a-z]+', sem_acento.casefold()) if palavra not in _PALAVRAS_IGNORADAS]


def _comeca_com(palavras: list[str], esperadas: tuple[str, ...]) -> bool:
    if len(palavras) < len(esperadas):
        return False
    return all(SequenceMatcher(None, palavra, esperada).ratio() >= _SIMILARIDADE_MINIMA for palavra, esperada in zip(palavras, esperadas, strict=False))


def tipo_da_planilha(doc: dict) -> TipoPlanilha | None:
    """Tipo da planilha pelo nome na árvore; None se não for uma delas."""
    palavras = _palavras(doc['nome_arvore'])
    if _comeca_com(palavras, _NOME_DEPENDENTES):
        return DEPENDENTES
    if _comeca_com(palavras, _NOME_TITULAR):
        return TITULAR
    if _comeca_com(palavras, _NOME_ANEXO):
        return ANEXO
    return None


def encontrar_planilhas(tds_docs: list[dict]) -> list[dict]:
    return [doc for doc in tds_docs if tipo_da_planilha(doc) is not None]


def nome_pdf(tipo: TipoPlanilha, matricula_titular: str, numero_sei_planilha: str) -> str:
    if tipo is ANEXO:
        return f'Utilização {tipo.tipo_curto} - {matricula_titular}'
    return f'Utilização {tipo.tipo_curto} - {matricula_titular} - SEI {numero_sei_planilha}'


def encontrar_pdf_pelo_nome_exato(tds_docs: list[dict], nome: str) -> dict | None:
    """Nome inteiro: a matrícula de um Anexo pode ser o início de outra."""
    return next((doc for doc in reversed(tds_docs) if doc['nome_arvore'] == f'{TIPO_DOC} {nome}'), None)


def encontrar_pdf_da_planilha(tds_docs: list[dict], numero_sei_planilha: str) -> dict | None:
    return next(
        (doc for doc in reversed(tds_docs) if doc['nome_arvore'].startswith(f'{TIPO_DOC} Utilização ') and doc['nome_arvore'].endswith(f' - SEI {numero_sei_planilha}')),
        None,
    )


# ---------------------------------------------------------------------------
# Leitura da planilha
# ---------------------------------------------------------------------------


def _converter_data(valor) -> pd.Timestamp:
    """A data vem como data do Excel ou como texto DD/MM/AAAA, conforme a
    planilha. Número e texto em outro formato viram NaT."""
    if isinstance(valor, datetime):
        return pd.Timestamp(valor)
    if isinstance(valor, str):
        return pd.to_datetime(valor.strip(), format='%d/%m/%Y', errors='coerce')
    return pd.NaT


def _valor_unico(df: pd.DataFrame, coluna: str, nome_arquivo: str):
    valores = df[coluna].dropna().unique()
    if len(valores) != 1:
        raise ErroAvaliacao(f'Planilha {nome_arquivo}: esperado um único valor em {coluna}, encontrados {len(valores)}')
    return valores[0]


def _nome_do_titular(df: pd.DataFrame, nome_arquivo: str) -> str:
    """A matrícula é única, mas o nome varia: outras maiúsculas, acentos ou
    preposições, casamento e erro de digitação. Vale o nome com mais linhas
    (um erro de digitação isolado não vira o nome do PDF) e, dentro dele, a
    forma mais completa."""
    nomes = [str(nome).strip() for nome in df[_NOME_BENEFICIARIO].dropna()]
    contagem = Counter(tuple(_palavras(nome)) for nome in nomes)
    if not contagem:
        raise ErroAvaliacao(f'Planilha {nome_arquivo}: esperado um único valor em {_NOME_BENEFICIARIO}, encontrados 0')
    if len(contagem) > 1:
        logger.warning(f'Planilha {nome_arquivo}: {len(contagem)} nomes para a mesma matrícula; vale o mais frequente')
    mais_frequente = contagem.most_common(1)[0][0]
    return max((nome for nome in nomes if tuple(_palavras(nome)) == mais_frequente), key=len)


def _matricula_em_texto(valor) -> str:
    return f'{valor:.0f}' if isinstance(valor, float) else str(valor).strip()


def _numerico(coluna: pd.Series, nome_arquivo: str) -> pd.Series:
    try:
        return pd.to_numeric(coluna)
    except (ValueError, TypeError) as e:
        raise ErroAvaliacao(f'Planilha {nome_arquivo}: valor não numérico em {coluna.name}') from e


def _remover_rodape(df: pd.DataFrame) -> pd.DataFrame:
    """Rodapé de total fora do padrão (ex.: COD_PRESTADOR = TOTAL): última
    linha sem matrícula e sem data, com a soma das demais. Sem a soma não é
    rodapé, e a linha segue para a validação."""
    ultima = df.iloc[-1]
    if len(df) < 2 or pd.notna(ultima[_MATRICULA_BENEFICIARIO]) or pd.notna(ultima[_DATA]):  # noqa: PLR2004
        return df
    valores = pd.to_numeric(df[_VALOR], errors='coerce')
    if abs(valores.iloc[-1] - valores.iloc[:-1].sum()) <= _TOLERANCIA_TOTAL:
        return df.iloc[:-1].copy()
    return df


def ler_planilha(arquivo: Path, tipo: TipoPlanilha) -> RelatorioPlanilha:
    """Lê a primeira aba e devolve o titular e os dados no layout do PDF."""
    if arquivo.suffix.casefold() != '.xlsx':
        raise ErroAvaliacao(f'Planilha {arquivo.name}: só o formato .xlsx é aceito')

    # Já houve planilha com a base geral na primeira aba e o processo na
    # segunda: não dá para escolher a aba sem conferir
    with pd.ExcelFile(arquivo) as planilha:
        abas = planilha.sheet_names
    if len(abas) > 1:
        raise ErroAvaliacao(f'Planilha {arquivo.name}: {len(abas)} abas ({", ".join(abas)}): conferir manualmente qual é a do processo')

    colunas = dict(tipo.colunas)
    df = pd.read_excel(arquivo)
    df.columns = [str(coluna).strip() for coluna in df.columns]
    faltando = [coluna for coluna in (_REFERENCIA, _MATRICULA_BENEFICIARIO, _NOME_BENEFICIARIO, *colunas) if coluna not in df.columns]
    if faltando:
        raise ErroAvaliacao(f'Planilha {arquivo.name}: colunas não encontradas: {faltando}')

    # O Anexo RELAÇÃO ATENDIMENTO termina com uma linha de total
    df = df[df[_REFERENCIA].astype(str).str.strip().str.casefold() != 'total'].copy()
    if df.empty:
        raise ErroAvaliacao(f'Planilha {arquivo.name}: sem atendimentos')
    df = _remover_rodape(df)

    df[_DATA] = df[_DATA].map(_converter_data)
    if df[_DATA].isna().any():
        raise ErroAvaliacao(f'Planilha {arquivo.name}: atendimento sem data válida')
    df[_VALOR] = _numerico(df[_VALOR], arquivo.name).fillna(0.0)
    for coluna in (_MATRICULA_DEPENDENTE, _MATRICULA_BENEFICIARIO):
        if coluna in colunas:
            df[coluna] = _numerico(df[coluna], arquivo.name)
            if df[coluna].isna().any():
                raise ErroAvaliacao(f'Planilha {arquivo.name}: atendimento sem matrícula em {coluna}')

    relatorio = df[list(colunas)].rename(columns=colunas)
    textos = relatorio.select_dtypes(exclude=['number', 'datetime']).columns
    relatorio[textos] = relatorio[textos].fillna('')
    if tipo is ANEXO:
        matriculas = df[_MATRICULA_BENEFICIARIO].unique()
        if len(matriculas) > _MAX_BENEFICIARIOS_ANEXO:
            raise ErroAvaliacao(f'Planilha {arquivo.name}: {len(matriculas)} beneficiários (máximo {_MAX_BENEFICIARIOS_ANEXO}): conferir se é a planilha do processo')
        primeira = _matricula_em_texto(matriculas[0])
        return RelatorioPlanilha(primeira if len(matriculas) == 1 else f'{primeira} e mais {len(matriculas) - 1}', '', relatorio)
    return RelatorioPlanilha(
        matricula_titular=_matricula_em_texto(_valor_unico(df, _MATRICULA_BENEFICIARIO, arquivo.name)),
        nome_titular=_nome_do_titular(df, arquivo.name),
        df=relatorio,
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _arquivos_baixados() -> set[Path]:
    return {caminho for caminho in DIR_ADC_PDF_ANT_AUT_PLANILHAS.iterdir() if caminho.is_file()}


def _downloads_em_andamento() -> set[Path]:
    return {caminho for caminho in _arquivos_baixados() if caminho.suffix.casefold() in _SUFIXOS_TEMPORARIOS}


def _descartar_downloads_em_andamento() -> None:
    """O arquivo que chegasse depois seria confundido com o da próxima planilha."""
    for caminho in _downloads_em_andamento():
        logger.warning(f'Download não terminou em {TIMEOUT_DOWNLOAD}s; descartado: {caminho.name}')
        caminho.unlink(missing_ok=True)


def _esperar_downloads_anteriores() -> None:
    """Rede de segurança: o download demorado é descartado ao passar do tempo,
    mas o temporário pode aparecer depois disso. O que não terminar é
    descartado, para um arquivo preso não parar os processos seguintes."""
    limite = time.monotonic() + TIMEOUT_DOWNLOAD
    while time.monotonic() < limite:
        if not _downloads_em_andamento():
            return
        time.sleep(_INTERVALO_DOWNLOAD)
    _descartar_downloads_em_andamento()


def _esperar_download(antes: set[Path], numero_sei: str) -> Path:
    limite = time.monotonic() + TIMEOUT_DOWNLOAD
    while time.monotonic() < limite:
        novos = _arquivos_baixados() - antes
        if novos and not any(caminho.suffix.casefold() in _SUFIXOS_TEMPORARIOS for caminho in novos):
            return sorted(novos)[0]
        time.sleep(_INTERVALO_DOWNLOAD)
    raise ErroAvaliacao(f'Planilha {numero_sei} não foi baixada em {TIMEOUT_DOWNLOAD}s')


def baixar_planilha(driver: webdriver.Remote, doc: dict) -> Path:
    """Abrir a planilha na árvore já inicia o download. O arquivo é salvo
    com o número SEI no início do nome, pois o nome original não identifica
    o documento e pode se repetir."""
    _esperar_downloads_anteriores()
    antes = _arquivos_baixados()
    try:
        selecionar_doc_arvore(driver, numero_sei=doc['numero_sei'])
    except ValueError:
        # A planilha não tem visualização: o que importa é o download
        logger.debug(f'Planilha {doc["numero_sei"]} aberta sem o iframe de visualização')
    driver.switch_to.default_content()

    try:
        baixado = _esperar_download(antes, doc['numero_sei'])
    except ErroAvaliacao:
        # O erro para o processo, e a execução segue sem esperar esta planilha
        _descartar_downloads_em_andamento()
        raise
    destino = DIR_ADC_PDF_ANT_AUT_PLANILHAS / f'{doc["numero_sei"]}_{baixado.name}'
    baixado.replace(destino)
    logger.info(f'Planilha baixada: {doc["nome_arvore"]} (SEI {doc["numero_sei"]}) em {destino.name}')
    return destino


# ---------------------------------------------------------------------------
# Fluxo
# ---------------------------------------------------------------------------


def _garantir_processo_aberto(driver: webdriver.Remote, registro) -> None:
    """Processo sem "Incluir Documento" (ex.: concluído na unidade) é reaberto
    e continua aberto depois de receber os PDFs. Chamada antes de baixar as
    planilhas: sem como reabrir, o processo para aqui."""
    # Abrir as pastas da árvore pode trocar a tela, e o botão sumiria sem o
    # processo estar fechado
    driver.refresh()
    if not tem_incluir_documento(driver):
        reabrir_processo_fechado(driver, registro)
    # O refresh fecha as pastas da árvore, onde estão as planilhas
    listar_documentos_arvore(driver)


def _recarregar_processo(driver: webdriver.Remote) -> None:
    """Depois de anexar um PDF, a tela muda e a inclusão seguinte falhava
    quase sempre. Recarregar volta à tela do processo, como no 1º PDF."""
    driver.refresh()
    if not tem_incluir_documento(driver):
        raise TimeoutException('Tela do processo sem "Incluir Documento"')


def _anexar_pdf_com_novas_tentativas(driver: webdriver.Remote, num: str, caminho_pdf: Path) -> None:
    """Com o SEI lento, a tela do processo pode não carregar a tempo. O tempo
    esgotado pode vir depois de salvar: só tenta de novo se o PDF não entrou."""
    for tentativa in range(1, _TENTATIVAS_ANEXAR + 1):
        try:
            _recarregar_processo(driver)
            anexar_pdf(driver, num, caminho_pdf, datetime.now())
            return
        except (TimeoutException, StaleElementReferenceException):
            if tentativa == _TENTATIVAS_ANEXAR:
                raise
            logger.warning(f'Tempo esgotado ao anexar {num} (tentativa {tentativa} de {_TENTATIVAS_ANEXAR})')
            logger.debug('Detalhes da tentativa', exc_info=True)

        time.sleep(_ESPERA_NOVA_TENTATIVA)
        if encontrar_pdf_pelo_nome_exato(listar_documentos_arvore(driver), num) is not None:
            logger.info(f'PDF {num} entrou na árvore apesar do tempo esgotado')
            return


def _inserir_pdf(driver: webdriver.Remote, registro, tipo: TipoPlanilha, relatorio: RelatorioPlanilha, numero_planilha: str, dir_pdf: Path) -> None:
    # Uma pasta por planilha: o processo pode ter mais de uma do mesmo titular
    pasta_pdf = dir_pdf / numero_planilha
    pasta_pdf.mkdir(parents=True, exist_ok=True)
    caminho_pdf = transformar_xls_em_pdf(
        tit_matricula=relatorio.matricula_titular,
        tit_nome=relatorio.nome_titular.upper(),
        tipo=tipo.tipo_pdf,
        df=relatorio.df,
        path_destino=pasta_pdf,
    )

    num = nome_pdf(tipo, relatorio.matricula_titular, numero_planilha)
    _anexar_pdf_com_novas_tentativas(driver, num, caminho_pdf)
    registro.pdfs_incluidos.append(num)
    numero_sei = numero_sei_por_nome(driver, f'{TIPO_DOC} {num}')
    if numero_sei is None:
        raise ErroAvaliacao(f'PDF anexado, mas não encontrado na árvore ({num}): a próxima execução o encontra pelo nome')
    logger.info(f'PDF anexado ao processo: {num} ({numero_sei})')


def _pdfs_de_todos_os_anexos(tds_docs: list[dict]) -> list[dict] | None:
    """PDFs de Anexo da árvore, se cada Anexo tem um depois dele (o PDF entra
    depois da planilha). Senão, None: o nome não diz de qual Anexo é o PDF, e
    um Anexo novo depois de um PDF antigo ainda precisa do seu."""
    pdfs: list[dict] = []
    disponiveis = 0
    for doc in reversed(tds_docs):
        if doc['nome_arvore'].startswith(f'{TIPO_DOC} Utilização {ANEXO.tipo_curto} - '):
            pdfs.append(doc)
            disponiveis += 1
        elif tipo_da_planilha(doc) is ANEXO:
            if disponiveis == 0:
                return None
            disponiveis -= 1
    return pdfs


def _inserir_pdfs_dos_anexos(driver: webdriver.Remote, registro, anexos: list[dict], obter_arquivo: Callable[[dict], Path], dir_pdf: Path) -> None:
    """O nome do PDF do Anexo não identifica a planilha: dois com o mesmo nome
    não dão para distinguir, e o processo para antes de inserir qualquer um."""
    relatorios = {doc['numero_sei']: ler_planilha(obter_arquivo(doc), ANEXO) for doc in anexos}
    nomes = {numero: nome_pdf(ANEXO, relatorio.matricula_titular, numero) for numero, relatorio in relatorios.items()}
    repetidos = sorted({nome for nome in nomes.values() if list(nomes.values()).count(nome) > 1})
    if repetidos:
        raise ErroAvaliacao(f'Anexos do processo com o mesmo nome de PDF ({", ".join(repetidos)}): separar manualmente')

    for doc in anexos:
        numero = doc['numero_sei']
        existente = encontrar_pdf_pelo_nome_exato(registro.tds_docs, nomes[numero])
        if existente is not None:
            registro.pdfs_na_arvore.append(existente['numero_sei'])
            logger.warning(f'Retomada: PDF do Anexo {numero} já está na árvore ({existente["numero_sei"]}); não será anexado de novo')
        else:
            _inserir_pdf(driver, registro, ANEXO, relatorios[numero], numero, dir_pdf)


def _tratar_anexos(driver: webdriver.Remote, registro, anexos: list[dict], obter_arquivo: Callable[[dict], Path], dir_pdf: Path) -> None:
    if not anexos:
        return

    existentes = _pdfs_de_todos_os_anexos(registro.tds_docs)
    if existentes is None:
        _inserir_pdfs_dos_anexos(driver, registro, anexos, obter_arquivo, dir_pdf)
    else:
        registro.pdfs_na_arvore += [doc['numero_sei'] for doc in existentes]
        logger.warning(f'Retomada: PDF dos {len(anexos)} Anexo(s) já está na árvore; a planilha não será baixada')

    for doc in anexos:
        numero = doc['numero_sei']
        antigo = encontrar_pdf_da_planilha(registro.tds_docs, numero)
        if antigo is not None:
            registro.pdfs_antigos_a_excluir.append(antigo['numero_sei'])
            logger.warning(f'PDF do Anexo {numero} no modelo antigo ({antigo["numero_sei"]}): excluir manualmente')


def _fica_no_estado_atual(registro) -> bool:
    """Já está no fluxo normal (com estado) ou é VELHO pelos marcadores. O
    VELHO pelos memos é separado pelo main_geacs_inicial."""
    return eh_velho_pelos_marcadores(registro) or estado_atual(registro) not in {None, TAG_AGUARDA_FLUXO_NORMAL}


def _falta_pdf(tds_docs: list[dict], planilhas: list[dict]) -> bool:
    """Do Anexo só se sabe o nome do PDF lendo a planilha: se _pdfs_de_todos_os_anexos
    não resolve, conta como faltando."""
    anexos = [doc for doc in planilhas if tipo_da_planilha(doc) is ANEXO]
    if anexos and _pdfs_de_todos_os_anexos(tds_docs) is None:
        return True
    return any(encontrar_pdf_da_planilha(tds_docs, doc['numero_sei']) is None for doc in planilhas if tipo_da_planilha(doc) is not ANEXO)


def inserir_pdfs(driver: webdriver.Remote, registro, planilhas: list[dict], obter_arquivo: Callable[[dict], Path], dir_pdf: Path) -> None:
    """Insere o PDF das planilhas da árvore que ainda não têm. obter_arquivo
    devolve o arquivo .xlsx de cada uma (usado também pelo fluxo ADC PDF ANT MAN)."""
    if _falta_pdf(registro.tds_docs, planilhas):
        _garantir_processo_aberto(driver, registro)

    for doc in planilhas:
        if tipo_da_planilha(doc) is ANEXO:
            continue
        existente = encontrar_pdf_da_planilha(registro.tds_docs, doc['numero_sei'])
        if existente is not None:
            registro.pdfs_na_arvore.append(existente['numero_sei'])
            logger.warning(f'Retomada: PDF da planilha {doc["numero_sei"]} já está na árvore ({existente["numero_sei"]}); não será anexado de novo')
            continue
        tipo = tipo_da_planilha(doc)
        _inserir_pdf(driver, registro, tipo, ler_planilha(obter_arquivo(doc), tipo), doc['numero_sei'], dir_pdf)

    _tratar_anexos(driver, registro, [doc for doc in planilhas if tipo_da_planilha(doc) is ANEXO], obter_arquivo, dir_pdf)


def deixar_aguardando_fluxo_normal(driver: webdriver.Remote, registro) -> bool:
    """Adiciona os marcadores que deixam o processo para o fluxo normal.
    False se ele fica como está (já no fluxo normal ou VELHO)."""
    if _fica_no_estado_atual(registro):
        logger.info('Processo já no fluxo normal ou VELHO: mantido no estado atual')
        return False

    adicionar_tag_se_ausente(driver, registro, TAG_PROCESSO_NOVO)
    adicionar_tag_se_ausente(driver, registro, TAG_AGUARDA_FLUXO_NORMAL)
    return True


def inserir_pdfs_das_planilhas(driver: webdriver.Remote, registro) -> None:
    planilhas = encontrar_planilhas(registro.tds_docs)
    registro.planilhas_sei = [doc['numero_sei'] for doc in planilhas]
    if not planilhas:
        logger.warning('Nenhuma planilha de utilização na árvore')
        registro.prox_acao = ProxAcao.ADC_PDF_ANT_AUT_SEM_PLANILHAS
        return

    logger.info(f'{len(planilhas)} planilha(s) na árvore: {[doc["nome_arvore"] for doc in planilhas]}')
    inserir_pdfs(driver, registro, planilhas, lambda doc: baixar_planilha(driver, doc), DIR_ADC_PDF_ANT_AUT_PDF)
    registro.prox_acao = ProxAcao.ADC_PDF_ANT_AUT_AGUARDA_FLUXO_NORMAL if deixar_aguardando_fluxo_normal(driver, registro) else ProxAcao.ADC_PDF_ANT_AUT_ESTADO_MANTIDO
