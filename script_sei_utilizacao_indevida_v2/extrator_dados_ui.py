import re
from typing import Dict, Literal

from script_sei_utilizacao_indevida_v2.memorandos.DadosUI import DadosUI

# Ajuste o import acima conforme o pacote real do projeto, por exemplo:
# from memorandos.MemoDisa import DadosBeneficiario


class FormatoMemorandoInvalido(ValueError):
    def __init__(self, msg):
        super().__init__(msg)


# Marcadores que precisam existir no texto para que ele seja considerado
# aderente ao modelo do Memorando IPSEMG/APIS-UTILIZAÇÃO.
_MARCADORES_OBRIGATORIOS_NOVOS_NOVOS: Dict[str, str] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
    'campo "Nome completo"': r'Nome completo:',
    'campo "Matrícula" (titular)': r'Matr[íi]cula:',
    'campo "Período titular"': r'Per[íi]odo de apura[çc][ãa]o do titular:',
}

_MARCADORES_OBRIGATORIOS_NOVOS_VELHOS: Dict[str, str] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
    'campo "Segurado(a)"': r'Segurad[oa]:',
    'campo "Matrícula" (titular)': r'Matr[íi]cula:',
    'período(s) do titular': (
        r'per[íi]odos?\s+de\s+\d{2}/\d{2}/\d{4}\s+a\s+\d{2}/\d{2}/\d{4}'
    ),
}

# Padrões para extração de cada campo (modelo "novo"). Cada um captura o
# restante da linha após o rótulo (o "." não casa com quebra de linha, então
# a captura para automaticamente no fim da linha).
_PADROES_NOME_TITULAR_NOVO = [
    re.compile(r'Nome completo:\s*(.+)'),
    re.compile(r'Matr[íi]cula:\s*\d{5,10}-\d'),
]
_PADROES_MATRICULA_TITULAR_NOVO = [re.compile(r'Matr[íi]cula:\s*(.+)')]
_PADROES_PERIODO_TITULAR_NOVO = [
    re.compile(r'Per[íi]odo de apura[çc][ãa]o do titular:\s*(.+)')
]
_PADRAO_MATRICULAS_DEPENDENTES_NOVO = re.compile(
    r'Matr[íi]cula dos dependentes:\s*(.+)'
)
_PADRAO_ASSINATURA_ELETRONICA = re.compile(
    r'Documento assinado eletronicamente', flags=re.IGNORECASE
)

# Padrões para extração de cada campo (modelo "velho"). Neste modelo os
# dados vêm em texto corrido, não em campos rotulados isoladamente.
_PADROES_NOME_TITULAR_VELHO = [re.compile(r'Segurad[oa]:\s*(.+)')]
_PADROES_MATRICULA_TITULAR_VELHO = [re.compile(r'Matr[íi]cula:\s*(.+)')]
_PADRAO_PERIODO_TITULAR_VELHO = re.compile(
    r'per[íi]odos?\s+de\s+([^.]+)\.', flags=re.IGNORECASE
)
_PADRAO_MENCAO_DEPENDENTES_VELHO = re.compile(
    r'dependentes?', flags=re.IGNORECASE
)

# Valor fixo usado quando há menção a dependentes no modelo "velho", mas o
# texto não traz a matrícula deles explicitamente.
_VALOR_MATRICULA_DEPENDENTE_AVERIGUAR = 'AVERIGUAR'

# Data no formato dd/mm/aaaa (ex.: 01/12/2023), usada para detectar/extrair
# período informado para os dependentes após o respectivo campo/menção.
_PADROES_DATA = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')


def validar_template(doc_text: str) -> Literal['novo', 'velho']:
    """
    Verifica se `doc_text` contém todos os marcadores esperados de algum
    dos modelos de Memorando IPSEMG/APIS-UTILIZAÇÃO conhecidos ("novo" ou
    "velho").

    Levanta FormatoMemorandoInvalido caso o texto não corresponda a
    nenhum dos modelos esperados.
    """
    ausentes_novos_novos = [
        descricao
        for descricao, padrao in _MARCADORES_OBRIGATORIOS_NOVOS_NOVOS.items()
        if not re.search(padrao, doc_text, flags=re.IGNORECASE)
    ]

    if not ausentes_novos_novos:
        return 'novo'

    ausentes_novos_velhos = [
        descricao
        for descricao, padrao in _MARCADORES_OBRIGATORIOS_NOVOS_VELHOS.items()
        if not re.search(padrao, doc_text, flags=re.IGNORECASE)
    ]

    if not ausentes_novos_velhos:
        return 'velho'

    raise FormatoMemorandoInvalido(
        msg=('O texto não corresponde a nenhum dos modelos esperados')
    )


def _extrair_campo_novo_novo(
    padroes: list[re.Pattern],
    doc_text: str,
    nome_campo: str,
    valido_none: bool = False,
) -> str:
    for padrao in padroes:
        match = padrao.search(doc_text)
        if not match or not match.group(1).strip():
            continue
        else:
            return match.group(1).strip()

    if valido_none:
        return None
    else:
        raise FormatoMemorandoInvalido(
            msg=(f'Não foi possível extrair o campo "{nome_campo}" do texto.')
        )


