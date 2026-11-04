import re
from typing import Literal, get_args

from mantis import interpretar_periodo
from rede_propria import ErroAvaliacao, normalizar_matricula

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


class FormatoMemorandoInvalido(ValueError):
    """O memorando da APIS não está no modelo esperado."""


# ---------------------------------------------------------------------------
# Padrões únicos por campo — usados tanto para validar quanto para extrair.
# Definir uma única vez evita que a checagem de presença (validar_template)
# e a extração (_extrair_campo) divirjam entre si.
# ---------------------------------------------------------------------------

_PADRAO_REMETENTE = re.compile(r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O', flags=re.IGNORECASE)

ModeloMemoApis = Literal['periodo_por_dependente', 'novo_novo']
MODELO_PERIODO_POR_DEPENDENTE, MODELO_NOVO_NOVO = get_args(ModeloMemoApis)

# --- Modelo "novo_novo" ---
# O que distingue o novo_novo do novo_velho (mesmos campos) é o pedido de
# atualização do levantamento. Exemplo: Memorando IPSEMG/APIS-UTILIZAÇÃO
# nº 2627/2026.
_PADRAO_ATUALIZACAO_LEVANTAMENTO = re.compile(r'atualiza[çc][ãa]o\s+do\s+levantamento\s+de\s+utiliza[çc][ãa]o', flags=re.IGNORECASE)
_PADRAO_NOME_TITULAR_NOVO = re.compile(r'Nome completo:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_MATRICULA_TITULAR_NOVO = re.compile(r'Matr[íi]cula:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_PERIODO_TITULAR_NOVO = re.compile(r'Per[íi]odo de apura[çc][ãa]o do titular:\s*(.+)', flags=re.IGNORECASE)

_PADRAO_ASSINATURA_ELETRONICA = re.compile(r'Documento assinado eletronicamente', flags=re.IGNORECASE)

_CAMPOS_MODELO_NOVO: dict[str, re.Pattern] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': _PADRAO_REMETENTE,
    'campo "Nome completo"': _PADRAO_NOME_TITULAR_NOVO,
    'campo "Matrícula" (titular)': _PADRAO_MATRICULA_TITULAR_NOVO,
    'campo "Período titular"': _PADRAO_PERIODO_TITULAR_NOVO,
}

# --- Modelo "periodo_por_dependente" (período de apuração de cada
# dependente) ---
# Procurado ANTES do novo_novo. Os campos do titular são os do novo_novo e
# cada dependente tem uma dupla de linhas, nesta ordem:
#   Matrícula do dependente: 555
#   Período de apuração do dependente: 01/01/2024 a 30/06/2024.
# A linha do período identifica o modelo. Ela é lida até o fim: período
# vazio é formato inválido, não a linha seguinte. Um resumo ("Matrículas dos
# dependentes: 555; 666") é ignorado.
_TRECHO_MATRICULA_DEPENDENTE = r'Matr[íi]cula do dependente:'
_TRECHO_PERIODO_DEPENDENTE = r'Per[íi]odo de apura[çc][ãa]o do dependente\s*:'
_PADRAO_LINHA_MATRICULA_DEPENDENTE = re.compile(_TRECHO_MATRICULA_DEPENDENTE, flags=re.IGNORECASE)
_PADRAO_LINHA_PERIODO_DEPENDENTE = re.compile(_TRECHO_PERIODO_DEPENDENTE, flags=re.IGNORECASE)
_PADRAO_DUPLA_DEPENDENTE = re.compile(
    rf'{_TRECHO_MATRICULA_DEPENDENTE}[^\S\n]*(.*?)\s*{_TRECHO_PERIODO_DEPENDENTE}[^\S\n]*(.*)',
    flags=re.IGNORECASE,
)
_PADRAO_MATRICULA_UNICA = re.compile(r'\d+(?:\s*[-./]\s*\d+)*')

# --- Modelos "novo_velho" e "velho" (não são mais aceitos; só identificados
# para a mensagem de erro) ---
_PADRAO_NOME_TITULAR_VELHO = re.compile(r'Segurad[oa]:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_PERIODO_TITULAR_VELHO = re.compile(
    r'per[íi]odos?\s*,?\s+de\s+\d{2}/\d{2}/\d{4}\s+a\s+\d{2}/\d{2}/\d{4}',
    flags=re.IGNORECASE,
)

_MARCADORES_MODELO_VELHO: dict[str, re.Pattern] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': _PADRAO_REMETENTE,
    'campo "Segurado(a)"': _PADRAO_NOME_TITULAR_VELHO,
    'campo "Matrícula" (titular)': _PADRAO_MATRICULA_TITULAR_NOVO,
    'período(s) do titular': _PADRAO_PERIODO_TITULAR_VELHO,
}

