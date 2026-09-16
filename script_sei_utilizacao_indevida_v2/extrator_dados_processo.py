import re
from typing import Dict

from memorandos.DadosProcesso import DadosProcesso

# Ajuste o import acima conforme o pacote real do projeto, por exemplo:
# from memorandos.MemoDisa import DadosBeneficiario


class FormatoMemorandoInvalido(ValueError):
    """
    Levantada quando o texto do memorando
    não corresponde ao modelo esperado.
    """


# Marcadores que precisam existir no texto para que ele seja considerado
# aderente ao modelo do Memorando IPSEMG/APIS-UTILIZAÇÃO.
_MARCADORES_OBRIGATORIOS: Dict[str, str] = {
    'remetente IPSEMG/APIS-UTILIZAÇÃO': r'IPSEMG/APIS-UTILIZA[ÇC][ÃA]O',
    'campo "Nome completo"': r'Nome completo:',
    'campo "Matrícula" (titular)': r'Matr[íi]cula:',
    'campo "Período titular"': r'Per[íi]odo de apura[çc][ãa]o do titular:',
    'campo "Matrícula dos dependentes"': r'Matr[íi]cula dos dependentes:',
}

# Padrões para extração de cada campo. Cada um captura o restante da linha
# após o rótulo (o "." não casa com quebra de linha, então a captura para
# automaticamente no fim da linha).
_PADRAO_NOME_TITULAR = re.compile(r'Nome completo:\s*(.+)')
_PADRAO_MATRICULA_TITULAR = re.compile(r'Matr[íi]cula:\s*(.+)')
_PADRAO_PERIODO_TITULAR = re.compile(
    r'Per[íi]odo de apura[çc][ãa]o do titular:\s*(.+)'
)
_PADRAO_MATRICULAS_DEPENDENTES = re.compile(
    r'Matr[íi]cula dos dependentes:\s*(.+)'
)
_PADRAO_ASSINATURA_ELETRONICA = re.compile(
    r'Documento assinado eletronicamente', flags=re.IGNORECASE
)

# Data no formato dd/mm/aaaa (ex.: 01/12/2023), usada para detectar se há
# período informado para os dependentes após o respectivo campo.
_PADRAO_DATA = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')


def validar_template(doc_text: str) -> None:
    """
    Verifica se `doc_text` contém todos os marcadores esperados do modelo de
    Memorando IPSEMG/APIS-UTILIZAÇÃO.

    Levanta FormatoMemorandoInvalido, listando os marcadores ausentes, caso o
    texto não corresponda ao modelo.
    """
    ausentes = [
        descricao
        for descricao, padrao in _MARCADORES_OBRIGATORIOS.items()
        if not re.search(padrao, doc_text, flags=re.IGNORECASE)
    ]

    if ausentes:
        lista = '; '.join(ausentes)
        raise FormatoMemorandoInvalido(
            f'O texto não corresponde ao modelo esperado. Itens ausentes ou '
            f'divergentes: {lista}.'
        )


def _extrair_campo(padrao: re.Pattern, doc_text: str, nome_campo: str) -> str:
    match = padrao.search(doc_text)
    if not match or not match.group(1).strip():
        raise FormatoMemorandoInvalido(
            f'Não foi possível extrair o campo "{nome_campo}" do texto.'
        )
    return match.group(1).strip()


def _extrair_matriculas_dependentes(doc_text: str) -> str:
    valor_bruto = _extrair_campo(
        _PADRAO_MATRICULAS_DEPENDENTES, doc_text, 'Matrícula dos dependentes'
    )
    matriculas = [
        matricula
        for matricula in re.split(r'[;,\s]+', valor_bruto.strip())
        if matricula
    ]
    return '; '.join(matriculas)


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
    match_dependentes = _PADRAO_MATRICULAS_DEPENDENTES.search(doc_text)
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
    return _PADRAO_DATA.search(texto_janela) is not None


def extrair_dados_processo(doc_text: str) -> DadosProcesso:

    validar_template(doc_text)

    nome_titular = _extrair_campo(
        _PADRAO_NOME_TITULAR, doc_text, 'Nome completo'
    )
    matricula_titular = _extrair_campo(
        _PADRAO_MATRICULA_TITULAR, doc_text, 'Matrícula'
    )
    periodo_titular = _extrair_campo(
        _PADRAO_PERIODO_TITULAR, doc_text, 'Período de apuração do titular'
    )
    matriculas_dependentes = _extrair_matriculas_dependentes(doc_text)
    periodo_dependentes = _detectar_periodo_dependentes(doc_text)

    return DadosProcesso(
        nome_titular=nome_titular,
        matricula_titular=matricula_titular,
        periodo_titular=periodo_titular,
        matriculas_dependentes=matriculas_dependentes,
        periodo_dependentes=periodo_dependentes,
    )