def _extrair_matriculas_dependentes(doc_text: str) -> str:
    valor_bruto = _extrair_campo_novo_novo(
        [_PADRAO_MATRICULAS_DEPENDENTES_NOVO],
        doc_text,
        'Matrícula dos dependentes',
        valido_none=True,
    )
    if valor_bruto:
        matriculas = [
            matricula
            for matricula in re.split(r'[;,\s]+', valor_bruto.strip())
            if matricula
        ]
        return '; '.join(matriculas)
    else:
        return None


def _detectar_periodo_dependentes(doc_text: str) -> bool:
    """
    Verifica se há alguma data (dd/mm/aaaa) no texto entre o campo
    "Matrícula dos dependentes:" e o início do bloco de assinatura
    eletrônica ("Documento assinado eletronicamente..."). Qualquer
    quantidade de datas encontrada nessa janela (uma ou mais) faz
    retornar True.
    Se o marcador de assinatura eletrônica não for encontrado, a busca
    considera o restante do texto até o final.
    """
    match_dependentes = _PADRAO_MATRICULAS_DEPENDENTES_NOVO.search(doc_text)
    if not match_dependentes:
        return False

    inicio_janela = match_dependentes.end()

    match_assinatura = _PADRAO_ASSINATURA_ELETRONICA.search(
        doc_text, pos=inicio_janela
    )
    fim_janela = (
        match_assinatura.start() if match_assinatura else len(doc_text)
    )

    texto_janela = doc_text[inicio_janela:fim_janela]
    return _PADROES_DATA.search(texto_janela) is not None


def _extrair_matriculas_dependentes_velho(doc_text: str) -> str:
    """
    No modelo "velho" não há campo explícito de matrícula dos
    dependentes. Caso o texto mencione a palavra "dependente(s)", marca
    a matrícula como "AVERIGUAR" (a ser confirmada manualmente). Caso
    contrário, retorna None.
    """
    if _PADRAO_MENCAO_DEPENDENTES_VELHO.search(doc_text):
        return _VALOR_MATRICULA_DEPENDENTE_AVERIGUAR
    return None


def _extrair_periodo_dependentes_velho(doc_text: str) -> str:
    """
    Busca a primeira menção à palavra "dependente(s)" no texto e retorna
    todas as datas (dd/mm/aaaa) encontradas entre essa menção e o início
    do bloco de assinatura eletrônica ("Documento assinado
    eletronicamente..."), unidas por "; ".
    Se o marcador de assinatura eletrônica não for encontrado, a busca
    considera o restante do texto até o final.
    Retorna None se não houver menção a dependentes ou se não houver
    nenhuma data na janela.
    """
    match_dependentes = _PADRAO_MENCAO_DEPENDENTES_VELHO.search(doc_text)
    if not match_dependentes:
        return None

    inicio_janela = match_dependentes.end()

    match_assinatura = _PADRAO_ASSINATURA_ELETRONICA.search(
        doc_text, pos=inicio_janela
    )
    fim_janela = (
        match_assinatura.start() if match_assinatura else len(doc_text)
    )

    texto_janela = doc_text[inicio_janela:fim_janela]
    datas = _PADROES_DATA.findall(texto_janela)
    return '; '.join(datas) if datas else None


def extrair_dados_ui(doc_text: str) -> DadosUI:

    tipo = validar_template(doc_text)

    if tipo == 'novo':
        nome_titular = _extrair_campo_novo_novo(
            _PADROES_NOME_TITULAR_NOVO, doc_text, 'Nome completo'
        )
        matricula_titular = _extrair_campo_novo_novo(
            _PADROES_MATRICULA_TITULAR_NOVO, doc_text, 'Matrícula'
        )
        periodo_titular = _extrair_campo_novo_novo(
            _PADROES_PERIODO_TITULAR_NOVO,
            doc_text,
            'Período de apuração do titular',
        )
        matriculas_dependentes = _extrair_matriculas_dependentes(doc_text)
        periodo_dependentes = _detectar_periodo_dependentes(doc_text)

    elif tipo == 'velho':
        nome_titular = _extrair_campo_novo_novo(
            _PADROES_NOME_TITULAR_VELHO, doc_text, 'Segurado(a)'
        )
        matricula_titular = _extrair_campo_novo_novo(
            _PADROES_MATRICULA_TITULAR_VELHO, doc_text, 'Matrícula'
        )
        periodo_titular = _extrair_campo_novo_novo(
            [_PADRAO_PERIODO_TITULAR_VELHO],
            doc_text,
            'Período(s) do titular',
        )
        matriculas_dependentes = _extrair_matriculas_dependentes_velho(
            doc_text
        )
        periodo_dependentes = _extrair_periodo_dependentes_velho(doc_text)

    return DadosUI(
        nome_titular=nome_titular,
        matricula_titular=matricula_titular,
        periodo_titular=periodo_titular,
        matriculas_dependentes=matriculas_dependentes,
        periodo_dependentes=periodo_dependentes,
    )