_PADROES_DATA = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
# A matrícula pode vir sem DV, com ele junto ou separado ("1234567 / 8",
# "1234567-8")
_TRECHO_MATRICULA = r'\d{3,10}(?:[^\S\n]*[-/][^\S\n]*\d(?!\d))?'
_PADRAO_MATRICULA = re.compile(_TRECHO_MATRICULA)
_PADRAO_MATRICULAS_DEPENDENTES_NOVO = re.compile(
    r'Matr[íi]culas? d(?:o|os) dependentes?:\s*'
    rf'({_TRECHO_MATRICULA}(?:(?:\s*[,;:/.]\s*|\s+e\s+|\s+){_TRECHO_MATRICULA})*|)',
    flags=re.IGNORECASE,
)


def eh_modelo_periodo_por_dependente(doc_text: str) -> bool:
    """O texto tem a linha do período de algum dependente."""
    return _PADRAO_LINHA_PERIODO_DEPENDENTE.search(doc_text) is not None


def _campos_ausentes(campos: dict[str, re.Pattern], doc_text: str) -> list[str]:
    return [descricao for descricao, padrao in campos.items() if not padrao.search(doc_text)]


def validar_template(doc_text: str) -> ModeloMemoApis:
    """O modelo com período por dependente é procurado primeiro (pela linha
    do período do dependente). Senão, só o modelo "novo_novo" é aceito. Os
    modelos "novo_velho" (mesmos campos, sem o pedido de atualização do
    levantamento) e "velho" (campo "Segurado(a)") são formato inválido."""
    if eh_modelo_periodo_por_dependente(doc_text):
        ausentes = _campos_ausentes(_CAMPOS_MODELO_NOVO, doc_text)
        if ausentes:
            raise FormatoMemorandoInvalido(f'O memorando está no modelo com período por dependente, mas faltam os campos {ausentes}')
        return MODELO_PERIODO_POR_DEPENDENTE

    ausentes = _campos_ausentes(_CAMPOS_MODELO_NOVO, doc_text)
    if not ausentes:
        if _PADRAO_ATUALIZACAO_LEVANTAMENTO.search(doc_text):
            return MODELO_NOVO_NOVO
        raise FormatoMemorandoInvalido('O memorando está no modelo "novo_velho" (sem o pedido de atualização do levantamento), que não é mais aceito')

    if all(padrao.search(doc_text) for padrao in _MARCADORES_MODELO_VELHO.values()):
        raise FormatoMemorandoInvalido('O memorando está no modelo "velho", que não é mais aceito')

    raise FormatoMemorandoInvalido(f'O texto não corresponde ao modelo esperado: faltam os campos {ausentes}')


def _extrair_campo(padrao: re.Pattern, doc_text: str, nome_campo: str, *, opcional: bool = False) -> str | None:
    match = padrao.search(doc_text)
    valor = match.group(1).strip() if match else ''
    if valor or opcional:
        return valor or None
    raise FormatoMemorandoInvalido(f'Não foi possível extrair o campo "{nome_campo}" do texto.')


def _extrair_matriculas_dependentes(doc_text: str) -> str | None:
    valor_bruto = _extrair_campo(_PADRAO_MATRICULAS_DEPENDENTES_NOVO, doc_text, 'Matrícula dos dependentes', opcional=True)
    if not valor_bruto:
        return None

    return '; '.join(_PADRAO_MATRICULA.findall(valor_bruto))


def _detectar_periodo_dependentes(doc_text: str) -> bool:
    """
    Verifica se há alguma data (dd/mm/aaaa) no texto entre o campo
    "Matrícula dos dependentes:" e o início do bloco de assinatura
    eletrônica ("Documento assinado eletronicamente..."). Qualquer
    quantidade de datas encontrada nessa janela (uma ou mais) faz
    retornar True.
    Se o tag de assinatura eletrônica não for encontrado, a busca
    considera o restante do texto até o final.
    """
    match_dependentes = _PADRAO_MATRICULAS_DEPENDENTES_NOVO.search(doc_text)
    if not match_dependentes:
        return False

    inicio_janela = match_dependentes.end()

    match_assinatura = _PADRAO_ASSINATURA_ELETRONICA.search(doc_text, pos=inicio_janela)
    fim_janela = match_assinatura.start() if match_assinatura else len(doc_text)

    texto_janela = doc_text[inicio_janela:fim_janela]
    return _PADROES_DATA.search(texto_janela) is not None


