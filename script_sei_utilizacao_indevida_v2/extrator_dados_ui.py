import re
from typing import Dict, Literal

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI


class FormatoMemorandoInvalido(ValueError):
    def __init__(self, msg):
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Padrões únicos por campo — usados tanto para validar quanto para extrair.
# Definir uma única vez evita que a checagem de presença (validar_template)
# e a extração (_extrair_campo) divirjam entre si.
# ---------------------------------------------------------------------------

_PADRAO_REMETENTE = re.compile(r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O', flags=re.IGNORECASE)

# --- Modelo "novo" ---
_PADRAO_NOME_TITULAR_NOVO = re.compile(r'Nome completo:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_MATRICULA_TITULAR_NOVO = re.compile(r'Matr[íi]cula:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_PERIODO_TITULAR_NOVO = re.compile(r'Per[íi]odo de apura[çc][ãa]o do titular:\s*(.+)', flags=re.IGNORECASE)

_PADROES_NOME_TITULAR_NOVO = [_PADRAO_NOME_TITULAR_NOVO]
_PADROES_MATRICULA_TITULAR_NOVO = [_PADRAO_MATRICULA_TITULAR_NOVO]
_PADROES_PERIODO_TITULAR_NOVO = [_PADRAO_PERIODO_TITULAR_NOVO]


_PADRAO_ASSINATURA_ELETRONICA = re.compile(r'Documento assinado eletronicamente', flags=re.IGNORECASE)

_MARCADORES_OBRIGATORIOS_NOVOS_NOVOS: Dict[str, re.Pattern] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': _PADRAO_REMETENTE,
    'campo "Nome completo"': _PADRAO_NOME_TITULAR_NOVO,
    'campo "Matrícula" (titular)': _PADRAO_MATRICULA_TITULAR_NOVO,
    'campo "Período titular"': _PADRAO_PERIODO_TITULAR_NOVO,
}

# --- Modelo "velho" (não é mais aceito; só identificado para a mensagem de erro) ---
_PADRAO_NOME_TITULAR_VELHO = re.compile(r'Segurad[oa]:\s*(.+)', flags=re.IGNORECASE)
_PADRAO_PERIODO_TITULAR_VELHO = re.compile(
    r'per[íi]odos?\s*,?\s+de\s+\d{2}/\d{2}/\d{4}\s+a\s+\d{2}/\d{2}/\d{4}',
    flags=re.IGNORECASE,
)

_MARCADORES_MODELO_VELHO: Dict[str, re.Pattern] = {
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


def validar_template(doc_text: str) -> Literal['novo']:
    """Só o modelo "novo" é aceito. O modelo "velho" (campo "Segurado(a)")
    passou a ser formato inválido."""
    ausentes = [descricao for descricao, padrao in _MARCADORES_OBRIGATORIOS_NOVOS_NOVOS.items() if not padrao.search(doc_text)]
    if not ausentes:
        return 'novo'

    if all(padrao.search(doc_text) for padrao in _MARCADORES_MODELO_VELHO.values()):
        raise FormatoMemorandoInvalido(msg='O memorando está no modelo "velho", que não é mais aceito')

    raise FormatoMemorandoInvalido(msg=f'O texto não corresponde ao modelo esperado: faltam os campos {ausentes}')


def _extrair_campo(
    padroes: list[re.Pattern],
    doc_text: str,
    nome_campo: str,
    valido_none: bool = False,
) -> str | None:
    for padrao in padroes:
        match = padrao.search(doc_text)
        if not match or not match.group(1).strip():
            continue
        else:
            return match.group(1).strip()

    if valido_none:
        return None
    else:
        raise FormatoMemorandoInvalido(msg=(f'Não foi possível extrair o campo "{nome_campo}" do texto.'))


def _extrair_matriculas_dependentes(doc_text: str) -> str | None:
    valor_bruto = _extrair_campo(
        [_PADRAO_MATRICULAS_DEPENDENTES_NOVO],
        doc_text,
        'Matrícula dos dependentes',
        valido_none=True,
    )
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

    nome_titular = _extrair_campo(_PADROES_NOME_TITULAR_NOVO, doc_text, 'Nome completo')
    matricula_titular = _extrair_campo(_PADROES_MATRICULA_TITULAR_NOVO, doc_text, 'Matrícula')
    periodo_titular = _extrair_campo(
        _PADROES_PERIODO_TITULAR_NOVO,
        doc_text,
        'Período de apuração do titular',
    )
    matriculas_dependentes = _extrair_matriculas_dependentes(doc_text)
    periodo_dependentes = _detectar_periodo_dependentes(doc_text)

    return DadosUI(
        nome_titular=nome_titular,
        matricula_titular=matricula_titular,
        periodo_titular=periodo_titular,
        matriculas_dependentes=matriculas_dependentes,
        periodo_dependentes=periodo_dependentes,
    )
