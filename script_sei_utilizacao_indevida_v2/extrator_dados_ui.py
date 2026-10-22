import re
from typing import Literal

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


class FormatoMemorandoInvalido(ValueError):
    """O memorando da APIS não está no modelo esperado."""


# ---------------------------------------------------------------------------
# Padrões únicos por campo — usados tanto para validar quanto para extrair.
# Definir uma única vez evita que a checagem de presença (validar_template)
# e a extração (_extrair_campo) divirjam entre si.
# ---------------------------------------------------------------------------

_PADRAO_REMETENTE = re.compile(r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O', flags=re.IGNORECASE)

# --- Modelo "novo_novo" (único aceito) ---
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
_PADRAO_MATRICULAS_DEPENDENTES_NOVO = re.compile(
    r'Matr[íi]culas? d(?:o|os) dependentes?:\s*'
    r'(\d{3,10}(?:(?:\s*[,;:/.]\s*|\s+e\s+|\s+)\d{3,10})*|)',
    flags=re.IGNORECASE,
)

_PADRAO_SEPARADOR_MATRICULAS = re.compile(r'\s+e\s+|[;,:/.]+|\s+', flags=re.IGNORECASE)


def validar_template(doc_text: str) -> Literal['novo_novo']:
    """Só o modelo "novo_novo" é aceito. Os modelos "novo_velho" (mesmos
    campos, sem o pedido de atualização do levantamento) e "velho" (campo
    "Segurado(a)") são formato inválido."""
    ausentes = [descricao for descricao, padrao in _CAMPOS_MODELO_NOVO.items() if not padrao.search(doc_text)]
    if not ausentes:
        if _PADRAO_ATUALIZACAO_LEVANTAMENTO.search(doc_text):
            return 'novo_novo'
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

    matriculas = [matricula for matricula in _PADRAO_SEPARADOR_MATRICULAS.split(valor_bruto.strip()) if matricula]
    return '; '.join(matriculas)


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


def extrair_dados_ui(doc_text: str) -> DadosUI:
    validar_template(doc_text)

    return DadosUI(
        nome_titular=_extrair_campo(_PADRAO_NOME_TITULAR_NOVO, doc_text, 'Nome completo'),
        matricula_titular=_extrair_campo(_PADRAO_MATRICULA_TITULAR_NOVO, doc_text, 'Matrícula'),
        periodo_titular=_extrair_campo(_PADRAO_PERIODO_TITULAR_NOVO, doc_text, 'Período de apuração do titular'),
        matriculas_dependentes=_extrair_matriculas_dependentes(doc_text),
        periodo_dependentes=_detectar_periodo_dependentes(doc_text),
    )