def _extrair_periodos_por_dependente(doc_text: str) -> dict[str, str]:
    """Matrícula do dependente (normalizada) -> período de apuração. Toda
    linha de matrícula ou de período precisa estar em uma dupla: fora dela,
    não se sabe qual período vale para o dependente."""
    duplas = list(_PADRAO_DUPLA_DEPENDENTE.finditer(doc_text))
    qtd_matriculas = len(_PADRAO_LINHA_MATRICULA_DEPENDENTE.findall(doc_text))
    qtd_periodos = len(_PADRAO_LINHA_PERIODO_DEPENDENTE.findall(doc_text))
    if not len(duplas) == qtd_matriculas == qtd_periodos:
        raise FormatoMemorandoInvalido(f'Há linhas de dependente fora de dupla: {qtd_matriculas} de matrícula, {qtd_periodos} de período e {len(duplas)} dupla(s)')

    periodos = {}
    for match in duplas:
        matricula_memo, periodo = match.group(1).strip(), match.group(2).strip().rstrip('.; ')
        if not _PADRAO_MATRICULA_UNICA.fullmatch(matricula_memo):
            raise FormatoMemorandoInvalido(f'A linha "Matrícula do dependente" deve ter uma única matrícula: "{matricula_memo}"')
        matricula = normalizar_matricula(matricula_memo)
        _validar_periodo_dependente(matricula, periodo)
        if matricula in periodos and periodos[matricula] != periodo:
            raise FormatoMemorandoInvalido(f'O dependente {matricula} aparece com dois períodos de apuração diferentes')
        periodos[matricula] = periodo
    return periodos


def _validar_periodo_dependente(matricula: str, periodo: str) -> None:
    """Número par de datas (cada intervalo tem início e fim) e, no conjunto,
    um período que o MANTIS consiga interpretar."""
    qtd_datas = len(_PADROES_DATA.findall(periodo))
    if not qtd_datas or qtd_datas % 2:
        raise FormatoMemorandoInvalido(f'O período do dependente {matricula} deve ter um número par de datas DD/MM/AAAA: "{periodo}"')
    try:
        interpretar_periodo(periodo, f'do dependente {matricula}')
    except ErroAvaliacao as e:
        raise FormatoMemorandoInvalido(str(e)) from e


def _extrair_dados_ui_periodo_por_dependente(doc_text: str) -> DadosUI:
    """Os períodos dos dependentes vêm definidos no memo: o fluxo não para
    pelo período variável (periodo_dependentes = False) e o MANTIS usa o
    período de cada um."""
    periodos = _extrair_periodos_por_dependente(doc_text)
    return DadosUI(
        nome_titular=_extrair_campo(_PADRAO_NOME_TITULAR_NOVO, doc_text, 'Nome completo'),
        matricula_titular=_extrair_campo(_PADRAO_MATRICULA_TITULAR_NOVO, doc_text, 'Matrícula'),
        periodo_titular=_extrair_campo(_PADRAO_PERIODO_TITULAR_NOVO, doc_text, 'Período de apuração do titular'),
        matriculas_dependentes='; '.join(periodos),
        periodo_dependentes=False,
        periodos_por_dependente=periodos,
    )


def extrair_dados_ui(doc_text: str) -> DadosUI:
    if validar_template(doc_text) == MODELO_PERIODO_POR_DEPENDENTE:
        return _extrair_dados_ui_periodo_por_dependente(doc_text)

    return DadosUI(
        nome_titular=_extrair_campo(_PADRAO_NOME_TITULAR_NOVO, doc_text, 'Nome completo'),
        matricula_titular=_extrair_campo(_PADRAO_MATRICULA_TITULAR_NOVO, doc_text, 'Matrícula'),
        periodo_titular=_extrair_campo(_PADRAO_PERIODO_TITULAR_NOVO, doc_text, 'Período de apuração do titular'),
        matriculas_dependentes=_extrair_matriculas_dependentes(doc_text),
        periodo_dependentes=_detectar_periodo_dependentes(doc_text),
    )
